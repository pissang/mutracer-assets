import sharp from 'sharp';
import { decodeGLB, encodeGLB } from './gltf.mjs';

/** Cap embedded PNG/JPEG/WebP textures while preserving all scene/material data. */
export async function limitTextures(bytes, maxSize = 1024, credit, camera) {
  if (!Number.isSafeInteger(maxSize) || maxSize < 1 || maxSize > 8192) throw new Error('Invalid texture size');
  const { json, bin } = decodeGLB(bytes);
  const replacements = new Map();
  const sizes = [];
  const normalImages = new Set();
  for (const material of json.materials || []) {
    for (const texture of [material.normalTexture, material.extensions?.KHR_materials_clearcoat?.clearcoatNormalTexture]) {
      const source = json.textures?.[texture?.index]?.source;
      if (source !== undefined) normalImages.add(source);
    }
  }
  for (const [index, image] of (json.images || []).entries()) {
    if (image.uri || image.bufferView === undefined) throw new Error('Textures must be embedded in GLB');
    const view = json.bufferViews?.[image.bufferView];
    if (!view || (view.buffer || 0) !== 0 || view.byteOffset + view.byteLength > bin.length) throw new Error('Invalid texture buffer view');
    const input = bin.subarray(view.byteOffset || 0, (view.byteOffset || 0) + view.byteLength);
    const metadata = await sharp(input).metadata();
    if (!metadata.width || !metadata.height) throw new Error('Unknown texture dimensions');
    let width = metadata.width, height = metadata.height;
    if (Math.max(width, height) > maxSize) {
      const resized = sharp(input).resize({ width: maxSize, height: maxSize, fit: 'inside', withoutEnlargement: true });
      let output;
      if (normalImages.has(index)) {
        const raw = await resized.removeAlpha().raw().toBuffer({ resolveWithObject: true });
        if (raw.info.channels !== 3) throw new Error('Expected RGB normal map');
        for (let i = 0; i < raw.data.length; i += 3) {
          const v = [raw.data[i],raw.data[i+1],raw.data[i+2]].map(n=>n/127.5-1);
          const length = Math.hypot(...v) || 1;
          for (let c=0;c<3;c++) raw.data[i+c] = Math.round((v[c]/length+1)*127.5);
        }
        output = await sharp(raw.data,{raw:raw.info}).png().toBuffer({resolveWithObject:true});
        image.mimeType = 'image/png';
      } else if (image.mimeType === 'image/jpeg') output = await resized.jpeg({quality:92}).toBuffer({resolveWithObject:true});
      else if (image.mimeType === 'image/webp') output = await resized.webp({quality:92}).toBuffer({resolveWithObject:true});
      else { output = await resized.png().toBuffer({resolveWithObject:true}); image.mimeType = 'image/png'; }
      replacements.set(image.bufferView, output.data);
      width = output.info.width; height = output.info.height;
    }
    sizes.push({ width, height });
  }
  const parts = []; let length = 0;
  const append = data => {
    const offset=length; const padded=Math.ceil(data.length/4)*4;
    parts.push(data,Buffer.alloc(padded-data.length)); length+=padded; return offset;
  };
  for (const [index,view] of (json.bufferViews || []).entries()) {
    if ((view.buffer || 0) !== 0) throw new Error('Only a single embedded buffer is supported');
    const start=view.byteOffset||0;
    const data=replacements.get(index)||bin.subarray(start,start+view.byteLength);
    if (!replacements.has(index) && data.length !== view.byteLength) throw new Error('Truncated buffer view');
    view.byteOffset=append(data); view.byteLength=data.length;
    const compressed=view.extensions?.EXT_meshopt_compression;
    if (compressed) {
      const start=compressed.byteOffset||0;
      const source=bin.subarray(start,start+compressed.byteLength);
      if ((compressed.buffer||0)!==0 || source.length!==compressed.byteLength) throw new Error('Invalid meshopt source');
      compressed.byteOffset=append(source);
    }
  }
  json.buffers=[{byteLength:length}];
  if (credit) json.asset.extras={...json.asset.extras,mutracerAttribution:credit};
  const scene=json.scenes?.[json.scene||0];
  if (scene && camera) scene.extras={...scene.extras,mutracerCamera:camera};
  return { glb:encodeGLB(json,Buffer.concat(parts)), stats:{ maxSize, resized:replacements.size, images:sizes } };
}
