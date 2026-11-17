import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
const types = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json'};
createServer(async (req, res) => {
  try {
    const path = new URL(req.url, 'http://localhost').pathname;
    const file = new URL('.' + (path === '/' ? '/index.html' : path === '/dev' ? '/dev.html' : path), import.meta.url);
    const data = await readFile(file);
    res.writeHead(200, {'Content-Type':types[file.pathname.slice(file.pathname.lastIndexOf('.'))] || 'text/plain'});
    res.end(data);
  } catch { res.writeHead(404); res.end('Not found'); }
}).listen(5173, '127.0.0.1', () => console.log('Frontend: http://localhost:5173/?mode=fixture'));
