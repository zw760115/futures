#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌面期货研究数据 → GitHub Pages 网站 同步桥接器
================================================
用途：把桌面/下载两份研究数据同步成网站的远程种子，并（可选）推送到 GitHub，
      让网页版打开即最新。

产出（两件事）：
  1. data/patch.json              ← ~/Desktop/期货研究数据/*.json 全字段合并
  2. data/profit_snapshot.json    ← 产业利润快照.json 的网站副本
     （index.html 的 loadProfitSnapshot() 会先读本地服务 /api/profit_snapshot，
       线上版读不到本地服务时回退读同源 data/profit_snapshot.json，
       所以这份副本是「利润参考库」能在网页版生效的通道）

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

REPO = os.path.dirname(os.path.abspath(__file__))
DESK_DIR = os.path.expanduser('~/Desktop/期货研究数据')
DL_DIR = os.path.expanduser('~/Downloads/期货研究数据')
PATCH_PATH = os.path.join(REPO, 'data', 'patch.json')
SNAP_OUT = os.path.join(REPO, 'data', 'profit_snapshot.json')
SNAP_NAME = '产业利润快照.json'

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
        code = code_from_filename(fn)
        if not code:
            continue
        try:
            data = json.load(open(fp, encoding='utf-8'))
        except Exception as e:
            print(f'  ⚠ 跳过 {fn}（解析失败: {e}）')
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

def push():
    os.chdir(REPO)
    _git('add', '-A')
    if _git('diff', '--cached', '--quiet', check=False).returncode == 0:
        print('（无改动，跳过提交与推送）')
        return
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
            return
        if _try_push(token, ['-c', 'http.version=HTTP/1.1'], _clean_env(), '直连 HTTP/1.1'):
            print('✓ 已推送到 GitHub，约 1–5 分钟后网页打开即最新')
            return
    else:
        print('  · 3s 探测：github.com:443 直连不通（大陆网络常见），跳过直连直接走代理')

    proxies = [u for u in _detect_proxies() if _proxy_reaches_github(u)]
    if not proxies:
        print('  · 未找到能到达 GitHub 的本地代理（FlClash 是否已开启并选好节点？）')
    for proxy in proxies:
        if _try_push(token, ['-c', 'http.version=HTTP/1.1'], _clean_env(proxy), '代理 ' + proxy):
            print('✓ 已推送到 GitHub，约 1–5 分钟后网页打开即最新')
            return
    print('✗ 推送失败（网络/代理问题）。请确认 FlClash 已开启并选好节点，再重试：'
          'python3 sync_to_site.py --push')
    sys.exit(1)

def main():
    push_flag = '--push' in sys.argv
    if not os.path.isdir(DESK_DIR):
        print(f'✗ 桌面数据目录不存在: {DESK_DIR}')
        sys.exit(1)

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

    if not push_flag:
        print('\n（未推送。要上线加 --push：python3 sync_to_site.py --push）')
        return
    push()

if __name__ == '__main__':
    main()
