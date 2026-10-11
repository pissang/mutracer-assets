import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, readdir, rm } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import os from 'node:os';
import path from 'node:path';
import { root } from '../scripts/check-assets.mjs';

test('review switches delivery, rejects oversized GitHub files, and removes models with recovery files', async () => {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'mutracer-review-'));
  const save = (name, value) => writeFile(path.join(temp, name), JSON.stringify(value));
  await save('models.json', [{ id: 'coffee', uid: 'uid' }, { id: 'big', uid: 'biguid' }]);
  await save('catalog.json', [{ id: 'coffee', delivery: 'github', bytes: 4 }, { id: 'big', delivery: 'r2', bytes: 21000000 }]);
  await save('presets.json', ['old catalog']);
  await mkdir(path.join(temp, 'assets/coffee'), { recursive: true });
  await writeFile(path.join(temp, 'assets/coffee/model.glb'), 'glb!');
  const child = spawn(process.execPath, ['scripts/review.mjs'], { cwd: root, env: { ...process.env, PORT: '0', REVIEW_DATA_ROOT: temp }, stdio: ['ignore', 'pipe', 'pipe'] });
  try {
    const base = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Review startup timeout')), 10000);
      child.stdout.on('data', (chunk) => {
        const match = chunk.toString().match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) { clearTimeout(timer); resolve(match[0]); }
      });
      child.once('error', (error) => { clearTimeout(timer); reject(error); });
    });
    const post = (id, action, origin = base) => fetch(`${base}/api/edit`, { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: origin }, body: JSON.stringify({ id, action }) });
    assert.equal((await post('coffee', 'remove', 'http://evil.example')).status, 403);
    assert.equal((await post('big', 'github')).status, 400);
    assert.equal((await post('coffee', 'r2')).status, 200);
    assert.equal(await readFile(path.join(temp, 'work/r2/coffee/model.glb'), 'utf8'), 'glb!');
    assert.equal((await post('coffee', 'github')).status, 200);
    assert.equal(await readFile(path.join(temp, 'assets/coffee/model.glb'), 'utf8'), 'glb!');
    assert.equal((await post('coffee', 'remove')).status, 200);
    const models = JSON.parse(await readFile(path.join(temp, 'models.json'), 'utf8'));
    assert.deepEqual(models.map((model) => model.id), ['big']);
    const catalog = JSON.parse(await readFile(path.join(temp, 'catalog.json'), 'utf8'));
    assert.deepEqual(catalog.map((model) => model.id), ['big']);
    const trash = await readdir(path.join(temp, 'work/removed'));
    assert.equal(await readFile(path.join(temp, 'work/removed', trash[0], 'assets/model.glb'), 'utf8'), 'glb!');
    await assert.rejects(readFile(path.join(temp, 'presets.json')), { code: 'ENOENT' });
  } finally {
    const ended = once(child, 'exit');
    child.kill('SIGTERM');
    await ended;
    await rm(temp, { recursive: true, force: true });
  }
});
