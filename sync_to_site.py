#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌面期货研究数据 → GitHub Pages 网站 同步桥接器
================================================
用途：把桌面/下载两份研究数据同步成网站的远程种子，并（可选）推送到 GitHub，
      让网页版打开即最新。

产出（三件事）：
  1. data/patch.json              ← ~/Desktop/期货研究数据/*.json 全字段合并
  2. data/profit_snapshot.json    ← 产业利润快照.json 的网站副本
     （index.html 的 loadProfitSnapshot() 会先读本地服务 /api/profit_snapshot，
       线上版读不到本地服务时回退读同源 data/profit_snapshot.json，
       所以这份副本是「利润参考库」能在网页版生效的通道）
  3. data/moneyflow.json          ← 资金流向快照.json 的网站副本
     （index.html 的 loadMoneyFlow() 先读本地服务 /api/moneyflow，
       线上版回退读同源 data/moneyflow.json，通道同上）

用法：
  python3 sync_to_site.py              # 仅生成上述两份文件（不推送）
  python3 sync_to_site.py --push       # 生成并 git push（自动用 ~/bin/gh 的 token）

注意：
  - 利润/成本(quad) 不在桌面 JSON 里（是网页手工填的），脚本会保留
    旧 patch.json 中的 quad，不会被基本面数据冲掉。
  - 每个品种取桌面文件夹里 mtime 最新的那份（兼容带日期后缀的副本）。
  - 推送顺序：直连（清掉继承的代理变量）→ 直连 HTTP/1.1 → 自动探测到的本地代理
    （macOS 系统代理 / FlClash 混合端口 7890 等）。
  - 产业利润快照取 Desktop 与 Downloads 两份中 mtime 最新的一份。
"""
import os, re, sys, json, glob, time, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import notify  # 失败告警 + 更新状态（notify.py 同目录，写入 ~/Desktop/期货研究数据/快照更新状态.json）

REPO = os.path.dirname(os.path.abspath(__file__))
UPD_OUT = os.path.join(REPO, 'data', 'update_status.json')
DESK_DIR = os.path.expanduser('~/Desktop/期货研究数据')
DL_DIR = os.path.expanduser('~/Downloads/期货研究数据')
PATCH_PATH = os.path.join(REPO, 'data', 'patch.json')
SNAP_OUT = os.path.join(REPO, 'data', 'profit_snapshot.json')
SNAP_NAME = '产业利润快照.json'
MF_OUT = os.path.join(REPO, 'data', 'moneyflow.json')
MF_SNAP_NAME = '资金流向快照.json'

# 模板内嵌的全部品种 CODE（与 index.html DATA 顶层键一致）
CODES = set("""A AG AL AP AU B BB BR BU C CF CJ CS CU CY EB EG FB FG FU HC I J JD
JM JR L LC LH LR M MA NI NR OI P PB PF PK PM PP PS PT RB RI RM RR RS RU SA SC
SF SH SI SM SN SP SR SS TA UR V WH WR Y ZC ZN""".split())

SUFFIX = '_库存基差期限结构'

def code_from_filename(fn):
    """A豆一_库存基差期限结构.json -> A ; AG白银_库存基差期限结构_20260914.json -> AG"""
    base = fn[:-5] if fn.lower().endswith('.json') else fn
    if base.endswith(SUFFIX):
        base = base[:-len(SUFFIX)]
    base = re.sub(r'_\d{8}$', '', base)          # 去日期后缀
    m = re.match(r'^([A-Za-z]+)', base)
    if not m:
        return None
    cand = m.group(1)
    return cand if cand in CODES else None

def scan_desk():
    """返回 {code: (mtime, data, fn)}，每个 code 取最新文件"""
    latest = {}
    for fp in glob.glob(os.path.join(DESK_DIR, '*.json')):
        fn = os.path.basename(fp)
        try:
            data = json.load(open(fp, encoding='utf-8'))
        except Exception as e:
            print(f'  ⚠ 跳过 {fn}（解析失败: {e}）')
            continue
        # 优先用 JSON 内部的 code 字段（权威）；文件名解析仅作兜底
        code = (data.get('code') if isinstance(data, dict) else None) or code_from_filename(fn)
        if not code or code not in CODES:
            continue
        mt = os.path.getmtime(fp)
        if code not in latest or mt > latest[code][0]:
            latest[code] = (mt, data, fn)
    return latest

def export_profit_snapshot():
    """把 产业利润快照.json 复制为网站同源副本 data/profit_snapshot.json（取最新一份）"""
    cands = [os.path.join(d, SNAP_NAME) for d in (DESK_DIR, DL_DIR)]
    cands = [p for p in cands if os.path.isfile(p)]
    if not cands:
        print(f'  ⚠ 未找到 {SNAP_NAME}（桌面/下载的 期货研究数据 里都没有），跳过利润快照副本')
        return False
    src = max(cands, key=os.path.getmtime)
    try:
        snap = json.load(open(src, encoding='utf-8'))
    except Exception as e:
        print(f'  ⚠ 快照解析失败（{src}）: {e}，跳过')
        return False
    os.makedirs(os.path.dirname(SNAP_OUT), exist_ok=True)
    with open(SNAP_OUT, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'✓ 已生成 data/profit_snapshot.json（源：{src}；asof {snap.get("asof")}，{len(snap.get("data", {}))} 个品种）')
    return True

def export_moneyflow_snapshot():
    """把 资金流向快照.json 复制为网站同源副本 data/moneyflow.json（取最新一份）。
    index.html 的 loadMoneyFlow() 先读本地服务 /api/moneyflow，线上读不到本地服务时
    回退读同源 data/moneyflow.json —— 这份副本是「💰 当日资金流向」能在网页版生效的通道。"""
    cands = [os.path.join(d, MF_SNAP_NAME) for d in (DESK_DIR, DL_DIR)]
    cands = [p for p in cands if os.path.isfile(p)]
    if not cands:
        print(f'  ⚠ 未找到 {MF_SNAP_NAME}（先用本地服务打开一次模板即会自动生成），跳过资金流向副本')
        return False
    src = max(cands, key=os.path.getmtime)
    try:
        snap = json.load(open(src, encoding='utf-8'))
    except Exception as e:
        print(f'  ⚠ 资金流向快照解析失败（{src}）: {e}，跳过')
        return False
    rows = snap.get('rows') or []
    if not rows:
        print('  ⚠ 资金流向快照 rows 为空，跳过')
        return False
    os.makedirs(os.path.dirname(MF_OUT), exist_ok=True)
    with open(MF_OUT, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'✓ 已生成 data/moneyflow.json（源：{src}；asof {snap.get("asof")}，{len(rows)} 个品种）')
    return True

def export_update_status():
    """把 ~/Desktop/期货研究数据/快照更新状态.json 复制为网站同源副本 data/update_status.json，
    网页版据此显示「资金流向 / 网页同步」是否更新成功（失败含原因）。"""
    if not os.path.isfile(notify.STATUS_PATH):
        return False
    try:
        data = json.load(open(notify.STATUS_PATH, encoding='utf-8'))
    except Exception as e:
        print(f'  ⚠ 更新状态文件解析失败：{e}，跳过')
        return False
    os.makedirs(os.path.dirname(UPD_OUT), exist_ok=True)
    with open(UPD_OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('✓ 已生成 data/update_status.json（资金流向/同步更新状态）')
    return True

def _gh_token():
    """取 GitHub token：优先 PATH 里的 gh，其次 ~/bin/gh（双击/定时任务环境 PATH 可能很窄）"""
    gh = shutil.which('gh') or os.path.expanduser('~/bin/gh')
    if not os.path.isfile(gh) and not shutil.which('gh'):
        print('✗ 未找到 gh 可执行文件')
        return None
    r = subprocess.run([gh, 'auth', 'token'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None

PROXY_ENV_KEYS = ('http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY')

def _clean_env(proxy=None):
    """基于干净环境构造子进程 env：先剔除继承来的代理变量（沙箱/IDE 可能注入一个连不通的代理，
    会让 git 直连 GitHub 报 'CONNECT tunnel failed, response 502'），再按需设置指定代理。"""
    e = dict(os.environ)
    for k in PROXY_ENV_KEYS:
        e.pop(k, None)
    if proxy:
        for k in PROXY_ENV_KEYS[:3] + PROXY_ENV_KEYS[3:6]:
            e[k] = proxy
    return e

def _detect_proxies():
    """本地可用代理候选：先读 macOS 系统代理（FlClash 开启时会写 127.0.0.1:7890），
    再补常见混合端口，最后只保留真的能建连的。"""
    cands = []
    try:
        r = subprocess.run(['scutil', '--proxy'], capture_output=True, text=True)
        ip = re.search(r'HTTPProxy\s*:\s*(\S+)', r.stdout)
        port = re.search(r'HTTPPort\s*:\s*(\d+)', r.stdout)
        if ip and port:
            cands.append(f'http://{ip.group(1)}:{port.group(1)}')
    except Exception:
        pass
    for p in (7890, 7891, 7897, 10809, 10808, 1080):
        u = f'http://127.0.0.1:{p}'
        if u not in cands:
            cands.append(u)
    ok = []
    for u in cands:
        host, port = u.replace('http://', '').split(':')
        try:
            import socket
            with socket.create_connection((host, int(port)), timeout=0.8):
                ok.append(u)
        except Exception:
            pass
    return ok

PUSH_TIMEOUT = 90          # 单条通道最长等待（秒）——超时即换下一条，避免整体卡死
GITHUB_HOST, GITHUB_PORT = 'github.com', 443

def _tcp_reachable(host=GITHUB_HOST, port=GITHUB_PORT, timeout=3.0):
    """timeout 秒内能否与 github.com:443 建立 TCP 连接。
    国内直连被墙时 SYN 会一直挂着（SYN_SENT），没有这一步就会在「直连」上白等几分钟，
    永远走不到后面的代理兜底 —— 这是脚本卡在「同步并推送」的根因。"""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def _proxy_reaches_github(u, timeout=4.0):
    """代理端口开着 ≠ 能出去：用 HTTP CONNECT 探一下能否到达 github.com:443。
    （沙箱/IDE 常注入一个「开着但连不通」的代理端口，这一步能把它提前筛掉）"""
    import socket
    try:
        host, port = u.replace('http://', '').split(':')
        s = socket.create_connection((host, int(port)), timeout=timeout)
        s.sendall(b'CONNECT github.com:443 HTTP/1.1\r\nHost: github.com:443\r\n\r\n')
        s.settimeout(timeout)
        head = s.recv(64).split(b'\r\n')[0]
        s.close()
        return b' 200' in head
    except Exception:
        return False

def _try_push(token, cfg, env, label):
    """用临时 credential.helper 供上 token（token 走环境变量，不进 argv、不留盘）。
    带硬超时：超时后连本通道的 git-remote-https 一起杀掉（否则会留一堆僵尸进程）。"""
    e = dict(env)
    e['GH_TOKEN'] = token
    e['GIT_TERMINAL_PROMPT'] = '0'
    cmd = (['git'] + cfg
           + ['-c', 'credential.helper=',                                   # 先清掉继承的 osxkeychain
              '-c', 'credential.helper=!f(){ echo username=x; echo password=$GH_TOKEN; };f',
              '-c', 'http.lowSpeedLimit=1000', '-c', 'http.lowSpeedTime=20',  # 传输停滞 20s 即放弃
              'push', 'origin', 'main'])
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=e, start_new_session=True)
    except Exception as ex:
        print(f'  ✗ {label} 无法执行：{ex}')
        return False
    try:
        out, err = p.communicate(timeout=PUSH_TIMEOUT)
    except subprocess.TimeoutExpired:
        import signal
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)   # 连子进程 git-remote-https 一起收掉
        except Exception:
            p.kill()
        try:
            p.communicate(timeout=5)
        except Exception:
            pass
        print(f'  ✗ {label} 超时（{PUSH_TIMEOUT}s 未完成），换下一个通道')
        return False
    if p.returncode == 0:
        print(f'  ✓ 推送成功（{label}）')
        return True
    tail = (err or out or '').strip().splitlines()
    print(f'  ✗ {label} 失败：{tail[-1] if tail else "未知错误"}')
    return False

def _clear_stale_lock():
    """清理僵尸 .git/index.lock。
    判定依据：没有任何 git 进程在跑（pgrep 无结果）→ 锁一定是僵尸，直接删。
    （编辑器、被中断的提交、或把仓库放在被同步/索引的目录里，都会留下空锁，
      后续所有 git 命令会以 128「File exists」失败）"""
    lock = os.path.join(REPO, '.git', 'index.lock')
    if not os.path.exists(lock):
        return
    if subprocess.run(['pgrep', '-x', 'git'], capture_output=True).returncode == 0:
        print('  ⚠ 检测到 git 进程在运行，保留 index.lock 不动')
        return
    try:
        age = time.time() - os.path.getmtime(lock)
        os.remove(lock)
        print(f'  ⚠ 清理了僵尸 .git/index.lock（无 git 进程占用，已存在 {age:.0f}s）')
    except Exception as e:
        print(f'  ⚠ 无法删除 .git/index.lock：{e}')

def _git(*args, **kw):
    """执行 git 命令；失败且原因是 index.lock 时，清锁重试一次。"""
    for attempt in (1, 2):
        _clear_stale_lock()
        r = subprocess.run(['git'] + list(args), capture_output=True, text=True)
        if r.returncode == 0:
            return r
        if attempt == 1 and 'index.lock' in (r.stderr or ''):
            print('  ⚠ git 报 index.lock 冲突，清锁重试…')
            continue
        break
    if kw.get('check', True):
        raise subprocess.CalledProcessError(r.returncode, ['git'] + list(args), r.stdout, r.stderr)
    return r

def sync_embedded_profit_ref():
    """把线上利润快照（data/profit_snapshot.json）回写进 index.html 内嵌的 PROFIT_REF。
    为什么：PROFIT_REF 是「利润档位」的唯一来源，而它由【页面内嵌】+【线上快照】两处叠加。
    各端网络/缓存状况不同（微信常取不到快照）→ 退回内嵌旧默认值 → 同一品种利润档不同
    → 高阶分值排行各端不一致。把内嵌值与线上快照对齐后，任何设备无论能否联网都算同一份。
    实现：在 PROFIT_REF 字面量后插入/更新一段带标记的 Object.assign 覆盖块（快照有值的品种才覆盖，
    内嵌独有的品种如 A 豆一保留原值）。"""
    html = os.path.join(REPO, 'index.html')
    snap_path = os.path.join(REPO, 'data', 'profit_snapshot.json')
    if not os.path.isfile(html) or not os.path.isfile(snap_path):
        print('  ⚠ 缺少 index.html 或 profit_snapshot.json，跳过内嵌利润同步')
        return False
    try:
        snap = json.load(open(snap_path, encoding='utf-8'))
    except Exception as e:
        print(f'  ⚠ 利润快照解析失败：{e}，跳过内嵌利润同步')
        return False
    data = snap.get('data') or {}
    over = {}
    for code, v in data.items():
        if isinstance(v, dict) and v.get('profit'):
            over[code] = {
                'profit': v.get('profit'),
                'cost': v.get('cost'),
                'asof': v.get('asof'),
                'src': v.get('src'),
                'note': v.get('note'),
            }
    if not over:
        print('  ⚠ 利润快照无可覆盖项，跳过内嵌利润同步')
        return False
    s = open(html, encoding='utf-8').read()
    block = ('/* === 内嵌利润参考自动同步（sync_to_site.py 生成，勿手改）=== */\n'
             '/* PROFIT_REF_SYNC_START */\n'
             'Object.assign(PROFIT_REF, ' + json.dumps(over, ensure_ascii=False) + ');\n'
             '/* PROFIT_REF_SYNC_END */')
    m = re.search(r'/\* PROFIT_REF_SYNC_START \*/.*?/\* PROFIT_REF_SYNC_END \*/', s, re.S)
    if m:
        s = s[:m.start()] + block + s[m.end():]
    else:
        i = s.find('const PROFIT_REF = {')
        if i < 0:
            print('  ⚠ 未找到 PROFIT_REF 定义，跳过内嵌利润同步')
            return False
        j = s.find('\n};', i)
        if j < 0:
            print('  ⚠ PROFIT_REF 定义未闭合，跳过内嵌利润同步')
            return False
        j += len('\n};')
        s = s[:j] + '\n\n' + block + s[j:]
    open(html, 'w', encoding='utf-8').write(s)
    print(f'✓ 内嵌利润参考已与线上快照对齐：覆盖 {len(over)} 个品种（asof {snap.get("asof")}）')
    return True


