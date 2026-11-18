export function backendOrigin(value) {
  let url;
  try { url = new URL(value); }
  catch { throw new Error('BACKEND_ORIGIN must be a bare HTTPS origin'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('BACKEND_ORIGIN must be a bare HTTPS origin');
  }
  return url.origin;
}

export function publicHtml(html, key = '') {
  const escaped = key.replace(/[&"<>]/g, character => ({'&': '&amp;', '"': '&quot;', '<': '&lt;', '>': '&gt;'}[character]));
  return html.replace('<meta name="kakao-map-app-key" content="">', `<meta name="kakao-map-app-key" content="${escaped}">`);
}

export function deploymentConfig(value) {
  const origin = backendOrigin(value);
  return {
    version: 3,
    routes: [
      {
        src: '/api/(.*)',
        dest: `${origin}/api/$1`,
        headers: {'Cache-Control': 'no-store', 'x-vercel-enable-rewrite-caching': '0'},
        transforms: [
          {type: 'request.headers', op: 'set', target: {key: 'ngrok-skip-browser-warning'}, args: '1'}
        ]
      },
      {src: '/dev', dest: '/dev.html'},
      {src: '/', dest: '/index.html'},
      {handle: 'filesystem'}
    ]
  };
}
