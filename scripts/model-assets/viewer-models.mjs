import {readFile,writeFile,mkdir,cp,rm,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {canPublish} from './licenses.mjs';
import {withCatalogLock,saveJSON} from './catalog-lock.mjs';

/** Prepare a procedural/Khronos sample's preview; its model stays at its source. */
export async function prepareViewerModel(root, entry, options, renderer) {
  if (!canPublish(entry) || !entry.credit || !entry.sourceUrl || !entry.licenseUrl ||
    (entry.url !== null && (typeof entry.url !== 'string' || !entry.url.startsWith('https://')))) {
    throw new Error(`Incomplete viewer sample metadata: ${entry.id}`);
  }
  const directory=path.join(root,'work/import',entry.id);
  await mkdir(directory,{recursive:true});
  const image=path.join(directory,'thumbnail.webp');
  const settings=path.join(directory,'render-settings.json');
  const signature=JSON.stringify({schema:1,entry,options});
  const cached=await readFile(settings,'utf8').then(value=>value===signature,()=>false) &&
    await stat(image).then(()=>true,()=>false);
  if (!cached) {
    console.log(`Rendering ${entry.id}`);
    const result=await renderer.render({url:entry.url,background:entry.background},image,entry.camera);
    await saveJSON(path.join(directory,'render-result.json'),result);
    await writeFile(settings,signature);
  } else console.log(`Reusing preview for ${entry.id}`);
  const credit={title:entry.name,author:entry.credit,sourceUrl:entry.sourceUrl,license:entry.license,
    licenseUrl:entry.licenseUrl,changes:`Preview rendered with MuTracer Studio Light and OIDN standard; ${options.width} × ${options.height} WebP at quality ${Math.round(options.previewQuality*100)}%. Default camera stored in the public presets. Original model remains procedural or is loaded unchanged from Khronos.`};
  await withCatalogLock(root,async()=>{
    const selection=JSON.parse(await readFile(path.join(root,'models.json'),'utf8'));
    const current=selection.find(model=>model.id===entry.id);
    if (!current) {console.log(`Removed during import: ${entry.id}`);return;}
    if (JSON.stringify(current)!==JSON.stringify(entry)) throw new Error(`Selection changed during rendering: ${entry.id}; rerun import`);
    const destination=path.join(root,'assets',entry.id);
    await mkdir(destination,{recursive:true});
    await cp(image,path.join(destination,'thumbnail.webp'));
    await saveJSON(path.join(destination,'attribution.json'),credit);
    const previewSha256=createHash('sha256').update(await readFile(image)).digest('hex');
    const catalog=JSON.parse(await readFile(path.join(root,'catalog.json'),'utf8'));
    const item={...entry,delivery:'external',sizeMB:Number((entry.bytes/1e6).toFixed(2)),previewSha256};
    const index=catalog.findIndex(old=>old.id===entry.id);
    if (index<0)catalog.push(item);else catalog[index]=item;
    await saveJSON(path.join(root,'catalog.json'),catalog);
    await rm(path.join(root,'presets.json'),{force:true});
    console.log(`Prepared ${entry.id}: preview → GitHub; model → ${entry.url?'Khronos':'procedural'}`);
  });
}
