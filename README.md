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
- **东方财富 push2 行情**：从 `*.github.io` 跨域调用可能被浏览器 CORS 拦截。若需要在线实时行情，可加一个 Cloudflare Worker 做反向代理（将 `push2.eastmoney.com` 代理到同源），再改模板里的接口地址即可。

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
