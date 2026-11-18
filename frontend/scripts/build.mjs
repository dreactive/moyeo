import {readFile, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {copyStatic} from './build-files.mjs';
import {deploymentConfig, publicHtml} from './deployment.mjs';

export async function buildFrontend(root, env) {
  const config = deploymentConfig(env.BACKEND_ORIGIN);
  const output = join(root, '.vercel', 'output');
  await copyStatic(root, join(output, 'static'));
  const index = join(output, 'static', 'index.html');
  await writeFile(index, publicHtml(await readFile(index, 'utf8'), env.KAKAO_JAVASCRIPT_KEY));
  await writeFile(join(output, 'config.json'), JSON.stringify(config, null, 2));
}

if (import.meta.main) await buildFrontend(fileURLToPath(new URL('../', import.meta.url)), process.env);
