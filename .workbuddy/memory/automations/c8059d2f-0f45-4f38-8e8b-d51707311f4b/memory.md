# 自动化执行记录：刷新期货产业利润快照 + 资金流向快照 + 推送网页版

本文件只记录高层执行情况，不含完整产物内容。

## 2026-09-23 17:45（本次）
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
