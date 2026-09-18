#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_fundamentals.py — 半自动基本面刷新管道（路线 B）

职责（只做能自动化的那一层，绝不伪造日期）：
  1. 对每个品种，从东方财富 push2delay 拉取该交易所全部合约；
  2. 过滤出本品种的真实月份合约，重建「期限结构 term」区块
     （labels / settle / close / main_idx / vmin / vmax / rows）；
  3. 把新 term 合并回现有品种 JSON，**原样保留** inv / basis / drivers /
     data_date（基本面人工整理日）/ cost / profit 等字段；
  4. 写入新的 term_date = 今日（行情/期限结构自动刷新日），
     与 data_date（基本面人工整理日）严格区分，避免误导。

不自动更新的字段（必须人工维护，保持诚实）：
  - inv.warrant / inv.industrial（仓单、工业库存）
  - basis（基差曲线）
  - drivers（多空驱动 / 观点）
  - data_date（这些字段的所属日，不因行情刷新而变）

用法：
  python3 refresh_fundamentals.py            # 刷新全部品种
  python3 refresh_fundamentals.py AU AG       # 只刷指定品种
  python3 refresh_fundamentals.py --push     # 刷新 + 调用 sync_to_site 推 GitHub
"""
import json, os, re, sys, glob, time, urllib.request, urllib.parse, ssl
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(SCRIPT_DIR, "index.html")
TODAY = datetime.now().strftime("%Y-%m-%d")

# 交易所 → 东方财富市场代码（与 期货行情服务.py 一致）
EXCHANGE_MKT = {
    "上期所": "m:113",
    "大商所": "m:114",
    "郑商所": "m:115",
    "中金所": "m:220",
    "广期所": "m:225",
    "能源中心": "m:142",
}

EM_HOSTS = [
    "https://push2delay.eastmoney.com",
    "https://push2.eastmoney.com",
    "https://82.push2.eastmoney.com",
    "https://48.push2.eastmoney.com",
    "https://push2his.eastmoney.com",
]

# 交易所覆盖：COMMODITIES 里个别品种标错了实际挂牌交易所，抓取时按此表纠正。
# 原油(SC)、20号胶(NR) 实际在 上海国际能源交易中心(INE, m:142)，模板里误标为「上期所」。
CODE_EXCHANGE_OVERRIDE = {
    "SC": "能源中心",
    "NR": "能源中心",
}

# 2026-09-18 22:35 起：数据唯一真源（桌面/下载不再保留拷贝或软链接）
DATA_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "期货服务", "期货研究数据")
SEARCH_DIRS = [
    DATA_DIR,
    SCRIPT_DIR,
]

# ---------- 工具 ----------
def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def _price_of(r):
    v = _num(r.get("f43"))       # 结算价优先
    if v is not None:
        return v
    return _num(r.get("f2"))     # 延迟源常只在 f2 给最新价

def _contract_ym(full):
    digits = ""
    for ch in reversed(str(full)):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    if len(digits) >= 4:
        return f"20{int(digits[:2]):02d}-{digits[2:4]}"
    if len(digits) == 3:
        cur = datetime.now().year
        base = (cur // 10) * 10
        year = base + int(digits[0])
        if year < cur - 5:
            year += 10
        return f"{year}-{digits[1:3]}"
    return "—"

# ---------- 读取品种表 ----------
def load_commodities():
    try:
        h = open(HTML_PATH, encoding="utf-8").read()
        i = h.find("const COMMODITIES")
        if i < 0:
            return []
        j = h.find("[", i)
        depth, end = 0, None
        for k in range(j, len(h)):
            if h[k] == "[":
                depth += 1
            elif h[k] == "]":
                depth -= 1
                if depth == 0:
                    end = k
                    break
        if end is not None:
            return json.loads(h[j:end + 1])
    except Exception as e:
        print("读取 COMMODITIES 失败:", e)
    return []

# ---------- 抓取单个交易所全部合约 ----------
def _fetch_market(mkt, fields, max_pages=6):
    ctx = ssl.create_default_context()
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    handlers = []
    if proxy:
        from urllib.request import ProxyHandler
        handlers.append(ProxyHandler({"http": proxy, "https": proxy}))
    # 必须统一用 build_opener 返回的 opener 对象：直连时若直接用 urllib.request 模块，
    # `urllib.request.open` 并不存在（只有 urlopen/urlretrieve），会导致全部品种抓取静默失败。
    opener = urllib.request.build_opener(*handlers)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://quote.eastmoney.com/",
    }
    out = []
    for page in range(1, max_pages + 1):
        url = (f"{'HOST'}/api/qt/clist/get?po=1&np=1&fltt=2&invt=2&fid=f12&fs="
               + urllib.parse.quote(mkt) + "&fields=" + fields
               + f"&pn={page}&pz=100&_={int(time.time()*1000)}")
        last_err = None
        for host in EM_HOSTS:
            try:
                req = urllib.request.Request(url.replace("HOST", host), headers=headers)
                with opener.open(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                d = data.get("data") or {}
                raw = d.get("diff") or d.get("list")
                if raw is None:
                    continue
                part = list(raw.values()) if isinstance(raw, dict) else list(raw)
                out.extend(part)
                if len(part) < 100:
                    return out
                break
            except Exception as e:
                last_err = e
                continue
        else:
            if last_err:
                print(f"  ⚠ 交易所 {mkt} 第{page}页抓取失败: {last_err}")
            break
    return out

def _build_term(code, ex, items):
    """从交易所全量合约中筛出本品种，重建 term 区块。"""
    rows_all = [
        r for r in items
        if r.get("f12") and str(r["f12"]).upper().startswith(code.upper())
        and str(r["f12"])[-1].isdigit() and _price_of(r) is not None
    ]
    if not rows_all:
        return None
    rows_all.sort(key=lambda r: str(r["f12"]))
    labels, settle, close, table = [], [], [], []
    for it in rows_all:
        full = str(it["f12"])
        px = _price_of(it)
        labels.append(full)
        settle.append(px)
        close.append(px)
        chg = _num(it.get("f170"))
        if chg is None:
            chg = _num(it.get("f3"))
        chg_str = (("+" if chg >= 0 else "") + f"{chg:.2f}%") if chg is not None else "—"
        vol = _num(it.get("f5")) or 0
        oi_str = f"{int(vol):,}" if vol else "—"
        table.append([full, _contract_ym(full), px, px, oi_str, chg_str])
    # 主力 = 成交量最大
    best = max(range(len(rows_all)), key=lambda i: (_num(rows_all[i].get("f5")) or 0))
    mn, mx = min(settle), max(settle)
    pad = (mx - mn) * 0.15 or (mn * 0.02 or 1)
    return {
        "labels": labels,
        "settle": settle,
        "close": close,
        "main_idx": best,
        "vmin": round(mn - pad, 2),
        "vmax": round(mx + pad, 2),
        "rows": table,
    }

# ---------- 读写品种 JSON ----------
def find_file(code):
    """按文件内 code 字段匹配（比文件名前缀正则稳健，避免 TA/VPVC 这类「代码后紧跟字母」误判）。"""
    code = code.upper()
    for d in SEARCH_DIRS:
        if not os.path.isdir(d):
            continue
        for path in sorted(glob.glob(os.path.join(d, "*_库存基差期限结构*.json"))):
            try:
                j = json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
            if (j.get("code") or "").upper() == code:
                return path
    return None

def target_dirs():
    """单一真源：只写 DATA_DIR 一处（2026-09-18 22:35）。"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        return [SCRIPT_DIR]
    return [DATA_DIR]