def bump_remote_v():
    """每次推送自动刷新 index.html 的 REMOTE_V。
    所有远程数据（patch/warrant/basis/profit）的 CDN 缓存键都带 ?v=REMOTE_V，
    把它刷成「年月日时分」时间戳 → 每次推送都让缓存键失效 → 各端（电脑/手机）
    拉到同一份最新数据，根除榜单因缓存时代不同而不一致的问题。
    注意：仅改变量不影响任何数据/渲染逻辑。"""
    html = os.path.join(REPO, 'index.html')
    if not os.path.isfile(html):
        return False
    s = open(html, encoding='utf-8').read()
    m = re.search(r"const REMOTE_V = '([^']+)';", s)
    if not m:
        return False
    old = m.group(1)
    base = time.strftime('%Y%m%d%H%M')        # 精确到分钟，每次推送必变
    if old.startswith(base):                  # 同分钟内多次推送 → 末尾加序号
        seq = re.search(r'\.(\d+)$', old)
        n = (int(seq.group(1)) + 1) if seq else 1
        new = old + '.' + str(n)
    else:
        new = base
    s = s.replace("const REMOTE_V = '%s';" % old, "const REMOTE_V = '%s';" % new, 1)
    open(html, 'w', encoding='utf-8').write(s)
    print('✓ REMOTE_V %s → %s（CDN 数据缓存键随之失效，各端将拉同一份最新数据）' % (old, new))
    return True

