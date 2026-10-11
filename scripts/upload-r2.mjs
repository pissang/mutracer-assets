import { parseArgs } from 'node:util';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { root } from './check-assets.mjs';
import { recordR2Upload } from './model-assets/catalog-lock.mjs';
import { canPublish } from './model-assets/licenses.mjs';

const { values } = parseArgs({ options: { bucket: { type: 'string' }, 'public-base': { type: 'string' }, model: { type: 'string', multiple: true }, force: { type: 'boolean' } } });
const bucket = values.bucket || process.env.R2_BUCKET;
const publicBase = values['public-base'] || process.env.R2_PUBLIC_BASE_URL;
if (!bucket) throw new Error('Pass --bucket (or R2_BUCKET)');
const base = publicBase ? new URL(publicBase) : null;
if (base && (base.protocol !== 'https:' || base.username || base.password || base.search || base.hash)) throw new Error('R2 public base must be a clean HTTPS URL');
const catalogFile = path.join(root, 'catalog.json');
const entries = JSON.parse(await readFile(catalogFile, 'utf8'));
if (values.model?.some((id) => !entries.some((entry) => entry.id === id && entry.delivery === 'r2'))) throw new Error('--model must select an existing R2 model ID');
for (const candidate of entries) {
  const entry = JSON.parse(await readFile(catalogFile, 'utf8')).find((current) => current.id === candidate.id);
  if (!entry) continue;
  if (entry.delivery !== 'r2' || (values.model && !values.model.includes(entry.id))) continue;
  if (!canPublish(entry)) throw new Error(`Not eligible for public upload: ${entry.id}`);
  if (!/^[a-z0-9-]+$/.test(entry.id)) throw new Error('Invalid model ID');
  const file = path.join(root, 'work/r2', entry.id, 'model.glb');
  const bytes = await readFile(file);
  if (bytes.length > 300 * 1024 ** 2) throw new Error(`${entry.id}: above Wrangler's 300 MiB limit; use an S3 multipart uploader`);
  const hash = createHash('sha256').update(bytes).digest('hex');
  if (entry.sha256 && entry.sha256 !== hash) throw new Error(`GLB changed after import: ${entry.id}`);
  const key = `models/${entry.id}/${hash.slice(0, 24)}/model.glb`;
  const alreadyUploaded = entry.r2Bucket === bucket && entry.r2Key === key;
  if (!alreadyUploaded || values.force) {
    console.log(`Uploading GLB for ${entry.id}`);
    await new Promise((resolve, reject) => {
    const env = { ...process.env, CI: 'true', WRANGLER_SEND_METRICS: 'false' };
    delete env.SKETCHFAB_ACCESS_TOKEN;
    delete env.SKETCHFAB_API_TOKEN;
    const child = spawn(process.execPath, [path.join(root, 'node_modules/wrangler/bin/wrangler.js'), 'r2', 'object', 'put', `${bucket}/${key}`, '--remote', '--file', file,
      '--storage-class', 'Standard', '--content-type', 'model/gltf-binary', '--cache-control', 'public, max-age=31536000, immutable'], { cwd: root, env, stdio: 'inherit' });
    child.on('error', reject);
    child.on('close', (code) => code === 0 ? resolve() : reject(new Error(`R2 upload failed for ${entry.id}`)));
    });
  } else console.log(`Already uploaded: ${entry.id}`);
  const metadata = { r2Bucket: bucket, r2Key: key };
  if (base) metadata.r2Url = `${base.href.replace(/\/+$/, '')}/${key}`;
  await recordR2Upload(root, entry.id, hash, metadata);
}
console.log(base ? 'R2 object paths and public URLs saved to catalog.json.' : 'R2 object paths saved to catalog.json. Set --public-base after configuring the public domain.');
