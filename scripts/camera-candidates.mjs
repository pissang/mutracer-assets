import {parseArgs} from 'node:util';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import sharp from 'sharp';
import {root} from './check-assets.mjs';
import {saveJSON} from './model-assets/catalog-lock.mjs';
import {createAssetRenderer} from './model-assets/render.mjs';

const {values}=parseArgs({options:{model:{type:'string',multiple:true},headless:{type:'boolean'},samples:{type:'string',default:'32'},views:{type:'string'}}});
const catalog=JSON.parse(await readFile(path.join(root,'catalog.json'),'utf8'));
const width=480,height=270;
const options={width,height,samples:Number(values.samples),timeout:300000,headless:!!values.headless};
if (!Number.isSafeInteger(options.samples)||options.samples<1) throw new Error('Invalid samples');
const views=values.views?JSON.parse(values.views):[{azimuth:35,elevation:14},{azimuth:-35,elevation:14},{azimuth:145,elevation:14},{azimuth:-145,elevation:14},{azimuth:55,elevation:35},{azimuth:-55,elevation:35}];
if (!Array.isArray(views)||!views.length||views.length>24||views.some(view=>!Number.isFinite(view.azimuth)||!Number.isFinite(view.elevation)||Math.abs(view.elevation)>=89||(view.margin!==undefined&&(!(view.margin>0)||view.margin>1)))) throw new Error('Invalid candidate views');
const renderer=await createAssetRenderer(options);
try {
  for(const model of catalog) {
    if(values.model&&!values.model.includes(model.id)) continue;
    const directory=path.join(root,'work/cameras',model.id);await mkdir(directory,{recursive:true});
    const cameras=[]; const layers=[];
    for(const [index,view] of views.entries()) {
      const file=path.join(directory,`${index+1}.webp`);
      const result=await renderer.render(model.delivery==='external'?{url:model.url,background:model.background}:path.join(root,'work/import',model.id,'model.glb'),file,{view});
      cameras.push({index:index+1,view,camera:result.camera});
      const label=Buffer.from(`<svg width="480" height="26"><rect width="480" height="26" fill="#14161b"/><text x="12" y="19" fill="white" font-size="16">${index+1}: azimuth ${view.azimuth}°, elevation ${view.elevation}°</text></svg>`);
      layers.push({input:file,left:index%3*width,top:Math.floor(index/3)*(height+26)},{input:label,left:index%3*width,top:Math.floor(index/3)*(height+26)+height});
    }
    await sharp({create:{width:width*3,height:(height+26)*Math.ceil(views.length/3),channels:3,background:'#14161b'}}).composite(layers).png().toFile(path.join(directory,'contact-sheet.png'));
    await saveJSON(path.join(directory,'candidates.json'),cameras);
    console.log(`Camera candidates: ${model.id} → ${directory}/contact-sheet.png`);
  }
} finally {await renderer.close();}
