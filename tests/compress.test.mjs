import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import sharp from 'sharp';
import {packGLTF, decodeGLB} from '../scripts/model-assets/gltf.mjs';
import {compressGLB} from '../scripts/model-assets/compress.mjs';
import {root} from '../scripts/check-assets.mjs';

test('compression preserves a 4K texture, attribution and default camera', async()=>{
  const directory=await mkdtemp(path.join(os.tmpdir(),'mutracer-compression-'));
  try {
    const texture=await sharp({create:{width:4096,height:4,channels:4,background:{r:20,g:90,b:150,alpha:0.5}}}).png().toBuffer();
    const camera={space:'grounded',position:[3,2,4],target:[0,1,0],fov:35};
    const credit={author:'Test author',license:'CC0'};
    const geometry=Buffer.from(new Float32Array([0,0,0,1,0,0,0,1,0]).buffer);
    const glb=packGLTF({
      'scene.gltf':Buffer.from(JSON.stringify({
        asset:{version:'2.0'},scene:0,scenes:[{nodes:[0],extras:{mutracerCamera:camera}}],nodes:[{mesh:0}],
        buffers:[{uri:'mesh.bin',byteLength:geometry.length}],bufferViews:[{buffer:0,byteOffset:0,byteLength:geometry.length}],
        accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[0,0,0],max:[1,1,0]}],
        images:[{uri:'color.png'}],textures:[{source:0}],materials:[{pbrMetallicRoughness:{baseColorTexture:{index:0}}}],
        meshes:[{primitives:[{attributes:{POSITION:0},material:0}]}]
      })),
      'mesh.bin':geometry,'color.png':texture
    },'scene.gltf',credit);
    const result=await compressGLB(glb,directory,root);
    const {json,bin}=decodeGLB(result.glb);
    const view=json.bufferViews[json.images[0].bufferView];
    const metadata=await sharp(bin.subarray(view.byteOffset||0,(view.byteOffset||0)+view.byteLength)).metadata();
    assert.equal(metadata.width,4096);
    assert.equal(metadata.height,4);
    assert.equal(metadata.hasAlpha,true);
    assert.deepEqual(json.asset.extras.mutracerAttribution,credit);
    assert.deepEqual(json.scenes[0].extras.mutracerCamera,camera);
    assert.equal(result.stats.images[0].width,4096);
  } finally {
    await rm(directory,{recursive:true,force:true});
  }
});
