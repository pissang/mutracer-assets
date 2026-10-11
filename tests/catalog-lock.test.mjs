import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { recordR2Upload, saveJSON, withCatalogLock } from '../scripts/model-assets/catalog-lock.mjs';

test('completed uploads preserve removals and do not restore stale catalog snapshots', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'mutracer-catalog-'));
  const file = path.join(root, 'catalog.json');
  try {
    await saveJSON(file, [{ id: 'keep', sha256: 'hash', delivery: 'r2' }, { id: 'remove', sha256: 'old', delivery: 'r2' }]);
    const deletion = withCatalogLock(root, async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
      const current = JSON.parse(await readFile(file, 'utf8'));
      await saveJSON(file, current.filter((entry) => entry.id !== 'remove'));
    });
    const upload = recordR2Upload(root, 'keep', 'hash', { r2Bucket: 'bucket', r2Key: 'key' });
    await Promise.all([deletion, upload]);
    assert.equal(await recordR2Upload(root, 'remove', 'old', { r2Bucket: 'bucket', r2Key: 'oldkey' }), false);
    const entries = JSON.parse(await readFile(file, 'utf8'));
    assert.equal(entries.length, 1);
    assert.equal(entries[0].r2Key, 'key');
    assert.equal(await recordR2Upload(root, 'keep', 'changedhash', { r2Bucket: 'bucket', r2Key: 'badkey' }), false);
  } finally { await rm(root, { recursive: true, force: true }); }
});
