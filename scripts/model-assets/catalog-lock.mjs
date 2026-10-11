import { open, readFile, mkdir, rm, writeFile, rename } from 'node:fs/promises';
import path from 'node:path';

/** Coordinate CLI uploads and review edits without resurrecting removed models. */
export async function withCatalogLock(root, action) {
  const work = path.join(root, 'work');
  await mkdir(work, { recursive: true });
  const file = path.join(work, 'catalog.lock');
  const deadline = Date.now() + 30000;
  let handle;
  while (!handle) {
    try { handle = await open(file, 'wx'); }
    catch (error) {
      if (error.code !== 'EEXIST') throw error;
      const owner = Number(await readFile(file, 'utf8').catch(() => ''));
      if (owner) {
        try { process.kill(owner, 0); }
        catch (error) { if (error.code === 'ESRCH') { await rm(file, { force: true }); continue; } }
      }
      if (Date.now() > deadline) throw new Error('Timed out waiting for a catalog edit');
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  }
  try {
    await handle.writeFile(String(process.pid));
    return await action();
  } finally {
    await handle.close();
    await rm(file, { force: true });
  }
}

export async function saveJSON(file, value) {
  const temp = `${file}.${process.pid}.tmp`;
  try {
    await writeFile(temp, JSON.stringify(value, null, 2) + '\n');
    await rename(temp, file);
  } finally { await rm(temp, { force: true }); }
}

export async function recordR2Upload(root, id, hash, metadata) {
  return withCatalogLock(root, async () => {
    const file = path.join(root, 'catalog.json');
    const catalog = JSON.parse(await readFile(file, 'utf8'));
    const entry = catalog.find((entry) => entry.id === id && entry.delivery === 'r2' && (!entry.sha256 || entry.sha256 === hash));
    if (!entry) return false;
    if (entry.r2Bucket !== metadata.r2Bucket || entry.r2Key !== metadata.r2Key) delete entry.r2Url;
    Object.assign(entry, metadata);
    await saveJSON(file, catalog);
    await rm(path.join(root, 'presets.json'), { force: true });
    return true;
  });
}
