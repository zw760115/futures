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
import os, sys, json, importlib.util, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import notify

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
    try:
        mod = load_service()
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
