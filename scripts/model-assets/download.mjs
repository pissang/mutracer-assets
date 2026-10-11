import { fetch, EnvHttpProxyAgent } from 'undici';
import { archiveToGLB, attribution, decodeGLB, encodeGLB, MAX_ASSET_BYTES } from './gltf.mjs';

const dispatcher = new EnvHttpProxyAgent();
export const closeDownloads = () => dispatcher.close();
async function bytes(url, headers = {}) {
  const response = await fetch(url, { dispatcher, headers, signal: AbortSignal.timeout(180000) });
  if (!response.ok) {
    await response.body?.cancel();
    throw new Error(`Sketchfab request failed (HTTP ${response.status})`);
  }
  if (Number(response.headers.get('content-length')) > MAX_ASSET_BYTES) { await response.body?.cancel(); throw new Error('Download exceeds 512 MiB limit'); }
  const parts = [];
  let length = 0;
  for await (const chunk of response.body) {
    length += chunk.length;
    if (length > MAX_ASSET_BYTES) throw new Error('Download exceeds 512 MiB limit');
    parts.push(chunk);
  }
  return Buffer.concat(parts);
}
export async function downloadModel(uid, options = {}) {
  const api = `https://api.sketchfab.com/v3/models/${uid}`;
  const token = process.env.SKETCHFAB_ACCESS_TOKEN || process.env.SKETCHFAB_API_TOKEN;
  if (!token) throw new Error('Set SKETCHFAB_ACCESS_TOKEN or SKETCHFAB_API_TOKEN');
  const scheme = process.env.SKETCHFAB_ACCESS_TOKEN ? 'Bearer' : 'Token';
  const headers = { Authorization: `${scheme} ${token}` };
  const source = JSON.parse((await bytes(api, headers)).toString());
  const credit = attribution(source, options);
  const formats = JSON.parse((await bytes(`${api}/download`, headers)).toString());
  const format = formats.glb?.url ? 'glb' : 'gltf';
  if (!formats[format]?.url) throw new Error('No glTF/GLB download available');
  if (new URL(formats[format].url).protocol !== 'https:') throw new Error('Archive must use HTTPS');
  // Signed archive requests do not receive the API credential.
  const archive = await bytes(formats[format].url);
  let glb;
  if (format === 'glb') {
    const parsed = decodeGLB(archive);
    parsed.json.asset.extras = {...parsed.json.asset.extras,mutracerAttribution:credit};
    glb = encodeGLB(parsed.json,parsed.bin);
  } else glb = archiveToGLB(archive, credit);
  return { glb, credit, source };
}
