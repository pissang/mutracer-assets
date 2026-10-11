import { parseArgs } from 'node:util';
import { readFile, mkdir, writeFile, cp, rm, stat } from 'node:fs/promises';
import path from 'node:path';
import { createInterface } from 'node:readline';
import { createHash } from 'node:crypto';
import { modelUid } from './model-assets/gltf.mjs';
import { downloadModel, closeDownloads } from './model-assets/download.mjs';
import { createAssetRenderer } from './model-assets/render.mjs';
import { root, MAX_FILE, checkRepository } from './check-assets.mjs';
import { limitTextures } from './model-assets/textures.mjs';
import { compressGLB } from './model-assets/compress.mjs';
import { withCatalogLock, saveJSON } from './model-assets/catalog-lock.mjs';

const { values } = parseArgs({ options: {
  help: { type: 'boolean' }, model: { type: 'string', multiple: true },
  'token-stdin': { type: 'boolean' }, 'refresh': { type: 'boolean' },
  'mutracer-dir': { type: 'string' }, headless: { type: 'boolean' }, webgl: { type: 'boolean' },
  width: { type: 'string', default: '960' }, height: { type: 'string', default: '540' },
  samples: { type: 'string', default: '256' }, timeout: { type: 'string', default: '300000' },
  local: { type: 'string' }, 'browser-path': { type: 'string' },
  'texture-size': { type: 'string', default: '1024' }
} });
if (values.help) {
  console.log(`Usage: npm run import -- [--model UID_OR_URL] [--headless] [--refresh]
Downloads + GLB + MuTracer previews. No GitHub or R2 uploads.
Default selection: models.json. Uses cached GLBs/previews unless --refresh.
--mutracer-dir DIR   MuTracer checkout with npm install (default ../mutracer)
--width/--height     Preview dimensions (default 960 × 540)
--samples           Offline samples (default 256, OIDN standard on WebGPU)
--texture-size      Maximum texture dimension (default 1024)
--timeout           GPU timeout in ms (default 300000)
--local FILE        Render a local GLB to ignored work/local-preview.webp only
--webgl             Unsupported: OIDN previews require WebGPU
--browser-path FILE Use this Chrome executable
--token-stdin       Read a personal API token from a hidden stdin input
Credentials: SKETCHFAB_ACCESS_TOKEN (OAuth) or SKETCHFAB_API_TOKEN (personal).
GLBs larger than 20 MB are staged in ignored work/r2; previews always go to assets/.`);
  await closeDownloads();
} else {
  let renderer;
  try {
    if (values['token-stdin']) {
      const input = createInterface({ input: process.stdin });
      process.env.SKETCHFAB_API_TOKEN = await new Promise((resolve) => input.once('line', resolve));
      input.close();
      process.stdin.pause();
    }
    const options = { width: Number(values.width), height: Number(values.height), samples: Number(values.samples), timeout: Number(values.timeout),
      headless: !!values.headless, webgl: !!values.webgl, mutracerDir: values['mutracer-dir'], browserPath: values['browser-path'], textureSize: Number(values['texture-size']),denoise:true,denoiser:{type:'oidn',model:'standard'} };
    for (const key of ['width', 'height', 'samples', 'timeout']) if (!Number.isSafeInteger(options[key]) || options[key] <= 0) throw new Error(`${key} must be a positive integer`);
    if (options.width > 8192 || options.height > 8192) throw new Error('Preview dimensions must not exceed 8192');
    const configured = JSON.parse(await readFile(path.join(root, 'models.json'), 'utf8'));
    const selected = values.model ? values.model.map((input) => {
      const uid = modelUid(input);
      return configured.find((entry) => entry.uid === uid) || { uid, id: uid };
    }) : configured;
    for (const entry of selected) {
      entry.uid = modelUid(entry.uid);
      if (!/^[a-z0-9-]+$/.test(entry.id)) throw new Error('Invalid model ID');
    }
    renderer = await createAssetRenderer(options);
    await mkdir(path.join(root, 'work'), { recursive: true });
    if (values.local) {
      const output = path.join(root, 'work/local-preview.webp');
      console.log(await renderer.render(path.resolve(values.local), output));
      console.log(`Preview: ${output}`);
    } else {
      for (const entry of selected) {
        const dir = path.join(root, 'work/import', entry.id);
        await mkdir(dir, { recursive: true });
        const glbFile = path.join(dir, 'model.glb');
        const metadata = path.join(dir, 'source.json');
        let credit;
        const existing = !values.refresh && await stat(glbFile).then(() => true, () => false);
        if (existing) {
          console.log(`Reusing ${entry.id}`);
          credit = JSON.parse(await readFile(path.join(dir, 'attribution.json'), 'utf8'));
        } else {
          console.log(`Downloading ${entry.id}`);
          const downloaded = await downloadModel(entry.uid, {reviewOnly:!!entry.reviewOnly,nonCommercial:entry.nonCommercial===true});
          credit = downloaded.credit;
          await writeFile(glbFile, downloaded.glb);
          await writeFile(metadata, JSON.stringify(downloaded.source, null, 2));
          await writeFile(path.join(dir, 'attribution.json'), JSON.stringify(credit, null, 2));
          await cp(glbFile,path.join(dir,'download.glb'));
        }
        const original=path.join(dir,'download.glb');
        if (!(await stat(original).then(()=>true,()=>false))) await cp(glbFile,original);
        if (entry.additionalCredits) credit.additionalCredits = entry.additionalCredits;
        credit.changes = `Repacked as a single GLB; textures limited to ${options.textureSize}px; geometry compressed/quantized with gltf-transform Meshopt without simplification; PNG textures compressed with lossless WebP; default camera embedded; preview rendered with MuTracer and denoised with OIDN standard.`;
        const processed = await limitTextures(await readFile(original),options.textureSize,credit,entry.camera);
        const compressed=await compressGLB(processed.glb,path.join(dir,'compression'),root);
        await writeFile(glbFile,compressed.glb);
        await saveJSON(path.join(dir,'attribution.json'),credit);
        await saveJSON(path.join(dir,'texture-stats.json'),processed.stats);
        const hash=createHash('sha256').update(compressed.glb).digest('hex');
        const image = path.join(dir, 'thumbnail.webp');
        const signature = JSON.stringify({ ...options, camera: entry.camera, sha256:hash });
        const renderSettings = path.join(dir, 'render-settings.json');
        if (existing && await readFile(renderSettings, 'utf8').then((text) => text === signature, () => false) && await stat(image).then(() => true, () => false)) {
          console.log(`Reusing preview for ${entry.id}`);
        } else {
          console.log(`Rendering ${entry.id}`);
          const backend = await renderer.render(glbFile, image, entry.camera);
          if (entry.camera && backend.loadedCamera) {
            const actual=backend.loadedCamera;
            const equal=(a,b)=>Math.abs(a-b)<=1e-5*Math.max(1,Math.abs(b));
            if (!equal(actual.fov,entry.camera.fov)||!actual.position.every((v,i)=>equal(v,entry.camera.position[i]))||!actual.target.every((v,i)=>equal(v,entry.camera.target[i]))) throw new Error(`Default loaded camera differs from preview: ${entry.id}`);
          }
          await saveJSON(path.join(dir,'render-result.json'),backend);
          console.log(`Rendered ${entry.id} on ${backend?.name} (${backend?.adapter})`);
          await writeFile(renderSettings, signature);
        }
        const size = (await stat(glbFile)).size;
        await withCatalogLock(root,async()=>{
        const selections=JSON.parse(await readFile(path.join(root,'models.json'),'utf8'));
        const current=selections.find(model=>model.id===entry.id);
        if (!current && (!values.model || configured.some(model=>model.id===entry.id))) {console.log(`Removed during import: ${entry.id}`);return;}
        const catalog=JSON.parse(await readFile(path.join(root,'catalog.json'),'utf8'));
        const delivery = entry.reviewOnly ? 'local' : size > MAX_FILE || current?.delivery === 'r2' ? 'r2' : 'github';
        const assetDir = path.join(root, entry.reviewOnly ? 'work/review' : 'assets', entry.id);
        await mkdir(assetDir, { recursive: true });
        await cp(image, path.join(assetDir, 'thumbnail.webp'));
        await cp(path.join(dir, 'attribution.json'), path.join(assetDir, 'attribution.json'));
        if (delivery === 'github' || delivery === 'local') await cp(glbFile, path.join(assetDir, 'model.glb'));
        else {
          const target = path.join(root, 'work/r2', entry.id);
          await mkdir(target, { recursive: true });
          await cp(glbFile, path.join(target, 'model.glb'));
          await rm(path.join(assetDir, 'model.glb'), { force: true });
        }
        const item = { id: entry.id, uid: entry.uid, name: entry.name || credit.title, tag: entry.tag || 'Sketchfab',
          license: credit.license, licenseUrl: credit.licenseUrl, credit: credit.author, sourceUrl: credit.sourceUrl,
          sizeMB: Number((size / 1e6).toFixed(2)), bytes: size, delivery,
          sha256: hash, textureSize:options.textureSize, compression:compressed.stats, ...(entry.materialNotes ? {materialNotes:entry.materialNotes} : {}), ...(entry.reviewOnly ? {reviewOnly:true} : {}), ...(entry.nonCommercial===true ? {nonCommercial:true} : {}), ...(entry.camera ? {camera:entry.camera} : {}) };
        const index = catalog.findIndex((old) => old.id === item.id);
        if (index >= 0 && catalog[index].sha256 === item.sha256 && delivery === 'r2') {
          for (const field of ['r2Url', 'r2Bucket', 'r2Key']) if (catalog[index][field]) item[field] = catalog[index][field];
        }
        if (index < 0) catalog.push(item); else catalog[index] = item;
        // Checkpoint each completed model so interruptions preserve finished work.
        await saveJSON(path.join(root, 'catalog.json'), catalog);
        await rm(path.join(root, 'presets.json'), { force: true });
        console.log(`Prepared ${entry.id}: ${item.sizeMB} MB → ${delivery}`);
        });
      }
      console.log(await checkRepository());
      console.log('Review with: npm run review');
    }
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  } finally {
    await renderer?.close();
    await closeDownloads();
  }
}
