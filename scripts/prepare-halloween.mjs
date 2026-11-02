// Bakes sources/halloween.glb into a self-contained Collection source.
// The example configures its sky, materials and lights in code. The viewer only reads the
// GLB, so this writes them into the file: unlit moon, stars and mist, OpenPBR metadata and
// merged foliage, plus a sibling sky.hdr that the GLB names as its environment.
//
// Usage: node scripts/prepare-halloween.mjs [source.glb]
// Then:  npm run import -- --headless --model halloween
import {mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import sharp from 'sharp';
import {NodeIO} from '@gltf-transform/core';
import {KHRONOS_EXTENSIONS, KHRMaterialsUnlit} from '@gltf-transform/extensions';
import {prune} from '@gltf-transform/functions';
import {root} from './check-assets.mjs';

const source = process.argv[2] ?? path.join(root, 'sources/halloween.glb');
const directory = path.join(root, 'work/import/halloween');
const FLAME_RADIUS = 0.02;
// No crystal dispersion here: the viewer traces three wavelengths per path, about ten times slower.
const OPENPBR = {
  bubble: {thinFilmWeight: 1, thinFilmThickness: 0.42, thinFilmIor: 1.33, geometryThinWalled: true},
  glass_red: {baseColor: [1, 1, 1], transmissionColor: [0.9, 0.06, 0.08], transmissionDepth: 0.1},
  glass_green: {baseColor: [1, 1, 1], transmissionColor: [0.12, 0.85, 0.25], transmissionDepth: 0.1},
  glass_purple: {baseColor: [1, 1, 1], transmissionColor: [0.45, 0.12, 0.9], transmissionDepth: 0.1},
  fabric: {fuzzWeight: 1, fuzzColor: [0.4, 0.18, 0.7], fuzzRoughness: 0.4}
};

const smoothstep = (x, a, b) => {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
};

/** Same fractal value noise as examples/halloween.ts: tileable in x. */
function clouds(x, y, period) {
  const lattice = (i, j, p) => {
    const n = Math.sin(((i % p + p) % p) * 127.1 + j * 311.7 + p) * 43758.5453;
    return n - Math.floor(n);
  };
  let total = 0, amplitude = 0.5;
  for (let octave = 0; octave < 6; octave++, amplitude *= 0.5) {
    const p = period << octave, u = x * p, v = y * p;
    const i = Math.floor(u), j = Math.floor(v);
    const a = u - i, b = v - j;
    const s = a * a * (3 - 2 * a), t = b * b * (3 - 2 * b);
    total += amplitude * ((lattice(i, j, p) * (1 - s) + lattice(i + 1, j, p) * s) * (1 - t)
      + (lattice(i, j + 1, p) * (1 - s) + lattice(i + 1, j + 1, p) * s) * t);
  }
  return total;
}

/** Violet dusk with purple clouds, rimmed gold around the moon, as a Radiance RGBE file. */
function nightSky(moon, width = 1024, height = 512) {
  const header = Buffer.from(`#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y ${height} +X ${width}\n`);
  const pixels = Buffer.alloc(width * height * 4);
  for (let row = 0; row < height; row++) {
    const sourceTheta = (row + 0.5) / height * Math.PI;
    for (let col = 0; col < width; col++) {
      // The viewer reads metadata environments in PBRT's Z-up lat-long.
      const sourcePhi = (col + 0.5) / width * 2 * Math.PI;
      const x = Math.sin(sourceTheta) * Math.cos(sourcePhi), y = Math.sin(sourceTheta) * Math.sin(sourcePhi), z = Math.cos(sourceTheta);
      const up = Math.max(y, 0);
      const phi = (Math.atan2(-z, -x) + 2 * Math.PI) % (2 * Math.PI), theta = Math.acos(y);
      const toMoon = Math.max(x * moon[0] + y * moon[1] + z * moon[2], 0);
      const density = clouds(phi / (2 * Math.PI), theta / Math.PI * 2.8 / (0.5 + up), 9);
      const cloud = smoothstep(density, 0.46, 0.68) * smoothstep(up, 0.03, 0.2);
      const rim = toMoon ** 90 * (0.2 + cloud * 0.9) + toMoon ** 10 * 0.025;
      const glow = Math.exp(-up * 9), shade = 0.5 + density;
      const sky = [0.018 + 0.34 * glow, 0.014 + 0.13 * glow, 0.075 + 0.26 * glow];
      const lit = [0.13 * shade, 0.08 * shade, 0.26 * shade];
      const warm = [1, 0.62, 0.3];
      const color = sky.map((c, i) => c + (lit[i] - c) * cloud + warm[i] * rim);
      const exponent = Math.ceil(Math.log2(Math.max(...color, 1e-9)));
      const scale = 256 / 2 ** exponent, offset = (row * width + col) * 4;
      for (let c = 0; c < 3; c++) pixels[offset + c] = Math.min(255, color[c] * scale);
      pixels[offset + 3] = exponent + 128;
    }
  }
  return Buffer.concat([header, pixels]);
}

const transformPoint = (m, x, y, z) => [m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13], m[2] * x + m[6] * y + m[10] * z + m[14]];

