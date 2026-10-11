import http from 'node:http';
import { readFile, mkdir, rename, cp, rm } from 'node:fs/promises';
import path from 'node:path';
import { root, MAX_FILE } from './check-assets.mjs';
import { withCatalogLock, saveJSON } from './model-assets/catalog-lock.mjs';

const dataRoot = process.env.REVIEW_DATA_ROOT || root;
const catalogFile = path.join(dataRoot, 'catalog.json');
const modelsFile = path.join(dataRoot, 'models.json');
const load = async (file) => JSON.parse(await readFile(file, 'utf8'));
const save = saveJSON;
// Serialize mutations to prevent two button presses overwriting catalog edits.
let mutations = Promise.resolve();
const page = await readFile(path.join(root, 'scripts/review.html'));
const server = http.createServer(async (req, res) => {
  try {
    const port = server.address()?.port;
    if (![`127.0.0.1:${port}`, `localhost:${port}`].includes(req.headers.host)) { res.writeHead(403); res.end(); return; }
    const url = new URL(req.url, `http://${req.headers.host}`);
    if (req.method === 'GET' && url.pathname === '/') { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(page); return; }
    if (req.method === 'GET' && url.pathname === '/api/models') {
      const [catalog, selected] = await Promise.all([load(catalogFile), load(modelsFile)]);
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ models: catalog, pending: selected.filter((m) => !catalog.some((c) => c.id === m.id)), maxFile: MAX_FILE })); return;
    }
    const thumbnail = url.pathname.match(/^\/assets\/([a-z0-9-]+)\/thumbnail\.webp$/);
    if (req.method === 'GET' && thumbnail) {
      const entry=(await load(catalogFile)).find(model=>model.id===thumbnail[1]);
      if (!entry) {res.writeHead(404);res.end();return;}
      res.setHeader('Content-Type', 'image/webp'); res.end(await readFile(path.join(dataRoot,entry.reviewOnly ? 'work/review' : 'assets',thumbnail[1],'thumbnail.webp')));return;
    }
    if (req.method === 'POST' && url.pathname === '/api/edit') {
      // Same-origin browser requests only, with JSON bodies; bind to loopback.
      if (req.headers.origin !== `http://${req.headers.host}` || !req.headers['content-type']?.startsWith('application/json')) { res.writeHead(403); res.end(); return; }
      let body = '';
      for await (const chunk of req) { body += chunk; if (body.length > 4096) throw new Error('Request too large'); }
      const { id, action } = JSON.parse(body);
      if (!/^[a-z0-9-]+$/.test(id) || !['remove', 'github', 'r2'].includes(action)) throw new Error('Invalid edit');
      const edit = async () => {
        const [catalog, models] = await Promise.all([load(catalogFile), load(modelsFile)]);
        const entry = catalog.find((item) => item.id === id);
        if (action === 'remove') {
          if (!entry && !models.some((item) => item.id === id)) throw new Error('Unknown model');
          const removed = path.join(dataRoot, 'work/removed', `${Date.now()}-${id}`);
          await mkdir(removed, { recursive: true });
          await save(path.join(removed, 'selection.json'), models.filter((item) => item.id === id));
          await save(path.join(removed, 'catalog.json'), catalog.filter((item) => item.id === id));
          if (entry) await rename(path.join(dataRoot, entry.reviewOnly ? 'work/review' : 'assets', id), path.join(removed, 'assets'));
          await save(modelsFile, models.filter((item) => item.id !== id));
          await save(catalogFile, catalog.filter((item) => item.id !== id));
        } else {
          if (!entry) throw new Error('Model must be imported before changing delivery');
          if (entry.delivery === 'external') throw new Error('External/procedural models only host previews here');
          if (entry.reviewOnly) throw new Error('Review-only models cannot be published');
          if (action === 'github' && entry.bytes > MAX_FILE) throw new Error('GLB exceeds jsDelivr 20 MB limit');
          if (action !== entry.delivery) {
            const github = path.join(dataRoot, 'assets', id, 'model.glb');
            const r2Dir = path.join(dataRoot, 'work/r2', id);
            const r2 = path.join(r2Dir, 'model.glb');
            if (action === 'r2') { await mkdir(r2Dir, { recursive: true }); await cp(github, r2); await rm(github); }
            else await cp(r2, github);
            entry.delivery = action;
          }
          for (const model of models) if (model.id === id) model.delivery = action;
          await save(modelsFile, models);
          await save(catalogFile, catalog);
        }
        // Any edited selection invalidates a previously generated viewer catalog.
        await rm(path.join(dataRoot, 'presets.json'), { force: true });
      };
      const operation = mutations.then(() => withCatalogLock(dataRoot, edit));
      mutations = operation.catch(() => {});
      await operation;
      res.setHeader('Content-Type', 'application/json'); res.end('{"ok":true}'); return;
    }
    res.writeHead(404); res.end();
  } catch (error) { res.writeHead(400, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ error: error.message })); }
});
server.listen(Number(process.env.PORT || 3013), '127.0.0.1', () => console.log(`Review models: http://127.0.0.1:${server.address().port}`));