def push():
    os.chdir(REPO)
    bump_remote_v()                           # 推送前先刷新版本戳，使 CDN 缓存失效
    _git('add', '-A')
    if _git('diff', '--cached', '--quiet', check=False).returncode == 0:
        print('（无改动，跳过提交与推送）')
        return 'skip'
    msg = 'sync: 研究数据 + 利润快照同步到网站 (%s)' % time.strftime('%Y-%m-%d %H:%M')
    _git('-c', 'user.name=WorkBuddy', '-c', 'user.email=noreply@workbuddy.local',
         'commit', '-q', '-m', msg)
    print('✓ 已提交：' + msg)

    token = _gh_token()
    if not token:
        print('✗ 未取到 GitHub token（~/bin/gh auth token 失败），无法推送')
        sys.exit(1)
    # 尝试顺序：能直连才试直连 → 否则直接走本地代理（避免在被墙的直连上白等）
    direct_ok = _tcp_reachable()
    if direct_ok:
        if _try_push(token, [], _clean_env(), '直连'):
            print('✓ 已推送到 GitHub，约 1–5 分钟后网页打开即最新')
            return 'pushed'
        if _try_push(token, ['-c', 'http.version=HTTP/1.1'], _clean_env(), '直连 HTTP/1.1'):
            print('✓ 已推送到 GitHub，约 1–5 分钟后网页打开即最新')
            return 'pushed'
    else:
        print('  · 3s 探测：github.com:443 直连不通（大陆网络常见），跳过直连直接走代理')

    proxies = [u for u in _detect_proxies() if _proxy_reaches_github(u)]
    if not proxies:
        print('  · 未找到能到达 GitHub 的本地代理（FlClash 是否已开启并选好节点？）')
    for proxy in proxies:
        if _try_push(token, ['-c', 'http.version=HTTP/1.1'], _clean_env(proxy), '代理 ' + proxy):
            print('✓ 已推送到 GitHub，约 1–5 分钟后网页打开即最新')
            return 'pushed'
    print('✗ 推送失败（网络/代理问题）。请确认 FlClash 已开启并选好节点，再重试：'
          'python3 sync_to_site.py --push')
    sys.exit(1)

