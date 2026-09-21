#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 / 刷新「资金流向快照.json」（当日资金流向，主力净流入·收盘位置法）
================================================================
用途：网页版（GitHub Pages）读不到本地服务，靠 sync_to_site.py 把快照导出成
      data/moneyflow.json 才能显示。本脚本负责在不启动 HTTP 服务的情况下刷新快照。

做法：直接复用 ~/Desktop/期货模板/期货行情服务.py 里的 build_moneyflow()，
      它会联网取数并把快照写到
        ~/Desktop/期货研究数据/资金流向快照.json
        ~/Downloads/期货研究数据/资金流向快照.json

失败告警：抓不到行情 / 脚本异常时，除打印原因，还会
        (1) 弹 macOS 系统通知（notify.notify）
        (2) 写 ~/Desktop/期货研究数据/快照更新状态.json（moneyflow 段）
      网页版据此显示「资金流向 更新状态」，用户打开即知有没有更新、失败原因。

用法：python3 fetch_moneyflow.py
"""
import os, sys, json, importlib.util, traceback, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import notify

TPL_DIR = os.path.expanduser('~/Desktop/期货模板')
SERVICE = os.path.join(TPL_DIR, '期货行情服务.py')

# ---------------------------------------------------------------------------
# 2026-09-21：东财 push2*.eastmoney.com 在本机被网络整体重置——TLS 握手成功、请求发出后
# 直接被空回复掐断（RemoteDisconnected），服务自带的 5 个行情域名全部不可用，资金流向
# 连续抓不到。实测东财期货频道接口 futsseapi.eastmoney.com/list/<mkt> 稳定可用，且字段齐全：
#   o/h/l 开高低 · p 最新 · zjsj 昨结算 · vol 成交量 · cje 成交额 · ccl 持仓量
# 这里把它映射成服务内部沿用的 push2 字段名（f2/f5/f6/f15/f16/f18/f12/f14），运行时
# 替换服务模块的 _fetch_market，**不改动服务源码**，build_moneyflow 的算法与网页口径不变。
FUTSSE_HOST = 'https://futsseapi.eastmoney.com'
FUTSSE_FIELDS = 'dm,sc,name,p,zde,zdf,vol,ccl,o,h,l,zjsj,cje'


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in ('', '-', '--'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _futsse_market(mkt, fields=None, pz=100, max_pages=8):
    """一次取回该交易所全部合约，转成 push2 行结构。"""
    num = str(mkt).split(':')[-1]
    url = (FUTSSE_HOST + '/list/' + num + '?orderBy=dm&sort=asc&pageSize=500&pageIndex=0'
           + '&field=' + FUTSSE_FIELDS)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://futures.eastmoney.com/',
    }
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    out = []
    for it in (data.get('list') or []):
        dm = it.get('dm')
        if not dm:
            continue
        px = _num(it.get('p'))
        zde = _num(it.get('zde'))
        # 昨收 = 最新 - 涨跌额；缺涨跌额时退用昨结算
        prev = (px - zde) if (px is not None and zde is not None) else _num(it.get('zjsj'))
        out.append({
            'f12': str(dm), 'f14': it.get('name') or '',
            'f2': px, 'f5': _num(it.get('vol')), 'f6': _num(it.get('cje')),
            'f15': _num(it.get('h')), 'f16': _num(it.get('l')),
            'f18': prev, 'f78': _num(it.get('ccl')),
        })
    return out


def install_futsse_source(mod):
    """用期货频道接口替换服务模块的行情抓取（失败自动回退原实现）。"""
    orig = getattr(mod, '_fetch_market', None)
    if orig is None:
        return

    def wrapper(mkt, fields=None, pz=100, max_pages=8):
        try:
            rows = _futsse_market(mkt, fields, pz, max_pages)
            if rows:
                return rows
            print('  ⚠ 期货频道 %s 返回空，回退 push2' % mkt)
        except Exception as e:
            print('  ⚠ 期货频道 %s 失败: %s，回退 push2' % (mkt, e))
        return orig(mkt, fields, pz, max_pages)

    mod._fetch_market = wrapper


# 数据唯一真源（2026-09-18 22:35 起）：数据只在 Library 这一份，桌面/下载不再留拷贝。
# 但服务的 MF_SNAP_DIRS 是按「脚本自身所在目录」推导的，而本脚本是用 ~/Desktop/期货模板
# 下的 symlink 路径加载服务 → SCRIPT_DIR 落到桌面模板目录，快照写不进真源目录，
# 于是 sync_to_site 只能读到服务早先写的旧副本。这里把真源目录显式补进去。
DATA_DIR = os.path.expanduser('~/Library/Application Support/期货服务/期货研究数据')


def ensure_snap_dirs(mod):
    dirs = getattr(mod, 'MF_SNAP_DIRS', None)
    if isinstance(dirs, list) and os.path.isdir(DATA_DIR) and DATA_DIR not in dirs:
        dirs.insert(0, DATA_DIR)


def load_service():
    if not os.path.isfile(SERVICE):
        raise SystemExit('未找到 %s' % SERVICE)
    spec = importlib.util.spec_from_file_location('futures_quote_service', SERVICE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    try:
        mod = load_service()
        install_futsse_source(mod)
        ensure_snap_dirs(mod)
        out = mod.build_moneyflow()
        rows = out.get('rows') or []
        if not rows:
            reason = '未取到资金流向数据（行情源不可用？）asof=%s' % out.get('asof')
            notify.notify('❌ 资金流向刷新失败', reason, ok=False)
            notify.write_status('moneyflow', ok=False, error=reason, asof=out.get('asof'), count=0)
            print('✗ ' + reason)
            return 1
        inflow = [r for r in rows if r['net'] > 0][:3]
        outflow = [r for r in rows if r['net'] < 0][-3:][::-1]
        print('✓ 资金流向已刷新：asof %s · fetch %s · %d 个品种'
              % (out.get('asof'), out.get('fetch_time'), out.get('count')))
        print('  净流入前三：' + ' · '.join('%s %+.2f亿' % (r['code'], r['net'] / 1e8) for r in inflow))
        print('  净流出前三：' + ' · '.join('%s %+.2f亿' % (r['code'], r['net'] / 1e8) for r in outflow))
        for d in getattr(mod, 'MF_SNAP_DIRS', []):
            print('  已写入：%s' % os.path.join(d, getattr(mod, 'MF_SNAP_NAME', '资金流向快照.json')))
        notify.write_status('moneyflow', ok=True, asof=out.get('asof'),
                            count=out.get('count'), fetch_time=out.get('fetch_time'))
        # 根治：抓取成功后自动同步并推送到网站，网页「同步时间戳」即时更新，徽标保持常绿
        try:
            import sync_to_site
            res = sync_to_site.sync_push()
            if res == 'pushed':
                print('✓ 抓取后已自动推送网站（网页同步时间已更新，徽标回绿）')
            elif res == 'skip':
                print('（无改动，未推送）')
        except Exception as e:
            # 抓取本身已成功；推送失败不覆盖 moneyflow 成功状态，仅提示
            print('⚠ 自动推送网站失败（抓取已成功，数据在本地）：%s' % e)
        return 0
    except Exception as e:
        reason = '资金流向脚本异常：%s' % e
        notify.notify('❌ 资金流向刷新失败', reason, ok=False)
        notify.write_status('moneyflow', ok=False, error=reason)
        print('✗ ' + reason)
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
