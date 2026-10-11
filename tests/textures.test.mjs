import {test} from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {packGLTF,decodeGLB,attribution} from '../scripts/model-assets/gltf.mjs';
import {limitTextures} from '../scripts/model-assets/textures.mjs';
import {buildCatalog} from '../scripts/build-catalog.mjs';

test('texture cap preserves geometry, material extensions, alpha and the chosen camera', async()=>{
  const texture=await sharp({create:{width:64,height:32,channels:4,background:{r:20,g:90,b:150,alpha:0.5}}}).png().toBuffer();
  const geometry=Buffer.from([10,20,30,40,50,60,70,80]);
  const material={extensions:{KHR_materials_transmission:{transmissionFactor:0.8}}};
  const glb=packGLTF({'scene.gltf':Buffer.from(JSON.stringify({asset:{version:'2.0'},scene:0,scenes:[{}],buffers:[{uri:'mesh.bin',byteLength:geometry.length}],bufferViews:[{buffer:0,byteOffset:0,byteLength:geometry.length}],images:[{uri:'color.png'}],materials:[material]})),'mesh.bin':geometry,'color.png':texture},'scene.gltf',{});
  const camera={space:'grounded',position:[3,2,4],target:[0,1,0],fov:45};
  const result=await limitTextures(glb,16,{},camera);
  assert.deepEqual(result.stats.images,[{width:16,height:8}]);
  const {json,bin}=decodeGLB(result.glb);
  assert.deepEqual(json.materials[0],material);
  assert.deepEqual(json.scenes[0].extras.mutracerCamera,camera);
  assert.deepEqual(bin.subarray(json.bufferViews[0].byteOffset,json.bufferViews[0].byteOffset+geometry.length),geometry);
  const image=json.bufferViews[json.images[0].bufferView];
  const metadata=await sharp(bin.subarray(image.byteOffset,image.byteOffset+image.byteLength)).metadata();
  assert.equal(metadata.hasAlpha,true);
});

test('noncommercial publication requires an explicit decision; restricted models remain local',()=>{
  const source={uid:'test',name:'Private preview',isDownloadable:true,user:{username:'author'},viewerUrl:'https://sketchfab.com/model',license:{slug:'by-nc-sa',url:'https://creativecommons.org/licenses/by-nc-sa/4.0/'}};
  assert.throws(()=>attribution(source),/Unsupported/);
  assert.equal(attribution(source,{reviewOnly:true}).license,'CC-BY-NC-SA 4.0');
  assert.deepEqual(buildCatalog([{id:'private',reviewOnly:true,delivery:'local',license:'CC-BY-NC-SA 4.0'}],'v0.1.0'),[]);
  assert.throws(()=>buildCatalog([{id:'private',delivery:'github',license:'CC-BY-NC-SA 4.0'}],'v0.1.0'),/eligible/);
  assert.equal(attribution(source,{nonCommercial:true}).license,'CC-BY-NC-SA 4.0');
  const published=buildCatalog([{id:'noncommercial',delivery:'github',license:'CC-BY-NC-SA 4.0',nonCommercial:true,bytes:100}],'v0.1.0');
  assert.equal(published[0].license,'CC-BY-NC-SA 4.0');
  assert.equal(published[0].nonCommercial,true);
  source.license={slug:'by-nc',url:'https://creativecommons.org/licenses/by-nc/4.0/'};
  assert.equal(attribution(source,{nonCommercial:true}).license,'CC-BY-NC 4.0');
  source.license={slug:'free-st',url:'https://sketchfab.com/licenses'};
  assert.throws(()=>attribution(source,{nonCommercial:true}),/Unsupported/);
  assert.equal(attribution(source,{reviewOnly:true}).license,'Sketchfab Free Standard');
  assert.throws(()=>buildCatalog([{id:'standard',delivery:'github',license:'Sketchfab Free Standard',nonCommercial:true}],'v0.1.0'),/eligible/);
});
