#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_copies.py — 期货研究模板「单一数据源」同步器

原则：
  1. futures-research-pages/index.html 是【唯一权威源】（网页版 + GitHub Pages 来源）。
  2. 桌面双击版、Downloads 便携版都是【由它生成的产物】，不再各自手动改。
  3. 改完 index.html 后跑本脚本：自动把权威源同步到另两份，并可一键推 GitHub。

用法：
  python3 sync_copies.py            # 仅同步本地两份副本（推荐日常）
  python3 sync_copies.py --push     # 同步 + git commit/push（含 index.html 与脚本自身）
  python3 sync_copies.py --no-backup # 跳过备份（不推荐）

注意：
  - 覆盖前会自动在目标同目录生成带时间戳的 _bak_ 备份，安全可回滚。
  - 推 GitHub 走 FlClash 代理（127.0.0.1:7890），无需手动设环境。
"""
import os
import sys
import shutil
import subprocess
import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANON = HERE / "index.html"

# 由权威源派生的两份副本（双击/便携场景）
TARGETS = [
    Path.home() / "Desktop" / "期货模板" / "期货商品研究模板_库存基差期限结构.html",
    Path.home() / "Downloads" / "期货商品研究模板_库存基差期限结构.html",
]

PROXY = "http://127.0.0.1:7890"
GIT_LOCKS = [
    HERE / ".git" / "index.lock",
    HERE / ".git" / "refs" / "remotes" / "origin" / "main.lock",
]


def log(msg):
    print(f"[sync] {msg}")


def backup_target(t: Path):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = t.with_name(f"{t.stem}_bak_{ts}{t.suffix}")
    shutil.copy2(t, bak)
    return bak


def clean_git_locks():
    for lk in GIT_LOCKS:
        try:
            if lk.exists():
                lk.unlink()
                log(f"已清理僵尸锁: {lk}")
        except Exception as e:
            log(f"清理锁失败(忽略): {lk} -> {e}")


def git(*args):
    env = dict(os.environ)
    env["http_proxy"] = PROXY
    env["https_proxy"] = PROXY
    env["HTTP_PROXY"] = PROXY
    env["HTTPS_PROXY"] = PROXY
    # 显式移除可能干扰的变量
    env.pop("GIT_CONFIG_NOSYSTEM", None)
    return subprocess.run(
        ["git", *args], cwd=str(HERE), env=env,
        capture_output=True, text=True,
    )


def main():
    push = "--push" in sys.argv
    no_backup = "--no-backup" in sys.argv

    if not CANON.exists():
        log(f"找不到权威源: {CANON}")
        sys.exit(1)

    canon_size = CANON.stat().st_size
    log(f"权威源: {CANON} ({canon_size} B)")

    for t in TARGETS:
        if not t.exists():
            log(f"目标不存在(跳过): {t}")
            continue
        if t.resolve() == CANON.resolve():
            log(f"目标与权威源相同，跳过: {t}")
            continue
        if not no_backup:
            bak = backup_target(t)
            log(f"备份 -> {bak.name}")
        shutil.copy2(CANON, t)
        new_size = t.stat().st_size
        log(f"已同步: {t.name} ({new_size} B)")

    log("本地两份副本已与权威源一致。")

    if push:
        clean_git_locks()
        # 仅跟踪 index.html 与脚本自身
        git("add", "index.html", "sync_copies.py")
        r = git("commit", "-m", "chore: 单一数据源同步 — index.html 为权威源，sync_copies.py 锁定三副本一致")
        log("git commit:\n" + (r.stdout or r.stderr).strip())
        if r.returncode == 0 or "nothing to commit" in (r.stdout + r.stderr):
            p = git("push", "origin", "main")
            log("git push:\n" + (p.stdout or p.stderr).strip())
            clean_git_locks()
        else:
            log("提交失败，未推送。")
    else:
        log("未传 --push，未提交/推送。需要发布时加 --push。")


if __name__ == "__main__":
    main()