/** Normal transform for the rotation and scale in m: the cofactor (inverse transpose) direction. */
function transformNormal(m, x, y, z) {
  const nx = (m[5] * m[10] - m[9] * m[6]) * x + (m[9] * m[2] - m[1] * m[10]) * y + (m[1] * m[6] - m[5] * m[2]) * z;
  const ny = (m[8] * m[6] - m[4] * m[10]) * x + (m[0] * m[10] - m[8] * m[2]) * y + (m[4] * m[2] - m[0] * m[6]) * z;
  const nz = (m[4] * m[9] - m[8] * m[5]) * x + (m[8] * m[1] - m[0] * m[9]) * y + (m[0] * m[5] - m[4] * m[1]) * z;
  const length = Math.hypot(nx, ny, nz) || 1;
  return [nx / length, ny / length, nz / length];
}

/** Rays would enter thousands of overlapping leaf instances one by one; one BLAS per material is far faster. */
function mergeFoliage(document, scene, buffer) {
  const groups = new Map();
  for (const node of document.getRoot().listNodes()) {
    const mesh = node.getMesh();
    if (!mesh || !/^(crown|carpet|tuft)/.test(node.getName())) continue;
    for (const primitive of mesh.listPrimitives()) {
      const group = groups.get(primitive.getMaterial()) ?? {positions: [], normals: [], indices: []};
      groups.set(primitive.getMaterial(), group);
      const matrix = node.getWorldMatrix();
      const position = primitive.getAttribute('POSITION'), normal = primitive.getAttribute('NORMAL');
      const base = group.positions.length / 3, a = [0, 0, 0], b = [0, 0, 0];
      for (let i = 0; i < position.getCount(); i++) {
        position.getElement(i, a);
        normal.getElement(i, b);
        group.positions.push(...transformPoint(matrix, a[0], a[1], a[2]));
        group.normals.push(...transformNormal(matrix, b[0], b[1], b[2]));
      }
      for (const index of primitive.getIndices().getArray()) group.indices.push(base + index);
    }
    node.dispose();
  }
  for (const [material, group] of groups) {
    const primitive = document.createPrimitive().setMaterial(material)
      .setAttribute('POSITION', document.createAccessor().setType('VEC3').setArray(new Float32Array(group.positions)).setBuffer(buffer))
      .setAttribute('NORMAL', document.createAccessor().setType('VEC3').setArray(new Float32Array(group.normals)).setBuffer(buffer))
      .setIndices(document.createAccessor().setType('SCALAR').setArray(new Uint32Array(group.indices)).setBuffer(buffer));
    const name = `foliage.${material.getName()}`;
    scene.addChild(document.createNode(name).setMesh(document.createMesh(name).addPrimitive(primitive)));
  }
}

