# 自动化执行记录：刷新期货产业利润快照 + 资金流向快照 + 推送网页版

本文件只记录高层执行情况，不含完整产物内容。

## 2026-09-28 17:52（本次）
- 任务：期限结构刷新 → 利润快照 + 资金流向 → sync_to_site --push → 状态/告警。中秋节后首个交易日。
- 结果：**全部成功**，无失败告警。
  - 期限结构：59/59，term_date=2026-09-28（inv/basis/drivers/data_date 原样保留，抽查 AU data_date 仍 2026-09-09）；合约数仅 EG 11→12、PS 7→8 有变动。
  - 资金流向：59 品种，asof 2026-09-28；净流入前三 MA +198.48亿 / SA +172.89亿 / FU +99.06亿，净流出前三 AU -1242.90亿 / RU -420.39亿 / M -378.09亿。
  - 产业利润快照：35 品种 asof=2026-09-28，note 全部依 9-28 公开源重写；**利润档位与 12 个 cost 全部保留原值**（未获同口径新值）。
  - 推送：3 次提交，本地 HEAD = 远端 HEAD（c8686fe），REMOTE_V=202609281902.1；线上验收 profit_snapshot asof=2026-09-28/35 品种、update_status 三段全 ok。
- 环境：代理 7890 OPEN；东财 futsse 源正常；首次 push 直连成功、第二次走代理成功（对齐 sync 状态段）。
- 🔴 **关键处置：修复了期限结构跨品种串值的老 bug（至少 9-18 起存在，影响 5 个品种）**
  1. `_build_term()` 原用 `startswith(code)`，同交易所「本品种代码是别品种前缀」时收进外品种合约：**P 棕榈油 ← pg/pp、J 焦炭 ← jd/jm、B 豆二 ← bb/bz、L 聚乙烯 ← lg/lh、C 玉米 ← cs**。
  2. 后果：`main_idx` 按持仓量最大 ⇒ **棕榈主力被标成 pp2701(8595)、焦炭主力被标成 jm2701(1457.5)**，图表与主力判定长期错误。
  3. 改为锚定 `^<CODE>\d+$` 后只重刷 5 个品种：P→p2701@9630、J→j2701@1952、L→l2701@8202、B→b2611@4021、C→c2611@2180；全品种体检 `剩余串值品种: 0`。
  4. 已回写 skill `futures-fundamentals-batch`：新增「常见坑 21」+ 把串值体检并入每日流程第 1 步。
- 其他要点：
  1. **甲醇主力口径不是 bug**：新闻报「主力 3249/+4.71%」是近月 MA611，脚本按持仓量最大给 MA701 2941/+1.69%（近强远弱 Back 结构），写 note 时两个都写。
  2. 线上验收需带随机缓存键；本次 `profit_snapshot.json` 推后仍显 09-25，`git show HEAD` 确认上游正确，等 45s 后即取到 09-28（坑 17 的又一次实例，未重推）。
  3. 利润刷新仍用一次性脚本（json.load → 更新 asof/src/note → assert 品种集合不变 + 档位/cost 不变 → .bak → 写盘 + json.load 校验），跑完已删，工作区 `git status` 干净。
- ⚠️ 后续提醒：10-01～10-07 国庆休市（10-08 恢复），期间连续 7 天走休市口径（skill 坑 20/22）；10-08 首日恢复常规口径。

## 2026-09-25 17:50
- 任务：期限结构刷新 → 利润快照 + 资金流向 → sync_to_site --push → 状态/告警。
- **背景：9-25(周五)～9-27 为中秋节休市**（9-24 晚无夜盘，9-28 周一恢复交易）。行情源静默返回 9-24 收盘值 ⇒ 当日全站数据与 9-24 **逐字节相同**（非 bug，已写入 skill 坑 20）。
- 结果：**全部成功**，无失败告警。
  - 期限结构：59/59「成功」，term_date=2026-09-25（价格实为 9-24 收盘；inv/basis/drivers/data_date 原样保留，抽查 AU data_date 仍 2026-09-09）；4 个僵尸品种（BB/FB/RS/WR）无期限结构，属预期。
  - 资金流向：59 品种，asof 2026-09-25（实为 9-24 收盘）；净流入前三 SC +1703.35亿 / RU +738.80亿 / EG +692.35亿，净流出前三 AU -1603.74亿 / AG -333.15亿 / LH -231.02亿 —— 与 9-24 完全一致。
  - 产业利润快照：35 品种 asof=2026-09-25；profit 档位与 12 个 cost **全部保留原值**；每个品种 note 追加【休市说明 + 节后关注】（并补 9-24/9-25 新增事实：世界钢铁协会 8 月中国粗钢-3.7%、9 月焦煤长协浮动值+323 元、焦煤竞拍流拍率 93.1%、CCF PTA 负荷 70.2%、EG 港口库存 13.4 万吨、LME 锌+1.63%/镍库存 278790 吨、统计局 9 月中旬猪价-2.7%、8 月能繁-2.94%、中美第八轮磋商+12 万吨美豆成交、沙河玻璃 812 元、硅铁产区利润<50 元/吨等）；src 追加休市标注。
  - 推送：3 次提交（a242da6 17:46 / 56803a6 17:50 / 1f14111 17:50），REMOTE_V=202609251750.1；远端 HEAD 与本地 HEAD 一致（1f14111，sha 校验通过）。
  - 线上验收：profit_snapshot.json asof=2026-09-25/35 品种、update_status.json 三段（moneyflow/ sync / profit）全部 ok 且 asof=2026-09-25（随机缓存键打穿，无需等待）。
