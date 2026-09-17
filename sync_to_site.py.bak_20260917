#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌面期货研究数据 → GitHub Pages 网站 同步桥接器
================================================
用途：你在桌面版「📥 全部同步」拉完数据后，跑本脚本把
      ~/Desktop/期货研究数据/*.json 整份同步成网站的远程种子
      data/patch.json，并（可选）推送到 GitHub，让网页版打开即最新。

原理：模板已有「远程种子合并层」(applyRemoteSeed)：
      内嵌数据 < 远程种子(patch.json) < 用户浏览器手填
      本脚本只负责生成 patch.json（全字段合并），不动用户手填。

用法：
  python3 sync_to_site.py              # 仅生成 data/patch.json（不推送）
  python3 sync_to_site.py --push       # 生成并 git push（需 gh 已登录）

注意：
  - 利润/成本(quad) 不在桌面 JSON 里（是网页手工填的），脚本会保留
    旧 patch.json 中的 quad，不会被基本面数据冲掉。
  - 每个品种取桌面文件夹里 mtime 最新的那份（兼容带日期后缀的副本）。
  - GitHub token 已存于本地 gh，--push 走 gh，无需重发。
"""
import os, re, sys, json, glob, subprocess

REPO = os.path.dirname(os.path.abspath(__file__))
DESK_DIR = os.path.expanduser('~/Desktop/期货研究数据')
PATCH_PATH = os.path.join(REPO, 'data', 'patch.json')

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
    """返回 {code: (mtime, data)}，每个 code 取最新文件"""
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

def main():
    push = '--push' in sys.argv
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
    if not scanned:
        print('✗ 桌面数据目录未匹配到任何品种 JSON')
        sys.exit(1)

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

    if not push:
        print('\n（未推送。要上线加 --push：python3 sync_to_site.py --push）')
        return

    # 推送
    os.chdir(REPO)
    subprocess.run(['git', 'add', '-A'], check=True)
    msg = 'sync: 桌面研究数据同步到网站远程种子 (%d 品种)' % len(patch)
    subprocess.run(['git', '-c', 'user.name=WorkBuddy', '-c', 'user.email=noreply@workbuddy.local',
                    'commit', '-m', msg], check=True)
    r = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True)
    if r.returncode != 0:
        print('✗ gh 未登录，无法推送。请先 `gh auth login --with-token`')
        sys.exit(1)
    subprocess.run(['git', 'push', 'origin', 'main'], check=True)
    print('✓ 已推送到 GitHub，约 1–5 分钟后网页打开即最新')

if __name__ == '__main__':
    main()
