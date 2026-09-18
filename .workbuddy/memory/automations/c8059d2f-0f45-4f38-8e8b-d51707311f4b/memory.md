# 自动化执行记录：刷新期货产业利润快照 + 资金流向快照 + 推送网页版

本文件只记录高层执行情况，不含完整产物内容。

## 2026-09-18 18:01（本次）
- 任务：期限结构刷新 → 利润快照 + 资金流向 → sync_to_site --push → 状态/告警。
- 结果：**全部成功**，无失败告警。
  - 期限结构：59/59 成功，term_date=2026-09-18（inv/basis/drivers/data_date 未动）。
  - 资金流向：59 品种，asof 2026-09-18；净流入前三 AU/AG/SN，净流出前三 SC/JM/M。
  - 产业利润快照：35 品种，顶层 asof=2026-09-18，28 条 note 依据 9-16~9-18 公开源重写；利润档位无变动，PVC 成本更新为 5329.53。
  - 推送：直连成功（commit ad36bcb / 8d46cc0 / 64e10f3），REMOTE_V=202609181804.1。
- 关键处置（后续务必沿用）：
  1. **代理先探测再决定**：7890 当时 closed（FlClash GUI 未起，只有 clash-verge-service 在跑），eastmoney 直连 200 → 走直连即可。
  2. **修了 refresh_fundamentals.py 的真 bug**：无代理分支 `opener = urllib.request` → 全部品种静默失败；改为恒用 `build_opener()`。
  3. fetch_moneyflow.py 会顺带触发一次 sync/push，故**改完利润快照后必须再跑一次** `sync_to_site.py --push`。
  4. `快照更新状态.json` 的 `profit` 段没人写，需显式 notify.write_status('profit',...) 后再推一次。
- 操作提示：利润快照刷新用一次性脚本（json.load → 按 code 更新 profit/cost/asof/src/note → assert 品种集合不变 → 双目录写盘 + .bak → json.load 校验），跑完删掉；本次已从 git 移除残留。

## 2026-09-17 17:45（首次记录）

- 任务：刷新「产业利润快照」（AI 联网检索维护）与「资金流向快照」，同步推送 GitHub Pages。
- 结果：**全部成功**。
  - 产业利润快照：35 个品种全覆盖，asof 更新为 2026-09-17；写出 ~/Desktop/期货研究数据/ 与 ~/Downloads/期货研究数据/ 两处，内容一致，json.load 校验通过，各留 .bak。
  - 有 cost 的品种 12 个（RM 5759 / AL 16155 / AO 2770 / SR 5400 / SS 14026 / SI 8987 / PS 43681 / V 5392 / EB 10108 / PK 7810 / CF 17500 / C 2180）；其余 23 个 cost 为 null。
  - 本期新增 cost：AL、AO、V、PS（其余为保留或同口径复现值）。
  - 资金流向快照：fetch_moneyflow.py 一次通过，59 个品种，净流入前三 CU/SN/LC，净流出前三 SC/EG/JM。
  - sync_to_site.py --push：直连推送成功（commit "sync: 研究数据 + 利润快照同步到网站 (2026-09-17 17:47)"）。

## 复用要点 / 坑位（后续执行参考）

- 数据源检索分组跑并行 WebSearch 效率最高：黑色（RB/HC/J/SF/SM/FG）、能化（TA/PF/V/EB/MA/UR/L/PP）、有色（CU/ZN/NI/SN/SS/SI/PS/AL/AO/PB）、农产品（M/P/RM/OI/C/CF/SR/PK/LH/JD）。每组一次查询即可覆盖。
- 写盘用一次性 Python 脚本（json.dump indent=1, ensure_ascii=False, 末尾换行），脚本内 assert 校验品种集合与原文件完全一致，避免误增删。
- 稳定可用的 cost 源：SMM 电解铝总成本 / 氧化铝完全成本（期市早餐每日更新）、隆众 PVC 电石法全国成本、百川 工业硅产区成本 & 多晶硅平均生产成本、Mysteel 加菜籽完税到厂成本。
- 易混淆、必须留空的口径：PTA 加工费、铜/锌/锡精矿 TC、油厂榨利、进口利润、聚烯烃「油制/PDH 制利润」、玻璃「按燃料路线成本」、双硅「分产区成本」——均非该品种自身的生产成本，写 note 不写 cost。
- 单位口径注意：生猪、蛋鸡的成本是「元/公斤」「元/只」，与模板的元/吨不可直接比较，一律 cost=null 只在 note 说明。