const io = new NodeIO().registerExtensions(KHRONOS_EXTENSIONS);
const document = await io.read(source);
const scene = document.getRoot().listScenes()[0];
const buffer = document.getRoot().listBuffers()[0];
const unlit = document.createExtension(KHRMaterialsUnlit).createUnlit();

// glTF point intensity is candela and sphere intensity is radiance, so divide by the disk
// area. A small radius keeps the projected pumpkin faces crisp.
const moonNode = document.getRoot().listNodes().find(node => node.getName() === 'moon');
if (!moonNode) throw new Error('The source has no moon');
const moonPosition = moonNode.getWorldTranslation();
const moonDirection = moonPosition.map(c => c / Math.hypot(...moonPosition));
for (const node of document.getRoot().listNodes()) {
  const light = node.getExtension('KHR_lights_punctual');
  if (light?.getType() !== 'point') continue;
  light.setIntensity(light.getIntensity() / (Math.PI * FLAME_RADIUS ** 2));
  node.setExtras({...node.getExtras(), mutracerRadius: FLAME_RADIUS});
}

for (const material of document.getRoot().listMaterials()) {
  const name = material.getName();
  if (OPENPBR[name]) material.setExtras({...material.getExtras(), mutracerOpenPBR: OPENPBR[name]});
  if (name === 'stone') material.setExtras({...material.getExtras(), mutracerUvProjection: 'triplanar', mutracerUvProjectionScale: [1.6, 1.6]});
  const emissive = material.getEmissiveTexture();
  if (name === 'moon') {
    material.setBaseColorTexture(emissive).setBaseColorFactor([3.2, 3.2, 3.2, 1]).setExtension('KHR_materials_unlit', unlit);
  } else if (name === 'star') {
    material.setBaseColorFactor([4, 4.3, 5, 1]).setExtension('KHR_materials_unlit', unlit);
  } else if (name === 'mist') {
    // three's alphaMap has no glTF form: move the grey mask into a base-color alpha channel.
    const mask = await sharp(emissive.getImage()).toColourspace('b-w').extractChannel(0).toBuffer();
    const image = await sharp({create: {width: emissive.getSize()[0], height: emissive.getSize()[1], channels: 3, background: '#fff'}})
      .joinChannel(mask).png().toBuffer();
    material.setBaseColorTexture(document.createTexture('mist').setImage(image).setMimeType('image/png'))
      .setBaseColorFactor([0.32, 0.25, 0.46, 0.3]).setAlphaMode('BLEND').setDoubleSided(true)
      .setExtension('KHR_materials_unlit', unlit);
  } else continue;
  material.setEmissiveTexture(null).setEmissiveFactor([0, 0, 0]);
  material.setExtension('KHR_materials_emissive_strength', null);
}

mergeFoliage(document, scene, buffer);

// The viewer resolves this path against the GLB's ../source directory.
document.getRoot().setExtras({pbrt: {light_sources: [{gltf: 'metadata_only', pbrt: 'infinite', source: '../halloween/sky.hdr'}]}});

await document.transform(prune({keepExtras: true, keepAttributes: true}));

const credit = {
  title: 'Halloween Night',
  author: 'Yi Shen',
  sourceUrl: 'https://github.com/pissang/mutracer-assets',
  license: 'CC0',
  licenseUrl: 'https://creativecommons.org/publicdomain/zero/1.0/',
  description: 'Original autumn Halloween night by Yi Shen, modeled with a Blender script.'
};
await mkdir(directory, {recursive: true});
await writeFile(path.join(directory, 'sky.hdr'), nightSky(moonDirection));
const bytes = await io.writeBinary(document);
await writeFile(path.join(directory, 'download.glb'), bytes);
await writeFile(path.join(directory, 'model.glb'), bytes);
await writeFile(path.join(directory, 'attribution.json'), JSON.stringify(credit, null, 2));
console.log(`Wrote ${directory}/download.glb: ${(bytes.length / 1e6).toFixed(2)} MB`);
