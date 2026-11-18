export function backendOrigin(value) {
  let url;
  try { url = new URL(value); }
  catch { throw new Error('BACKEND_ORIGIN must be a bare HTTPS origin'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('BACKEND_ORIGIN must be a bare HTTPS origin');
  }
  return url.origin;
}
