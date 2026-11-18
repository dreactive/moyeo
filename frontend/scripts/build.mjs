import {readFile, writeFile, rm} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {copyStatic} from './build-files.mjs';
import {deploymentConfig, publicHtml} from './deployment.mjs';

export async function buildFrontend(root, env) {
  const config = deploymentConfig(env.BACKEND_ORIGIN);
  const output = resolve(root, '.vercel', 'output');
  // Only reset the generated output directory beneath the frontend root.
  await rm(output, {recursive: true, force: true});
  await copyStatic(root, join(output, 'static'));
  const index = join(output, 'static', 'index.html');
  await writeFile(index, publicHtml(await readFile(index, 'utf8'), env.KAKAO_JAVASCRIPT_KEY));
  await writeFile(join(output, 'config.json'), JSON.stringify(config, null, 2));
}

if (import.meta.main) await buildFrontend(fileURLToPath(new URL('../', import.meta.url)), process.env);