def _safe_name(s):
    return re.sub(r'[/\\\?%\*:\|"<>\x00-\x1f]', '', str(s or '')).strip()

BAK_SUBDIR = "_bak"


def backup_one(fp):
    """把现有品种 JSON 快照到同目录的 _bak/ 子目录，滚动只保留最近 1 份。

    为什么不沿用 `xxx.json.bak_<时间戳>`：那样备份会撒在主数据目录里无限堆积
    （2026-09-18 清理过 153 份存量）。集中到 _bak/ + 滚动保留 → 主目录始终干净，
    每个品种仍留一步回滚点。"""
    bak_dir = os.path.join(os.path.dirname(fp), BAK_SUBDIR)
    try:
        os.makedirs(bak_dir, exist_ok=True)
    except OSError:
        return None
    stem = os.path.basename(fp)
    for old in glob.glob(os.path.join(bak_dir, stem + ".bak_*")):
        try:
            os.remove(old)
        except OSError:
            pass
    dst = os.path.join(bak_dir, f"{stem}.bak_{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    try:
        os.replace(fp, dst)
    except OSError:
        return None
    return dst


def save_variety(code, name, data):
    fname = f"{code}{_safe_name(name)}_库存基差期限结构.json"
    written = []
    for d in target_dirs():
        fp = os.path.join(d, fname)
        # 备份进 _bak/（滚动只留最近 1 份），主目录不再产生 .bak_ 文件
        if os.path.exists(fp):
            backup_one(fp)
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        written.append(fp)
    return written

# ---------- 主流程 ----------
def refresh_one(code, name, ex):
    ex = CODE_EXCHANGE_OVERRIDE.get(code.upper(), ex)
    mkt = EXCHANGE_MKT.get(ex)
    if not mkt:
        return (code, "skip", f"不支持的交易所 {ex}")
    fields = "f12,f14,f43,f2,f3,f5,f170"
    items = _fetch_market(mkt, fields)
    term = _build_term(code, ex, items)
    if term is None:
        return (code, "skip", f"东财未返回 {code} 合约")
    # 合并回现有文件（保留 inv/basis/drivers/data_date）
    fp = find_file(code)
    if fp:
        with open(fp, encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj = {"code": code, "name": name, "exchange": ex, "data_date": ""}
    n_old = len((obj.get("term") or {}).get("labels") or [])
    obj["term"] = term
    obj["term_date"] = TODAY
    obj["exchange"] = ex
    if name:
        obj["name"] = name
    save_variety(code, name or obj.get("name", ""), obj)
    return (code, "ok", f"合约 {n_old}→{len(term['labels'])}，已写 term_date={TODAY}")

def main():
    args = sys.argv[1:]
    do_push = "--push" in args
    codes = [a for a in args if not a.startswith("--")]
    comms = load_commodities()
    if not comms:
        print("无法读取品种表，退出")
        return
    if codes:
        sel = {c[0].upper(): c for c in comms if c[0].upper() in [x.upper() for x in codes]}
    else:
        sel = {c[0].upper(): c for c in comms}
    print(f"=== 刷新 {len(sel)} 个品种期限结构（{TODAY}）===")
    ok = skip = 0
    for c in comms:
        if c[0].upper() not in sel:
            continue
        code, name, ex = c[0], c[1], c[2]
        try:
            res = refresh_one(code, name, ex)
        except Exception as e:
            res = (code, "skip", f"异常: {e}")
        flag = "✓" if res[1] == "ok" else "·"
        if res[1] == "ok":
            ok += 1
        else:
            skip += 1
        print(f"  {flag} {code} {name}: {res[2]}")
    print(f"=== 完成：成功 {ok} / 跳过 {skip} ===")
    if do_push:
        print("--- 调用 sync_to_site 推 GitHub ---")
        os.system(f'{sys.executable} "{os.path.join(SCRIPT_DIR, "sync_to_site.py")}" --push')

if __name__ == "__main__":
    main()
