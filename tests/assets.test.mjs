import { test } from 'node:test';
import assert from 'node:assert/strict';
import { zipSync, strToU8 } from 'fflate';
import { archiveToGLB, attribution, modelUid, unpackArchive } from '../scripts/model-assets/gltf.mjs';
import { checkSizes, MAX_FILE, MAX_PACKAGE } from '../scripts/check-assets.mjs';
import { buildCatalog } from '../scripts/build-catalog.mjs';

const credit = attribution({ uid: '9ccda2fddba846e6ba97eb774b8a09c6', name: 'Coffee Maker', isDownloadable: true,
  user: { displayName: 'Author', profileUrl: 'https://sketchfab.com/author' }, viewerUrl: 'https://sketchfab.com/model', description: 'Concept credit',
  license: { slug: 'by', url: 'https://creativecommons.org/licenses/by/4.0/' } });
test('packs GLB resources and retains physical materials and attribution', () => {
  const files = {
    'scene.gltf': strToU8(JSON.stringify({ asset: { version: '2.0' }, buffers: [{ uri: 'a.bin', byteLength: 3 }, { uri: 'b.bin', byteLength: 4 }],
      bufferViews: [{ buffer: 1, byteOffset: 1, byteLength: 2, extensions: { EXT_meshopt_compression: { buffer: 1, byteOffset: 2 } } }],
      images: [{ uri: 'texture.png' }], materials: [{ extensions: { KHR_materials_transmission: { transmissionFactor: 0.9 } } }] })),
    'a.bin': new Uint8Array([1,2,3]), 'b.bin': new Uint8Array([4,5,6,7]), 'texture.png': new Uint8Array([8,9])
  };
  const glb = archiveToGLB(zipSync(files), credit);
  assert.equal(glb.readUInt32LE(8), glb.length);
  const length = glb.readUInt32LE(12);
  const json = JSON.parse(glb.toString('utf8', 20, 20 + length));
  assert.equal(json.bufferViews[0].byteOffset, 5);
  assert.equal(json.bufferViews[0].extensions.EXT_meshopt_compression.byteOffset, 6);
  assert.equal(json.images[0].bufferView, 1);
  assert.equal(json.buffers[0].uri, undefined);
  assert.equal(json.materials[0].extensions.KHR_materials_transmission.transmissionFactor, 0.9);
  assert.deepEqual(json.asset.extras.mutracerAttribution, credit);
});
test('rejects unsupported licenses and unsafe archive paths', () => {
  assert.throws(() => attribution({ license: { slug: 'by-nc', url: credit.licenseUrl } }), /Unsupported/);
  assert.throws(() => unpackArchive(zipSync({ '../secret': strToU8('bad') })), /Unsafe/);
  assert.equal(modelUid('https://sketchfab.com/3d-models/coffee-9ccda2fddba846e6ba97eb774b8a09c6'), '9ccda2fddba846e6ba97eb774b8a09c6');
});
test('enforces both per-file and snapshot limits without reading large fixtures', () => {
  assert.equal(checkSizes([{ path: 'model.glb', size: MAX_FILE }]), MAX_FILE);
  assert.throws(() => checkSizes([{ path: 'model.glb', size: MAX_FILE + 1 }]), /20 MB/);
  assert.throws(() => checkSizes(Array.from({ length: 8 }, (_, i) => ({ path: `${i}.glb`, size: MAX_PACKAGE / 8 + 1 }))), /150 MB/);
});
test('builds mixed delivery URLs with all screenshots on a pinned GitHub version', () => {
  const entries = [{ id: 'coffee', delivery: 'github', bytes: 100 }, { id: 'bottle', delivery: 'r2', r2Url: 'https://assets.example/bottle.glb', bytes: 30000000 }];
  const output = buildCatalog(entries, 'v0.1.0');
  assert.equal(output[0].url, 'https://cdn.jsdelivr.net/gh/pissang/mutracer-assets@v0.1.0/assets/coffee/model.glb');
  assert.equal(output[1].url, entries[1].r2Url);
  assert.match(output[1].thumbnail, /^https:\/\/cdn.jsdelivr.net\/gh\/pissang\/mutracer-assets@v0.1.0\//);
  assert.throws(() => buildCatalog(entries, 'main'), /immutable/);
  assert.throws(() => buildCatalog([{ id: 'pending', delivery: 'r2' }], 'v0.1.0'), /upload/);
});
