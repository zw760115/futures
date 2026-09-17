#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_warrant.py — 自动抓取四大交易所仓单日报 → 解析 → 输出 data/warrant.json

数据源（均为交易所官网每日收盘后发布的免费公开数据）:
  - 郑商所 CZCE : AkShare futures_warehouse_receipt_czce  (经官网 cdrb 页面)
  - 大商所 DCE  : 官网 JSON 接口 wbillWeeklyQuotes (POST)
  - 广期所 GFEX : 官网 JSON 接口 interfacesWebTdWbillWeeklyQuotes/loadList (POST)
  - 上期所 SHFE : 旧 .dat 接口已废弃(对2026返回404)，改用东方财富库存接口兜底拿总量+增减

输出: data/warrant.json
  {
    "data_date": "20260916",
    "generated_at": "ISO时间",
    "warrant": {
      "AU": {"exchange":"上期所","total":123,"delta":-5,"unit":"张","items":[{"name":"中工美","value":88}],"source":"eastmoney"},
      ...
    }
  }

说明:
  - 每个交易所独立 try/except，单所失败不影响其它所
  - 自动回溯交易日：若指定日期无数据，向前回溯最多 7 个自然日找最近有数据的交易日
  - 仅输出模板中存在(excl. 非标准)的品种代码；其余忽略
