import { execFileSync } from 'node:child_process';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { canPublish, LOCAL_LICENSES } from './model-assets/licenses.mjs';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// Decimal MB is deliberately conservative for jsDelivr's documented limits.
export const MAX_FILE = 20_000_000;
export const MAX_PACKAGE = 150_000_000;

export function checkSizes(files) {
  let total = 0;
  for (const file of files) {
    if (file.size > MAX_FILE) throw new Error(`${file.path}: ${(file.size / 1e6).toFixed(2)} MB exceeds jsDelivr's 20 MB file limit`);
    total += file.size;
  }
  if (total > MAX_PACKAGE) throw new Error(`Repository snapshot is ${(total / 1e6).toFixed(2)} MB, exceeding jsDelivr's 150 MB limit`);
  return total;
}

export async function checkRepository() {
  const files = [...new Set(execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'], { cwd: root }).toString().split('\0').filter(Boolean))];
  const measured = [];
  for (const file of files) {
    try { measured.push({ path: file, size: (await stat(path.join(root, file))).size }); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  const total = checkSizes(measured);
  const catalog = JSON.parse(await readFile(path.join(root, 'catalog.json'), 'utf8'));
  const ids = new Set();
  for (const entry of catalog) {
    if (!/^[a-z0-9-]+$/.test(entry.id) || ids.has(entry.id)) throw new Error('Catalog IDs must be unique lowercase slugs');
    ids.add(entry.id);
    const folder = path.join(root, entry.reviewOnly ? 'work/review' : 'assets', entry.id);
    if (entry.reviewOnly && entry.delivery !== 'local') throw new Error(`Review-only models must stay local: ${entry.id}`);
    if (entry.delivery === 'github' || entry.delivery === 'local') {
      const glb = await readFile(path.join(folder, 'model.glb'));
      if (glb.readUInt32LE(0) !== 0x46546c67 || glb.readUInt32LE(8) !== glb.length) throw new Error(`Invalid GLB: ${entry.id} (Git LFS is unsupported)`);
    } else if (entry.delivery === 'external') {
      if (entry.url !== null && (typeof entry.url !== 'string' || !entry.url.startsWith('https://'))) throw new Error(`Invalid external model URL: ${entry.id}`);
    } else if (entry.delivery !== 'r2') throw new Error(`Invalid delivery: ${entry.id}`);
    const webp = await readFile(path.join(folder, 'thumbnail.webp'));
    if (webp.toString('ascii', 0, 4) !== 'RIFF' || webp.toString('ascii', 8, 12) !== 'WEBP') throw new Error(`Invalid WebP: ${entry.id}`);
    const credit = JSON.parse(await readFile(path.join(folder, 'attribution.json'), 'utf8'));
    if (credit.license !== entry.license || !(entry.reviewOnly ? LOCAL_LICENSES.includes(credit.license) : canPublish(entry)) || !credit.author || !credit.licenseUrl || !credit.sourceUrl) throw new Error(`Missing license/credit or delivery permission: ${entry.id}`);
  }
  return { models: catalog.length, bytes: total };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(await checkRepository());
}