def export_all():
    """重建 data/ 下全部远程种子（patch.json / profit_snapshot.json / moneyflow.json / update_status.json）。
    不改 git / 不推送，供其它脚本（如 fetch_moneyflow.py）在抓取成功后复用。"""
    if not os.path.isdir(DESK_DIR):
        print(f'✗ 桌面数据目录不存在: {DESK_DIR}')
        return False

    # 读旧 patch，保留 quad（利润/成本）
    old_patch = {}
    if os.path.exists(PATCH_PATH):
        try:
            old_patch = json.load(open(PATCH_PATH, encoding='utf-8'))
        except Exception:
            old_patch = {}

    scanned = scan_desk()
    if scanned:
        patch = dict(old_patch)
        merged_codes = []
        for code, (mt, data, fn) in sorted(scanned.items()):
            entry = dict(data)
            # 保留旧 patch 中的 quad（利润/成本来自网页手工填写，桌面 JSON 不含）
            if code in old_patch and isinstance(old_patch[code], dict) and old_patch[code].get('quad'):
                entry['quad'] = old_patch[code]['quad']
            patch[code] = entry
            merged_codes.append(f'{code}({fn})')

        os.makedirs(os.path.dirname(PATCH_PATH), exist_ok=True)
        with open(PATCH_PATH, 'w', encoding='utf-8') as f:
            json.dump(patch, f, ensure_ascii=False, indent=1)
        print(f'✓ 已生成 data/patch.json：{len(patch)} 个品种')
        print('  品种：' + ', '.join(merged_codes))
    else:
        print(f'  ⚠ 桌面数据目录未匹配到任何品种 JSON，跳过 patch.json（{DESK_DIR}）')

    # 产业利润快照 → 网站同源副本（线上版利润参考库的数据通道）
    export_profit_snapshot()

    # 线上利润快照 → 回写页面内嵌 PROFIT_REF（消除各端利润档来源分叉）
    sync_embedded_profit_ref()

    # 资金流向快照 → 网站同源副本（线上版「当日资金流向」折叠条的数据通道）
    export_moneyflow_snapshot()
    export_update_status()
    return True