- 环境：代理 7890 OPEN；东财 futsse/push2delay 正常返回（内容为 9-24 收盘）；git push 直连两次失败、走代理成功（与 9-23 同款瞬时抖动）。
- 关键处置：
  1. 用「与 9-24 快照 diff 为空」判定休市，避免了误报「数据源坏了」而反复重跑（已回写 skill 坑 20）。
  2. 休市日利润快照口径首次确立：asof=当日（快照更新日）+ note 内显式写明「行情为节前最后交易日 9-24 收盘」+ src 追加休市标注，避免 asof 与 note 口径打架（已回写 skill「每日 17:45 自动化」小节）。
  3. 先 `notify.write_status('profit',…)`（带 src）再推；两次 `--push` 对齐线上 sync 段。
  4. 一次性利润刷新脚本在 `/tmp` 起草执行后删除；工作区 `git status` 干净。
- ⚠️ 后续提醒：10-01～10-07 国庆休市（10-08 恢复），期间的 17:45 自动化会连续 7 天命中休市口径，按上面第 2 条处理；10-08 首日恢复常规口径（note 不再带【休市说明】）。

## 2026-09-24 17:57
- 任务：期限结构刷新 → 利润快照 + 资金流向 → sync_to_site --push → 状态/告警。
- 结果：**全部成功**，无失败告警。
  - 期限结构：59/59 成功，term_date=2026-09-24（inv/basis/drivers/data_date 原样保留，抽查 AU data_date 仍为 2026-09-09）；合约数普遍持平，仅 EG 12→11、EB 11→10、J 33→32、PS 9→7 有变动。
  - 资金流向：59 品种，asof 2026-09-24；净流入前三 SC +1703.35亿 / RU +738.80亿 / EG +692.35亿，净流出前三 AU -1603.74亿 / AG -333.15亿 / LH -231.02亿。
  - 产业利润快照：35 品种全部 asof=2026-09-24，note 全部依 9-24 公开源重写（Mysteel/SMM/上海金属网SHMET/卓创/隆众/CCF/百川盈孚/生意社/国家统计局/内蒙古粮储局/长江有色/东方财富期货 + 光大·华泰·东吴·东海·混沌天成·宁证·上海中期·中联钢·兰格）；档位无变动（high 3 / mid 10 / low 22）；cost 无同口径新值→12 个品种全部保留原值。
  - 推送：3 次提交（7a0962d 17:57 / 8d289a4 17:59 / 66129fc 17:59），REMOTE_V=202609241759.1，远端 HEAD 与本地 HEAD 一致（66129fc，sha 校验通过）。
- 环境：代理 7890 **OPEN**（www.eastmoney.com 200）；东财 `futsseapi` 源正常，直连 push GitHub 全程成功、无需中转到代理。
- 关键处置：
  1. 按 skill 顺序执行「期限结构 → fetch_moneyflow（自带一次 push，17:57）→ 刷利润快照 + 显式 `notify.write_status('profit', src=…)` → 两次 `sync_to_site.py --push`」，一次到位无返工；第二次 push 用于把线上 `sync` 段对齐（坑 14）。
  2. **坑 17 复核并细化**：线上 `profit_snapshot.json` **与 `update_status.json` 同时**停在 09-23；`git show HEAD` 确认上游正确后，带随机缓存键 `sleep 20` 再取即为 09-24 ⇒ 边缘缓存窗口**可短至 20–40 秒**，未重推（已回写 skill）。
  3. `raw.githubusercontent.com` 直连本次**空响应**，不可作为上游对照，改用 `git show HEAD:data/...`（已回写 skill 坑 17）。
  4. 发现 `~/Desktop/期货模板/期货研究数据/` 现在是一个**真实目录（非软链）**，但只含 fetch_moneyflow 写入的 `资金流向快照.json`；利润快照只在 Library 真源 ⇒ 只需写 Library 一份（已回写 skill「数据目录」小节）。
