import { createReadStream } from 'node:fs';
import { writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { chromium } from 'playwright';

const assetRepo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

async function withTimeout(operation, ms) {
  let timer;
  try {
    return await Promise.race([operation(), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('Model preparation or offline render timed out')), ms);
      timer.unref();
    })]);
  } finally {
    clearTimeout(timer);
  }
}

/** A dedicated viewer engine, without React, presets, or remote HDR downloads. */
export async function createAssetRenderer(options) {
  if (options.webgl) throw new Error('Asset previews require WebGPU for OIDN denoising; WebGL is unsupported');
  const repo = path.resolve(options.mutracerDir || process.env.MUTRACER_ROOT || path.join(assetRepo, '../mutracer'));
  let modelFile;
  let loadedFile;
  const server = await createServer({
    configFile: path.join(repo, 'viewer/vite.config.ts'),
    server: { host: '127.0.0.1', port: 0, open: false },
    plugins: [{
      name: 'model-asset-render',
      configureServer(vite) {
        vite.middlewares.use((req, res, next) => {
          if (req.url?.split('?')[0] === '/__asset-model.glb' && modelFile) {
            res.setHeader('Content-Type', 'model/gltf-binary');
            createReadStream(modelFile).on('error', () => { res.statusCode = 500; res.end(); }).pipe(res);
          } else if (req.url?.split('?')[0] === '/__asset-render') {
            res.setHeader('Content-Type', 'text/html');
            res.end('<!doctype html><style>body{margin:0}canvas{width:100vw;height:100vh;display:block}</style><canvas></canvas>');
          } else next();
        });
      }
    }]
  });
  let browser;
  try {
    await server.listen();
    browser = await chromium.launch({
      channel: options.browserPath ? undefined : 'chrome',
      executablePath: options.browserPath,
      headless: options.headless,
      args: ['--enable-unsafe-webgpu']
    });
    const page = await browser.newPage({ viewport: { width: options.width, height: options.height } });
    page.setDefaultTimeout(options.timeout);
    const port = server.httpServer.address().port;
    await page.goto(`http://127.0.0.1:${port}/__asset-render${options.webgl ? '?webgl' : ''}`);
    await page.evaluate(async (threeUrl) => {
      const { ViewerEngine } = await import('/src/engine/ViewerEngine.ts');
      const { useViewer, DEFAULT_SETTINGS } = await import('/src/store.ts');
      const { Vector3 } = await import(threeUrl);
      window.assetVector3 = Vector3;
      useViewer.setState({ settings: { ...DEFAULT_SETTINGS, lighting: 'studio', background: 'color', denoise: true, denoiseModel: 'standard', denoiseWhileConverging: false, resolutionScale: 1, maxSamples: 1, interactivePreview: false } });
      window.assetStore = useViewer;
      window.assetEngine = new ViewerEngine(document.querySelector('canvas'));
    }, `/@fs${path.join(repo, 'node_modules/three/build/three.module.js')}`);
    return {
      async render(file, output, camera) {
        return withTimeout(async () => {
          const external = typeof file === 'object' ? file : null;
          const key = external ? JSON.stringify(external) : file;
          modelFile = external ? null : file;
          const cameraResult = await page.evaluate(async ({ width, height, camera, reload, external }) => {
            window.assetStore.setState(s => ({settings: {...s.settings, background: external?.background || 'color'}}));
            if (reload) {
              let loaded;
              if (external?.url === null) {
                const {createMaterialSpheres} = await import('/src/engine/loadModel.ts');
                loaded = await window.assetEngine.loadModel(createMaterialSpheres());
              } else {
                loaded = await window.assetEngine.loadUrl(external?.url || `/__asset-model.glb?t=${Date.now()}`);
              }
              if (loaded === false) throw new Error('GLB loading failed; check required glTF extensions and textures');
            }
            const loadedCamera=reload?{position:window.assetEngine.camera.position.toArray(),target:window.assetEngine.controls.target.toArray(),fov:window.assetEngine.perspectiveCamera.fov,space:'grounded'}:null;
            window.assetEngine.fit(width / height);
            if (camera?.view) {
              const engine=window.assetEngine, Vector3=window.assetVector3;
              const box=engine.modelBounds(), center=box.getCenter(new Vector3());
              const az=camera.view.azimuth*Math.PI/180, el=camera.view.elevation*Math.PI/180;
              const direction=new Vector3(Math.sin(az)*Math.cos(el),Math.sin(el),Math.cos(az)*Math.cos(el));
              const right=new Vector3().crossVectors(new Vector3(0,1,0),direction).normalize();
              const up=new Vector3().crossVectors(direction,right);
              const tanV=Math.tan(engine.perspectiveCamera.fov*Math.PI/360)*(camera.view.margin||0.88), tanH=tanV*width/height;
              let distance=0;
              for(let i=0;i<8;i++) {
                const corner=new Vector3(i&1?box.max.x:box.min.x,i&2?box.max.y:box.min.y,i&4?box.max.z:box.min.z).sub(center);
                const depth=corner.dot(direction);
                distance=Math.max(distance,depth+Math.abs(corner.dot(right))/tanH,depth+Math.abs(corner.dot(up))/tanV);
              }
              camera={position:center.clone().addScaledVector(direction,distance).toArray(),target:center.toArray(),fov:engine.perspectiveCamera.fov};
            }
            if (camera) {
              if (camera.fov) {
                window.assetStore.setState(s=>({settings:{...s.settings,fov:camera.fov,projection:'perspective'}}));
                window.assetEngine.perspectiveCamera.fov=camera.fov;
                window.assetEngine.perspectiveCamera.updateProjectionMatrix();
              }
              window.assetEngine.lookAt(new window.assetVector3(...camera.position), new window.assetVector3(...camera.target));
            }
            return {camera:{position:window.assetEngine.camera.position.toArray(),target:window.assetEngine.controls.target.toArray(),fov:window.assetEngine.perspectiveCamera.fov,space:'grounded'},loadedCamera};
          }, { width: options.width, height: options.height, camera, external, reload:loadedFile !== key });
          loadedFile=key;
          await page.waitForFunction(() => {
            const state = window.assetStore.getState();
            if (state.stats.phase === 'error') throw new Error('MuTracer GPU preparation failed');
            return !state.loading && state.stats.samples > 0;
          }, null, { timeout: options.timeout });
          const rendered = await page.evaluate(async ({ width, height, samples, previewQuality = 0.8 }) => {
            const renderer = window.assetEngine.engine;
            const final = window.assetEngine.final;
            if (renderer.backend !== 'webgpu') throw new Error('Asset previews require WebGPU for OIDN denoising');
            await final.setDenoiser({ type: 'oidn', model: 'standard', weightsBaseUrl: new URL('/oidn/weights/',location.href).href });
            if (!final.denoiser) throw new Error('OIDN did not attach to the final render');
            let denoised=false;
            const unsubscribe=window.assetStore.subscribe(state=>{if(state.export?.stage==='denoising') denoised=true;});
            let blob;
            try {
              blob = await window.assetEngine.renderImage({ width, height, samples, transparent: false }, 'image/webp', previewQuality);
            } finally {unsubscribe();}
            if (!denoised) throw new Error('Offline preview did not run the denoising pass');
            if (!final.denoiser) throw new Error('OIDN was detached during the offline render');
            const bytes = new Uint8Array(await blob.arrayBuffer());
            let binary = '';
            for (const byte of bytes) binary += String.fromCharCode(byte);
            return { image: btoa(binary), backend: window.assetStore.getState().backend, denoised, denoiser: { type: 'oidn', model: 'standard', runtime: renderer.getDiagnostics()?.oidn } };
          }, options);
          await writeFile(output, Buffer.from(rendered.image, 'base64'));
          return {...rendered.backend,...cameraResult,denoised:rendered.denoised,denoiser:rendered.denoiser};
        }, options.timeout);
      },
      async close() {
        try { await browser.close(); } finally { await server.close(); }
      }
    };
  } catch (error) {
    await browser?.close();
    await server.close();
    throw error;
  }
}
