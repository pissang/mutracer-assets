import path from 'node:path';
import { unzipSync } from 'fflate';

export const MAX_ASSET_BYTES = 512 * 1024 * 1024;
const align = (n) => (n + 3) & ~3;

export function modelUid(input) {
  const match = String(input).match(/(?:^|[-/])([a-f0-9]{32})(?:\/?(?:[?#].*)?)$/i);
  if (!match) throw new Error('Expected a Sketchfab model URL or 32-character UID');
  return match[1].toLowerCase();
}

export function attribution(model, { reviewOnly = false, nonCommercial = false } = {}) {
  const license = model.license;
  if (!license || !((license.slug === 'by' && /creativecommons\.org\/licenses\/by\/4\.0\/?$/.test(license.url)) ||
    (license.slug === 'cc0' && /creativecommons\.org\/publicdomain\/zero\/1\.0\/?$/.test(license.url)) ||
    ((reviewOnly || nonCommercial) && ['by-nc','by-nc-sa'].includes(license.slug) && new RegExp(`creativecommons\\.org/licenses/${license.slug}/4\\.0/?$`).test(license.url)) ||
    (reviewOnly && license.slug === 'free-st' && /^https:\/\/sketchfab\.com\/licenses\/?$/.test(license.url)))) {
    throw new Error(`Unsupported license for ${model.uid}: NC requires a noncommercial decision; Free Standard is local-only`);
  }
  if (!model.isDownloadable) throw new Error(`Model ${model.uid} is not downloadable`);
  return {
    title: model.name,
    author: model.user.displayName || model.user.username,
    authorUrl: model.user.profileUrl,
    sourceUrl: model.viewerUrl,
    license: {by:'CC-BY 4.0','by-nc':'CC-BY-NC 4.0','by-nc-sa':'CC-BY-NC-SA 4.0','free-st':'Sketchfab Free Standard',cc0:'CC0'}[license.slug],
    licenseUrl: license.url,
    // Preserve the creator's description, including additional credits.
    description: model.description || '',
    changes: 'Repacked as a single GLB without changing geometry or materials; preview rendered with MuTracer.'
  };
}

export function unpackArchive(bytes) {
  let expanded = 0;
  return unzipSync(bytes, {
    filter(file) {
      if (/\\|^\/|^[a-z]:|(^|\/)\.\.(\/|$)/i.test(file.name)) throw new Error('Unsafe ZIP entry');
      expanded += file.originalSize;
      if (expanded > MAX_ASSET_BYTES) throw new Error('ZIP exceeds the expanded size limit');
      return !file.name.endsWith('/');
    }
  });
}

function resource(files, base, uri) {
  if (/^data:/i.test(uri)) {
    const match = uri.match(/^data:([^;,]+)?(;base64)?,([\s\S]*)$/i);
    if (!match) throw new Error('Invalid data URI');
    return { bytes: Buffer.from(match[2] ? match[3] : decodeURIComponent(match[3]), match[2] ? 'base64' : 'utf8'), mime: match[1] };
  }
  const decoded = decodeURIComponent(uri);
  if (/^[a-z][a-z\d+.-]*:|^\/|\\|[?#]/i.test(decoded)) throw new Error('Only archive-relative glTF resources are supported');
  const key = path.posix.normalize(path.posix.join(base, decoded));
  if (key === '..' || key.startsWith('../') || !files[key]) throw new Error(`Missing or unsafe glTF resource: ${uri}`);
  return { bytes: Buffer.from(files[key]), mime: { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.ktx2': 'image/ktx2' }[path.posix.extname(key).toLowerCase()] };
}

/** Repack bytes directly, preserving glTF extensions and material parameters. */
export function packGLTF(files, entry, credit) {
  const json = JSON.parse(Buffer.from(files[entry]).toString('utf8'));
  if (json.asset?.version !== '2.0') throw new Error('Only glTF 2.0 is supported');
  const parts = [];
  let length = 0;
  const append = (bytes) => {
    const offset = length;
    parts.push(bytes, Buffer.alloc(align(bytes.length) - bytes.length));
    length += align(bytes.length);
    if (length > MAX_ASSET_BYTES) throw new Error('GLB exceeds the size limit');
    return offset;
  };
  const offsets = (json.buffers || []).map((buffer) => {
    if (!buffer.uri) throw new Error('glTF buffer is missing its URI');
    const { bytes } = resource(files, path.posix.dirname(entry), buffer.uri);
    if (bytes.length < buffer.byteLength) throw new Error('Truncated glTF buffer');
    return append(bytes.subarray(0, buffer.byteLength));
  });
  const relocate = (ref) => {
    if (!Number.isInteger(ref.buffer) || offsets[ref.buffer] === undefined) throw new Error('Invalid glTF buffer reference');
    ref.byteOffset = (ref.byteOffset || 0) + offsets[ref.buffer];
    ref.buffer = 0;
  };
  for (const view of json.bufferViews || []) {
    relocate(view);
    if (view.extensions?.EXT_meshopt_compression) relocate(view.extensions.EXT_meshopt_compression);
  }
  json.bufferViews ||= [];
  for (const image of json.images || []) {
    if (!image.uri) continue;
    const { bytes, mime } = resource(files, path.posix.dirname(entry), image.uri);
    image.mimeType ||= mime;
    if (!image.mimeType) throw new Error('Unknown image MIME type');
    image.bufferView = json.bufferViews.length;
    json.bufferViews.push({ buffer: 0, byteOffset: append(bytes), byteLength: bytes.length });
    delete image.uri;
  }
  json.buffers = [{ byteLength: length }];
  json.asset.extras = { ...json.asset.extras, mutracerAttribution: credit };
  return encodeGLB(json, Buffer.concat(parts));
}

export function encodeGLB(json, bin) {
  const encoded = Buffer.from(JSON.stringify(json));
  const jsonChunk = Buffer.alloc(align(encoded.length), 0x20);
  encoded.copy(jsonChunk);
  const output = Buffer.alloc(12 + 8 + jsonChunk.length + 8 + bin.length);
  output.writeUInt32LE(0x46546c67, 0);
  output.writeUInt32LE(2, 4);
  output.writeUInt32LE(output.length, 8);
  output.writeUInt32LE(jsonChunk.length, 12);
  output.writeUInt32LE(0x4e4f534a, 16);
  jsonChunk.copy(output, 20);
  const binHeader = 20 + jsonChunk.length;
  output.writeUInt32LE(bin.length, binHeader);
  output.writeUInt32LE(0x004e4942, binHeader + 4);
  bin.copy(output, binHeader + 8);
  return output;
}

export function decodeGLB(bytes) {
  if (bytes.length < 20 || bytes.readUInt32LE(0) !== 0x46546c67 || bytes.readUInt32LE(4) !== 2 || bytes.readUInt32LE(8) !== bytes.length) throw new Error('Invalid GLB');
  let json, bin = Buffer.alloc(0);
  for (let offset = 12; offset < bytes.length;) {
    const length = bytes.readUInt32LE(offset), type = bytes.readUInt32LE(offset + 4);
    if (offset + 8 + length > bytes.length) throw new Error('Truncated GLB chunk');
    const chunk = bytes.subarray(offset + 8, offset + 8 + length);
    if (type === 0x4e4f534a) json = JSON.parse(chunk.toString('utf8'));
    else if (type === 0x004e4942) bin = chunk;
    offset += 8 + length;
  }
  if (!json || json.asset?.version !== '2.0' || json.buffers?.[0]?.uri ||
    json.buffers?.slice(1).some(buffer=>buffer.uri || !buffer.extensions?.EXT_meshopt_compression?.fallback)) throw new Error('Unsupported GLB layout');
  return { json, bin };
}

export function archiveToGLB(bytes, credit) {
  const files = unpackArchive(bytes);
  const entries = Object.keys(files).filter((name) => /\.gltf$/i.test(name));
  const entry = entries.find((name) => /(^|\/)scene\.gltf$/i.test(name)) || (entries.length === 1 && entries[0]);
  if (!entry) throw new Error('ZIP must contain one glTF scene (or scene.gltf)');
  return packGLTF(files, entry, credit);
}