"""

import os
import sys
import json
import datetime as dt
import requests
import pandas as pd

try:
    import akshare as ak
except Exception as e:
    ak = None
    print("[WARN] akshare 未安装，郑商所/上期所(东方财富兜底)将无法抓取:", e, file=sys.stderr)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "warrant.json")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# ---- 模板中存在的品种代码(取自 index.html DATA 键) ----
TEMPLATE_CODES = {
    "AU", "AG", "AL", "AO", "AP", "BR", "BU", "C", "CF", "CJ", "CS", "CU", "CY",
    "EB", "EG", "FG", "HC", "I", "J", "JD", "JM", "JR", "L", "LC", "LH", "LR",
    "M", "MA", "NI", "NR", "OI", "P", "PB", "PF", "PK", "PM", "PP", "PS", "PX",
    "RB", "RI", "RM", "RR", "RS", "SA", "SF", "SI", "SM", "SN", "SP", "SR",
    "SS", "TA", "UR", "V", "WH", "Y", "ZN", "B", "A",
}

# 大商所: 中文品种名 -> 模板代码
DCE_NAME2CODE = {
    "豆一": "A", "豆二": "B", "豆粕": "M", "豆油": "Y", "棕榈油": "P",
    "玉米": "C", "玉米淀粉": "CS", "粳米": "RR", "鸡蛋": "JD", "生猪": "LH",
    "焦煤": "JM", "焦炭": "J", "铁矿石": "I", "聚乙烯": "L", "聚氯乙烯": "V",
    "聚丙烯": "PP", "乙二醇": "EG", "苯乙烯": "EB", "原木": "LG",
}

# 上期所: 模板代码 -> 东方财富中文名(库存接口兜底用)
SHFE_CODE2CN = {
    "AU": "沪金", "AG": "沪银", "CU": "沪铜", "AL": "沪铝", "AO": "氧化铝",
    "NI": "镍", "SN": "锡", "ZN": "沪锌", "PB": "沪铅", "RB": "螺纹钢",
    "HC": "热卷", "BU": "沥青", "NR": "20号胶", "BR": "丁二烯橡胶",
    "SS": "不锈钢", "SP": "纸浆",
}

# 广期所代码(小写->大写, 与模板一致)
GFEX_CODES = {"SI", "LC", "PS"}

# 各品种合约乘数(吨/手 或 吨/张, 与交易所一致); 用于把"张/手"换算成"万吨"显示
TON_PER_LOT = {
    # 上期所
    "AU": 0.001, "AG": 0.015, "CU": 5, "AL": 5, "AO": 20, "NI": 1, "SN": 1,
    "ZN": 5, "PB": 5, "RB": 10, "HC": 10, "BU": 10, "NR": 10, "BR": 5,
    "SS": 5, "SP": 10,
    # 郑商所
    "SR": 10, "CF": 5, "CY": 5, "TA": 5, "MA": 10, "FG": 20, "SA": 20, "UR": 20,
    "RM": 10, "OI": 10, "PK": 5, "AP": 10, "CJ": 5, "SF": 5, "SM": 5, "WH": 20,
    "JR": 20, "LR": 20, "RI": 20, "RS": 10, "PM": 50, "PF": 5,
    # 大商所
    "A": 10, "B": 10, "M": 10, "Y": 10, "P": 10, "C": 10, "CS": 10, "RR": 10,
    "JD": 5, "LH": 16, "JM": 60, "J": 100, "I": 100, "L": 5, "V": 5, "PP": 5,
    "EG": 10, "EB": 5, "LG": 90,
    # 广期所
    "SI": 5, "LC": 1, "PS": 3,
}
DEFAULT_TON = 10  # 未知品种按 10 吨/手估算


def _wan(total, code):
    """把 张/手 换算成 万吨(保留4位)"""
    return round(total * TON_PER_LOT.get(code, DEFAULT_TON) / 10000.0, 4)


def _to_int(x):
    try:
        if pd.isna(x):
            return 0
        s = str(x).replace(",", "").strip()
        if s in ("", "nan", "NaN"):
            return 0
        return int(float(s))
    except Exception:
        return 0


def backdate(start: str, days=7):
    """从 start(YYYYMMDD) 向前回溯, 生成候选交易日列表"""
    d = dt.datetime.strptime(start, "%Y%m%d")
    out = []
    for i in range(days):
        out.append(d.strftime("%Y%m%d"))
        d -= dt.timedelta(days=1)
    return out


# ---------------- 各交易所抓取 ----------------
def fetch_czce(date):
    """郑商所: 各品种列名不统一, 做健壮字段解析"""
    if ak is None:
        return {}
    d = ak.futures_warehouse_receipt_czce(date=date)
    out = {}
    for code, df in d.items():
        code = str(code).upper()
        if code not in TEMPLATE_CODES:
            continue
        name_col = next((c for c in ["仓库简称", "厂库简称", "机构简称"] if c in df.columns), None)
        qty_cols = [c for c in ["仓单数量", "仓单数量(完税)", "仓单数量(保税)", "确认书数量", "预报数量"] if c in df.columns]
        delta_col = "当日增减" if "当日增减" in df.columns else None
        if not name_col or not qty_cols:
            continue

        def qty_of(r):
            return sum(_to_int(r[c]) for c in qty_cols)

        items, total, delta = [], 0, 0
        for _, r in df.iterrows():
            nm = str(r[name_col]).strip()
            q = qty_of(r)
            dl = _to_int(r[delta_col]) if delta_col else 0
            if nm in ("总计", "小计") or nm in ("", "nan", "NaN"):
                if nm == "总计":
                    total, delta = q, dl
            else:
                if q > 0:
                    items.append({"name": nm, "value": q})
                total = total  # 占位, 下面兜底
        if total == 0:  # 无总计行(如 WH/AP), 用明细求和
            total = sum(it["value"] for it in items)
            delta = sum(_to_int(r[delta_col]) for _, r in df.iterrows() if delta_col and str(r[name_col]).strip() not in ("总计", "小计")) if delta_col else 0
        out[code] = {"exchange": "郑商所", "total": total, "delta": delta,
                     "unit": "张", "total2": _wan(total, code),
                     "items": items, "source": "czce"}
    return out


def fetch_dce(date):
    url = "http://www.dce.com.cn/dcereport/publicweb/dailystat/wbillWeeklyQuotes"
    r = requests.post(url, json={"tradeDate": date, "varietyId": "all"},
                     headers=UA, timeout=30)
    data = r.json().get("data", {}).get("entityList", [])
    if not data:
        return {}
    df = pd.DataFrame(data)
    out = {}
    for name, g in df.groupby("variety"):
        code = DCE_NAME2CODE.get(str(name).strip())
        if not code:
            continue
        g = g.fillna({"wbillQty": 0, "diff": 0})
        total = _to_int(g["wbillQty"].sum())
        delta = _to_int(g["diff"].sum())
        items = [
            {"name": str(r["whAbbr"]), "value": _to_int(r["wbillQty"])}
            for _, r in g.iterrows()
            if str(r.get("whAbbr", "")).strip() not in ("小计", "总计")
            and _to_int(r["wbillQty"]) > 0
        ]
        out[code] = {"exchange": "大商所", "total": total, "delta": delta,
                     "unit": "手", "total2": _wan(total, code),
                     "items": items, "source": "dce"}
    return out


def fetch_gfex(date):
    url = "http://www.gfex.com.cn/u/interfacesWebTdWbillWeeklyQuotes/loadList"
    r = requests.post(url, data={"gen_date": date}, headers=UA, timeout=30)
    data = r.json().get("data", [])
    if not data:
        return {}
    df = pd.DataFrame(data)
    out = {}
    for code, g in df.groupby(df["varietyOrder"].astype(str).str.upper()):
        code = str(code).upper()
        if not code or code not in TEMPLATE_CODES:  # 跳过空(总计)行
            continue
        g = g.fillna({"wbillQty": 0, "diff": 0})
        total = _to_int(g["wbillQty"].sum())
        delta = _to_int(g["diff"].sum())
        items = [
            {"name": str(r["whAbbr"]), "value": _to_int(r["wbillQty"])}
            for _, r in g.iterrows()
            if _to_int(r["wbillQty"]) > 0
        ]
        out[code] = {"exchange": "广期所", "total": total, "delta": delta,
                     "unit": "手", "total2": _wan(total, code),
                     "items": items, "source": "gfex"}
    return out


# 东方财富库存接口的品种中文名映射(官方接口失败时兜底; 东财覆盖全部市场)
DCE_CODE2CN = {
    "A": "豆一", "B": "豆二", "M": "豆粕", "Y": "豆油", "C": "玉米", "CS": "玉米淀粉",
    "P": "棕榈", "L": "塑料", "V": "PVC", "PP": "聚丙烯", "EG": "乙二醇", "EB": "苯乙烯",
    "J": "焦炭", "JM": "焦煤", "I": "铁矿石", "JD": "鸡蛋", "LH": "生猪",
    "PG": "液化石油气", "RR": "粳米", "BZ": "纯苯",
}


def fetch_em_inventory(date, codes_map, exchange_cn, tag):
    """通用东方财富库存兜底(仅总量+增减, 无分仓库)。codes_map: 模板代码->东财中文名"""
    if ak is None:
        return {}
    out = {}
    for code, cn in codes_map.items():
        try:
            df = ak.futures_inventory_em(symbol=cn)
            if df is None or len(df) == 0:
                continue
            df = df.copy()
            df["日期"] = df["日期"].astype(str)
            row = df[df["日期"] == date]
            if len(row) == 0:
                row = df.iloc[[-1]]
            r = row.iloc[0]
            out[code] = {
                "exchange": exchange_cn,
                "total": _to_int(r["库存"]),
                "delta": _to_int(r["增减"]),
                "unit": "张" if exchange_cn == "上期所" else "手",
                "total2": _wan(_to_int(r["库存"]), code),
                "items": [],
                "source": "eastmoney",
            }
        except Exception as e:
            print(f"  [{tag}/{code}] 东方财富兜底失败: {e}", file=sys.stderr)
    return out


def fetch_shfe_em(date):
    """上期所: 旧接口废弃, 用东方财富库存接口兜底(仅总量+增减, 无分仓库)"""
    return fetch_em_inventory(date, SHFE_CODE2CN, "上期所", "SHFE")


def fetch_dce_em(date):
    """大商所: 官方接口被反爬(412)或失败时, 用东方财富库存接口兜底"""
    return fetch_em_inventory(date, DCE_CODE2CN, "大商所", "DCE")


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().strftime("%Y%m%d")
    print(f"目标日期: {start}  每个交易所独立回溯最多7天找各自最近交易日...")

    warrant = {}
    dates_used = {}   # exchange -> 该所最近有数据的日期

    # 每所独立回溯：某所当日无数据(如17:30前日报未发布)时, 该所自己退一天, 不拖累其它所
    # 每条: (标签, 中文名, 官方抓取函数, 东财兜底函数)
    fetchers = [
        ("CZCE", "郑商所", fetch_czce, None),
        ("DCE",  "大商所", fetch_dce, fetch_dce_em),
        ("GFEX", "广期所", fetch_gfex, None),
        ("SHFE", "上期所", fetch_shfe_em, None),
    ]
    for tag, cn, fn, fallback in fetchers:
        got = {}
        for date in backdate(start, 7):
            print(f"\n--- [{tag}] 试 {date} ---")
            try:
                got = fn(date)
            except Exception as e:
                got = {}
                print(f"  [{tag}] 失败: {e}", file=sys.stderr)
            if not got and fallback is not None:
                try:
                    got = fallback(date)
                    if got:
                        print(f"  [{tag}] 官方接口无数据, 已用东方财富兜底")
                except Exception as e:
                    print(f"  [{tag}] 兜底也失败: {e}", file=sys.stderr)
            if got:
                dates_used[cn] = date
                warrant.update(got)
                print(f"  [{tag}] {date} 成功: {len(got)} 个品种")
                break
        if not got:
            print(f"[WARN] {cn} 近7天均无数据, 本次跳过", file=sys.stderr)

    if not warrant:
        print("[ERROR] 近7天均无交易所数据, 未输出", file=sys.stderr)
        sys.exit(2)

    used_date = max(dates_used.values())

    result = {
        "data_date": used_date,
        "exchange_dates": dates_used,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "warrant": warrant,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入 {OUT}")
    print(f"   数据日期: {used_date}  覆盖品种数: {len(warrant)}")
    for cn, d in dates_used.items():
        n = sum(1 for v in warrant.values() if v["exchange"] == cn)
        print(f"   - {cn}: {n} 个品种 (数据日期 {d})")
    # 打印样例
    for code in list(warrant)[:6]:
        w = warrant[code]
        print(f"   {code}: 总量={w['total']}{w['unit']} 增减={w['delta']} 分仓库={len(w['items'])}条 src={w['source']}")


if __name__ == "__main__":
    main()
