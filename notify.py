#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
失败告警 + 更新状态 公共模块
==========================
被 fetch_moneyflow.py / sync_to_site.py 调用：
  - notify.notify(title, msg, ok=True)   仅失败(ok=False)时弹 macOS 系统通知，成功静默不骚扰
  - notify.write_status(kind, ok, **info) 把每次运行结果写进
        ~/Desktop/期货研究数据/快照更新状态.json
状态文件再由 sync_to_site.py 复制为 data/update_status.json，网页版据此显示
「资金流向 / 网页同步 是否更新成功」，用户打开网页即可知道有没有更新、失败原因。
"""
import os, sys, json, datetime, subprocess

DATA_DIR = os.path.expanduser('~/Library/Application Support/期货服务/期货研究数据')
STATUS_PATH = os.path.join(DATA_DIR, '快照更新状态.json')
KINDS = ('moneyflow', 'sync', 'profit')


def _now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def notify(title, message, ok=True):
    """失败(ok=False)时弹 macOS 系统通知（带声音）。best-effort，环境不支持也不报错。"""
    if ok:
        return
    if sys.platform != 'darwin':
        return
    try:
        msg = (message or '').replace('"', '\\"')[:240]
        title = (title or '期货快照').replace('"', '\\"')[:60]
        script = 'display notification "%s" with title "%s" sound name "Glass"' % (msg, title)
        subprocess.run(['osascript', '-e', script], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=8)
    except Exception:
        pass


def write_status(kind, ok, **info):
    """更新 ~/Desktop/期货研究数据/快照更新状态.json 中 kind 这一段。"""
    if kind not in KINDS:
        return
    now = _now()
    data = {}
    if os.path.isfile(STATUS_PATH):
        try:
            data = json.load(open(STATUS_PATH, encoding='utf-8'))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
    rec = data.setdefault(kind, {})
    rec['last_run'] = now
    if ok:
        rec['last_success'] = now
        rec['status'] = 'ok'
        rec.pop('error', None)
    else:
        rec['status'] = 'fail'
        rec['error'] = (info.get('error') or '未知错误')[:400]
    for k, v in info.items():
        if k == 'error':
            continue
        rec[k] = v
    # 只保留已知三类，避免文件无限膨胀
    data = {k: data[k] for k in KINDS if k in data}
    try:
        os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
        with open(STATUS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write('\n')
    except Exception:
        pass