- 一次性利润刷新脚本在 `/tmp` 起草并执行，跑完已删；工作区 `git status` 干净无残留。

## 2026-09-23 17:45
- 任务：期限结构刷新 → 利润快照 + 资金流向 → sync_to_site --push → 状态/告警。
- 结果：**全部成功**，无失败告警。
  - 期限结构：59/59 成功，term_date=2026-09-23（inv/basis/drivers/data_date 原样保留，抽查 AU data_date 仍为 2026-09-09）；合约数普遍持平，仅 J 32→33、LC 10→12、PT 5→6、PS 10→9 有变动。
  - 资金流向：59 品种，asof 2026-09-23；净流入前三 RU +735.67亿 / BR +174.51亿 / NR +137.03亿，净流出前三 SC -803.06亿 / MA -506.55亿 / BU -362.08亿。
  - 产业利润快照：35 品种全部 asof=2026-09-23，note 全部依 9-23 公开源重写（Mysteel/SMM/卓创/隆众/CCF/百川盈孚/生意社/内蒙古粮储局/龙口市府/金投网/同花顺/曲合网 + 迈科·申银万国·光大·东吴·混沌天成·广州期货·兰格）；利润档位无变动；cost 无同口径新值→12 个品种全部保留原值。
  - 推送：4 次提交（ec626de 17:46 / 9d931ee 17:47 / 8573c09 18:23 / 326069c 18:23），REMOTE_V=202609231823.1.2，远端 HEAD 与本地 HEAD 一致（326069c，sha 校验通过）。
- 环境：代理 7890 **OPEN**（出口 IP 66.90.99.210）；东财 `futsseapi` 直连+代理均正常。
- 关键处置：
  1. **17:47 那次 push 走代理报 `SSL_ERROR_SYSCALL`**（探活判直连不通→走 7890→LibreSSL 握手断）。十几秒后直连/代理 `curl github.com` 双双 200 → **直接重跑 `--push` 即走直连成功**，属代理节点瞬时抖动，按重试处理（记入 skill 坑 18）。
  2. **线上 `profit_snapshot.json` / `update_status.json` push 后仍返回 09-22**，一度疑似未上线；核对 `git show HEAD:data/...` 正确后用 `?cb=<随机>` 打穿 CDN 才拿到 09-23 ⇒ **GitHub Pages 边缘缓存假象，不要重推**（记入 skill 坑 17，`?v=<REMOTE_V>` 也穿不透）。
  3. `notify.write_status('profit', …)` 是 merge 语义，本次首写漏传 `src` ⇒ 状态段沿用了 09-22 的 src；补一次显式写入并推送（记入 skill 说明）。
  4. 同分钟多次收尾重推 → `REMOTE_V` 叠成 `202609231823.1.2`，功能无害（记入 skill 坑 19）。
  5. 一次性利润刷新脚本跑完已删，工作区 `git status` 干净无残留。
- 已同步更新 skill `futures-fundamentals-batch`：补 35 品种完整清单、带随机缓存键的线上验收命令、状态段 merge 语义说明，新增常见坑 17/18/19。

## 2026-09-22 17:45
- 任务：期限结构刷新 → 利润快照 + 资金流向 → sync_to_site --push → 状态/告警。
- 结果：**全部成功**，无失败告警。
  - 期限结构：59/59 成功，term_date=2026-09-22（inv/basis/drivers/data_date 原样保留，抽查 AU data_date 仍为 2026-09-09）；合约数 3~35 条/品种（EG/EB/JM/I 6→12、J 6→31、LC 6→11、SI 6→10 为最大补齐）。
  - 资金流向：59 品种，asof 2026-09-22；净流入前三 SC +466.39亿 / MA +440.42亿 / LC +204.77亿，净流出前三 AU -1487.73亿 / AG -457.38亿 / JM -375.75亿。
  - 产业利润快照：35 品种全部 asof=2026-09-22，note 全部依 9-22 公开源重写（Mysteel/SMM/卓创/隆众/CCF/生意社/内蒙古粮储局/金融界/同花顺/曲合网 + 长江证券·申银万国·光大·首创·混沌天成·广发·华泰）；利润档位无变动；cost 无同口径新值→12 个品种全部保留原值。
  - 推送：3 次提交（08a24be 17:46 / e74b37a 17:47 / 603401c 17:50），REMOTE_V=202609221750，远端 HEAD 与本地 HEAD 一致（sha 校验通过）。
