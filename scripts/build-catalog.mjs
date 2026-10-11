import { parseArgs } from 'node:util';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { root, checkRepository } from './check-assets.mjs';
import { canPublish } from './model-assets/licenses.mjs';
import { withCatalogLock, saveJSON } from './model-assets/catalog-lock.mjs';

export function buildCatalog(entries, version, repository = 'pissang/mutracer-assets') {
  if (!/^(?:v?\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?|[a-f0-9]{40})$/i.test(version)) throw new Error('Use an immutable semver tag or full commit SHA');
  if (!/^[\w.-]+\/[\w.-]+$/.test(repository)) throw new Error('Invalid GitHub repository');
  const base = `https://cdn.jsdelivr.net/gh/${repository}@${version}`;
  return entries.filter(entry=>!entry.reviewOnly).map((entry) => {
    if (!/^[a-z0-9-]+$/.test(entry.id)) throw new Error('Invalid model ID');
    if (entry.license && !canPublish(entry)) throw new Error(`Not eligible for public presets: ${entry.id}`);
    if (entry.delivery === 'r2' && !entry.r2Url) throw new Error(`${entry.id}: upload its GLB and set the R2 public URL before generating the catalog`);
    if (entry.delivery === 'external' && entry.url !== null &&
      (typeof entry.url !== 'string' || !entry.url.startsWith('https://'))) throw new Error(`${entry.id}: invalid external model URL`);
    return { id: entry.id, name: entry.name, tag: entry.tag, url: entry.delivery === 'external' ? entry.url : entry.delivery === 'r2' ? entry.r2Url : `${base}/assets/${entry.id}/model.glb`,
      thumbnail: `${base}/assets/${entry.id}/thumbnail.webp`, license: entry.license, credit: entry.credit,
      sourceUrl: entry.sourceUrl, licenseUrl: entry.licenseUrl, attributionUrl: `${base}/assets/${entry.id}/attribution.json`,
      ...(entry.bytes ? {sizeMB: Number((entry.bytes / 1024 ** 2).toFixed(2))} : {}), ...(entry.nonCommercial===true ? {nonCommercial:true} : {}), ...(entry.camera ? {camera:entry.camera} : {}) };
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { values } = parseArgs({ options: { version: { type: 'string' }, repository: { type: 'string', default: 'pissang/mutracer-assets' } } });
  if (!values.version) throw new Error('Pass --version v0.1.0 (create and push that tag manually after reviewing)');
  await withCatalogLock(root, async () => {
    await checkRepository();
    const entries = JSON.parse(await readFile(path.join(root, 'catalog.json'), 'utf8'));
    const presets = buildCatalog(entries, values.version, values.repository);
    await saveJSON(path.join(root, 'presets.json'), presets);
  });
  console.log(`Wrote presets.json for ${values.version}. Commit and push files and tag manually.`);
}
