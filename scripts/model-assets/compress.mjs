import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import sharp from 'sharp';
import {decodeGLB,encodeGLB} from './gltf.mjs';
import {saveJSON} from './catalog-lock.mjs';

const execute=promisify(execFile);
/** Compress only: no simplification, flattening, joining or material substitution. */
export async function compressGLB(bytes,directory,root) {
  await mkdir(directory,{recursive:true});
  const cli=path.join(root,'node_modules/@gltf-transform/cli/bin/cli.js');
  const version=JSON.parse(await readFile(path.join(root,'node_modules/@gltf-transform/cli/package.json'),'utf8')).version;
  const signature=JSON.stringify({sha256:createHash('sha256').update(bytes).digest('hex'),version,webp:'png-lossless',meshopt:'medium',positionBits:16,normalBits:12,uvBits:14});
  const output=path.join(directory,'model.glb'),settings=path.join(directory,'settings.json');
  if(await readFile(settings,'utf8').then(value=>value===signature,()=>false)) return {glb:await readFile(output),stats:JSON.parse(await readFile(path.join(directory,'stats.json'),'utf8'))};
  const source=decodeGLB(bytes);
  const input=path.join(directory,'input.glb'),webp=path.join(directory,'textures.glb');
  await writeFile(input,bytes);
  const env={...process.env}; delete env.SKETCHFAB_API_TOKEN;delete env.SKETCHFAB_ACCESS_TOKEN;
  for(const args of [['webp',input,webp,'--formats','png','--lossless','true','--effort','70'],['meshopt',webp,output,'--level','medium','--quantize-position','16','--quantize-normal','12','--quantize-texcoord','14']]) {
    const result=await execute(process.execPath,[cli,...args],{cwd:root,env,timeout:180000,maxBuffer:4*1024**2});
    if (/not registered|unsupported extension/i.test(result.stdout+result.stderr)) throw new Error('gltf-transform cannot preserve one of the model extensions');
  }
  const parsed=decodeGLB(await readFile(output));
  // Asset-level extras are not represented by glTF Transform's document model.
  parsed.json.asset.extras=source.json.asset.extras;
  const originalCamera=source.json.scenes?.[source.json.scene||0]?.extras?.mutracerCamera;
  const compressedCamera=parsed.json.scenes?.[parsed.json.scene||0]?.extras?.mutracerCamera;
  if(JSON.stringify(originalCamera)!==JSON.stringify(compressedCamera)) throw new Error('Compression changed the default camera');
  for(const extension of source.json.extensionsUsed||[]) {
    if(!parsed.json.extensionsUsed?.includes(extension)) throw new Error(`Compression dropped ${extension}`);
  }
  const images=[];
  for(const image of parsed.json.images||[]) {
    const view=parsed.json.bufferViews[image.bufferView];
    const metadata=await sharp(parsed.bin.subarray(view.byteOffset||0,(view.byteOffset||0)+view.byteLength)).metadata();
    if(metadata.width>1024||metadata.height>1024) throw new Error('Compressed texture exceeds 1K');
    images.push({width:metadata.width,height:metadata.height,mimeType:image.mimeType});
  }
  let glb=encodeGLB(parsed.json,parsed.bin);
  // Retain the smaller result if compression overhead exceeds the savings.
  const compressed=glb.length<bytes.length;
  if(!compressed) glb=bytes;
  const stats={tool:'gltf-transform',version,inputBytes:bytes.length,outputBytes:glb.length,compressed,geometry:'Meshopt (16-bit positions, 12-bit normals, 14-bit UVs)',textures:'lossless WebP for PNG; JPEG unchanged',images};
  await writeFile(output,glb);await writeFile(settings,signature);await saveJSON(path.join(directory,'stats.json'),stats);
  return {glb,stats};
}