- 环境：代理 7890 **OPEN**；东财 `futsseapi.eastmoney.com/list/<mkt>` 直连与代理均稳定（`futures.eastmoney.com` 200）；`push2*` 未被重新测试（已非主路径）。
- 关键处置：
  1. 首推走直连成功，第二次走代理成功；**校验远端必须带代理**——`git ls-remote` 直连会 75s 超时，与 push 结果不等价（记入 skill 坑 15）。
  2. 发现的既有小瑕疵：`data/update_status.json` 的 `sync` 段永远滞后一次推送（脚本先复制状态再写自身状态）→ 收尾多跑一次 push 对齐（记入 skill 坑 14）。
  3. 流程顺序按「期限 → 资金流向 → 利润快照 + 显式 write_status('profit') → push」执行，利润状态段先写后推，一次到位。
  4. 利润快照刷新用一次性脚本（json.load → 按 code 更新 asof/src/note → assert 品种集合不变 → .bak → 写盘 + json.load 校验），跑完已删除，工作区干净无残留。
- 已同步更新 skill `futures-fundamentals-batch`：新增「每日 17:45 自动化标准执行顺序」小节 + 常见坑 14/15/16，并修正了旧描述里过时的自动化步骤序号。

## 2026-09-21 17:45
- 任务：期限结构刷新 → 利润快照 + 资金流向 → sync_to_site --push → 状态/告警。
- 结果：**全部成功**，无失败告警。
  - 期限结构：59/59 成功，term_date=2026-09-21；每个品种合约数由"一键下载"的 6 条补齐到 10-35 条，主力按**持仓量最大**修正。
  - 资金流向：59 品种，asof 2026-09-21；净流入前三 BU/JM/SP，净流出前三 AU/AG/SC。
  - 产业利润快照：35 品种全部 asof=2026-09-21，note/src 依 9-21 公开源（华安/格林大华/国都/福能/光大/上海中期/瑞达/先锋 + Mysteel/SMM/隆众/CCF/卓创/生意社/内蒙古粮储局）重写；利润档位无变动；cost 无同口径新值→一律保留原值。
  - 推送：直连不通（3s 探测即跳过）→ 走代理 127.0.0.1:7890 成功；commit da3974b / 55f1a70 / 4fd5903，REMOTE_V=202609211756。
- **本次最大变更：东财行情源整体迁移**
  1. `push2*` 全部 7 个域名当日**同时被掐**（TLS 通、请求发出后空回复 RemoteDisconnected），走代理/直连/沙箱内外部都一样，成功率 ~0-5% —— 不是本机代理问题。
  2. 改用 **`futsseapi.eastmoney.com/list/<mkt>`**（`Referer: https://futures.eastmoney.com/`，`pageSize=500` 一次拿全交易所全部合约，字段含 o/h/l/cje/ccl），实测 6/6 交易所稳定。
  3. `refresh_fundamentals.py`：新增 futsse 源 + **模块级 `_MARKET_CACHE`**（原来每个品种都重抓同一交易所，59 品种→现在只需 6 次请求）+ 持仓量列/`main_idx` 改用 f78。
  4. `fetch_moneyflow.py`：新增 `install_futsse_source(mod)` **运行时 monkey-patch** 服务的 `_fetch_market`（不动服务源码），并按 push2 字段名映射（f2/f5/f6/f15/f16/f18），CLV 算法不变；另加 `ensure_snap_dirs(mod)` 把 Library 真源 insert 进 `MF_SNAP_DIRS` —— 否则快照只写进 `~/Desktop/期货模板/期货研究数据/`，sync 读不到、线上停在 15:42 的旧副本。
- 关键处置（后续务必沿用）：
  1. 代理 7890 当时 **OPEN**，但东财 push2 照样不通 → **别再拿"代理通不通"当东财可用性的判据**，直接打 futsse 源。
  2. 同机 `www.eastmoney.com` / `quote.eastmoney.com` / `futures.eastmoney.com` 仍 200 ⇒ 只有 push2 被掐，可作为"行情源挂了 vs 本机故障"的判别。
  3. `快照更新状态.json` 的 `profit` 段仍无人写，需显式 `notify.write_status('profit',...)` 后再跑一次 push。
  4. "一键下载"写进真源的 term 是**截断版**（`len(labels)==6 and main_idx==2`），别当成已刷过。
  5. 数据唯一真源 = `~/Library/Application Support/期货服务/期货研究数据/`；任务描述里的 `~/Desktop/期货研究数据/` 已于 09-18 删除，脚本全部只认真源。
  6. 利润快照刷新沿用一次性脚本（json.load → 按 code 更新 asof/src/note → assert 品种集合不变 → 写盘 + .bak → json.load 校验），跑完即弃。

## 2026-09-18 18:01
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
