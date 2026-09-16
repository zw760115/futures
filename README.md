# 期货商品研究模板（库存 / 基差 / 期限结构 / 利润）

一个**纯前端、零依赖、单文件**的期货基本面研究工作台。所有数据与分析结果只存在浏览器 `localStorage`，**不上传任何服务器**（符合"资料不出本机"原则）。

## 功能

- 69 个期货品种一键切换（进阶版 = 库存 + 基差；高阶版 = 库存 + 基差 + 产业利润）
- 自动判定：库存分位、基差方向、趋势（去/累库）、期限结构、驱动多空、四象限定位
- 顶部「高阶分值排行」：最强多头 3 / 最弱空头 3
- 支持导入本地 JSON、手动录入、AI 讲解文案一键复制
- 行情服务对接（本地 / 东方财富）拉取实时基差与期限结构

## 本地使用

1. 直接双击 `index.html` 即可在浏览器打开。
2. 数据通过「导入 JSON」或手动填写进入；分析结论保存在本机浏览器，刷新不丢。

## 实时行情说明（部署到 GitHub Pages 后）

- **本地行情服务**（`127.0.0.1:8766`）：仅在你自己电脑上运行 `期货行情服务.py` 时可用，Pages 上无效。
- **东方财富 push2 行情**：从 `*.github.io` 跨域调用会被浏览器 CORS 拦截（东方财富不返回 `Access-Control-Allow-Origin`）。模板已内置「🌐 在线行情代理」开关：**填一个 Cloudflare Worker 地址即可让在线版也能拉实时行情**。本地（127.0.0.1）打开无需填，自动走本地服务优先。

### 给在线版加实时行情（Cloudflare Worker 反向代理，免费）

1. 登录 https://dash.cloudflare.com → 左侧 **Workers & Pages** → **创建 Worker**（免费额度足够）。
2. 把本仓库 `cloudflare/worker.js` 的内容**整段粘贴**进编辑器，点 **Save and Deploy**。
3. 记下分配的子域，形如 `https://em-proxy.<你的子域>.workers.dev`。
4. 打开已部署的页面 `https://<你的用户名>.github.io/futures/` → 顶部「🌐 在线行情代理」输入框粘贴该地址 → 点 **保存**。
5. 点「🔄 一键下载行情」，提示「正在经行情代理拉取实时行情」即成功。

> 原理：Worker 把 `https://<子域>.workers.dev/em/push2.eastmoney.com/...` 还原成 `https://push2.eastmoney.com/...` 并补 `Access-Control-Allow-Origin: *` 响应头，绕过浏览器 CORS。所有请求仍只到你自己的 Worker，数据不经过任何第三方。

## 部署到 GitHub Pages

1. 在 GitHub 新建一个**公开**仓库（如 `futures-research-template`）。
2. 把本目录内容（`index.html`、`.nojekyll`、`README.md`）推上去：
   ```bash
   cd futures-research-pages
   git init
   git add .
   git commit -m "init: 期货商品研究模板"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/<仓库名>.git
   git push -u origin main
   ```
3. 仓库 → Settings → Pages → Source 选 `main` 分支 `/ (root)` → Save。
4. 几分钟后访问 `https://<你的用户名>.github.io/<仓库名>/`。

> 仓库根目录已放 `.nojekyll`，避免 GitHub 的 Jekyll 处理影响页面。
