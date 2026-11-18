import {cp, mkdir} from 'node:fs/promises';
import {join} from 'node:path';

export async function copyStatic(root, output) {
  await mkdir(output, {recursive: true});
  for (const name of ['index.html', 'dev.html', 'styles.css', 'src', 'fixtures']) {
    await cp(join(root, name), join(output, name), {recursive: true});
  }
}
