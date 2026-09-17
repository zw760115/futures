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

用法：python3 fetch_moneyflow.py
"""
import os, sys, json, importlib.util

TPL_DIR = os.path.expanduser('~/Desktop/期货模板')
SERVICE = os.path.join(TPL_DIR, '期货行情服务.py')


def load_service():
    if not os.path.isfile(SERVICE):
        raise SystemExit('未找到 %s' % SERVICE)
    spec = importlib.util.spec_from_file_location('futures_quote_service', SERVICE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    mod = load_service()
    out = mod.build_moneyflow()
    rows = out.get('rows') or []
    if not rows:
        print('✗ 未取到资金流向数据（行情源不可用？）asof=%s' % out.get('asof'))
        return 1
    inflow = [r for r in rows if r['net'] > 0][:3]
    outflow = [r for r in rows if r['net'] < 0][-3:][::-1]
    print('✓ 资金流向已刷新：asof %s · fetch %s · %d 个品种'
          % (out.get('asof'), out.get('fetch_time'), out.get('count')))
    print('  净流入前三：' + ' · '.join('%s %+.2f亿' % (r['code'], r['net'] / 1e8) for r in inflow))
    print('  净流出前三：' + ' · '.join('%s %+.2f亿' % (r['code'], r['net'] / 1e8) for r in outflow))
    for d in getattr(mod, 'MF_SNAP_DIRS', []):
        print('  已写入：%s' % os.path.join(d, getattr(mod, 'MF_SNAP_NAME', '资金流向快照.json')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
