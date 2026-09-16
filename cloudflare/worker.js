// ============================================================
//  东方财富行情反向代理 (Cloudflare Worker)
//  用途：让 GitHub Pages 等静态站点能跨域拉取东方财富实时行情
//        （东方财富接口不返回 Access-Control-Allow-Origin，直连会被浏览器 CORS 拦截）
//
//  部署（无需 wrangler，网页即可）：
//   1. 登录 https://dash.cloudflare.com → 左侧 Workers & Pages → 创建 Worker
//   2. 把本文件内容粘贴进编辑器，Save and Deploy
//   3. 记下分配的子域，形如 https://em-proxy.<你的子域>.workers.dev
//
//  前端用法（在期货模板「🌐 在线行情代理」输入框粘贴该地址即可）：
//    原地址  https://push2.eastmoney.com/api/qt/clist/get?...
//    改为    https://em-proxy.<子域>.workers.dev/em/push2.eastmoney.com/api/qt/clist/get?...
//    本 Worker 会剥掉 /em/ 前缀，还原成 https://push2.eastmoney.com/... 并补 CORS 头
// ============================================================

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 健康检查 / 说明
    if (url.pathname === '/' || url.pathname === '/health') {
      return new Response(
        'EM Quote Proxy OK.\n用法: /em/<eastmoney-host><path>?query\n例: /em/push2.eastmoney.com/api/qt/clist/get?fs=m:113',
        { headers: { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'text/plain; charset=utf-8' } }
      );
    }

    // 仅代理 /em/<host><path>
    if (!url.pathname.startsWith('/em/')) {
      return new Response('Bad path. 期望 /em/push2.eastmoney.com/api/qt/clist/get?...', { status: 400 });
    }

    //  /em/push2.eastmoney.com/api/qt/...  ->  https://push2.eastmoney.com/api/qt/...
    const rest = url.pathname.slice('/em'.length); // /push2.eastmoney.com/api/qt/...
    const target = 'https://' + rest + url.search;

    // 服务端代发：带浏览器常见头，避免东方财富按 referer 校验返回 40x
    const upstream = await fetch(target, {
      method: request.method,
      redirect: 'follow',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
        'Referer': 'https://quote.eastmoney.com/',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9'
      }
    });

    // 透传响应体 + 状态，补 CORS 头（前端是简单 GET，不触发 preflight）
    const resp = new Response(upstream.body, upstream);
    resp.headers.set('Access-Control-Allow-Origin', '*');
    resp.headers.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
    resp.headers.set('Cache-Control', 'no-store');
    return resp;
  }
};