def sync_push():
    """导出全部远程种子并提交 + 推送 GitHub（供抓取脚本成功后「抓完即推」，根治网页同步时间戳滞后）。
    返回 'pushed' / 'skip' / 抛异常（失败）；失败会发系统通知 + 写 sync 状态，由调用方决定是否吞掉。"""
    export_all()
    try:
        res = push()
        notify.write_status('sync', ok=True, pushed=(res == 'pushed'))
        return res
    except SystemExit:
        # 子函数以 sys.exit(1) 表达失败（如推送 / token 失败）→ 已打印原因，补通知 + 状态
        notify.notify('❌ 网页同步/推送失败', '见终端日志：FlClash 是否开启？网络是否可用？', ok=False)
        notify.write_status('sync', ok=False, error='同步/推送失败（见终端日志），最可能是 FlClash 未开启或网络不通')
        raise
    except Exception as e:
        notify.notify('❌ 网页同步异常', str(e)[:200], ok=False)
        notify.write_status('sync', ok=False, error=str(e)[:300])
        print('✗ 同步异常：', e)
        raise


def main():
    push_flag = '--push' in sys.argv
    if not push_flag:
        export_all()
        print('\n（未推送。要上线加 --push：python3 sync_to_site.py --push）')
        notify.write_status('sync', ok=True, pushed='skip')
        return
    # push 模式：export + push 一次完成（sync_push 内部自带 export_all，避免重复生成）
    sync_push()

if __name__ == '__main__':
    main()
