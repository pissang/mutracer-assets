# MuTracer assets

Independent example models and MuTracer-rendered previews for
[MuTracer](https://github.com/pissang/mutracer). Models use their own CC licenses;
the repository's MIT license applies to the tooling only.

## Import and review

Use Node 22+, Google Chrome and a GPU. Clone MuTracer next to this repository
and run `npm install` in both checkouts. The renderer uses MuTracer's current
viewer engine, so it needs `../mutracer/viewer/vite.config.ts`. Set
`MUTRACER_ROOT` or `--mutracer-dir` for another location.

```bash
npm ci
# Set SKETCHFAB_API_TOKEN (personal token) or SKETCHFAB_ACCESS_TOKEN (OAuth).
npm run import -- --headless
npm run review
```

Open `http://127.0.0.1:3013`. Each card shows the rendered preview, author,
license, size and delivery location. **Remove** takes the model out of both
`catalog.json` and `models.json`, and moves its assets to ignored
`work/removed/<timestamp>-<id>/`. It will not return on the next default import.
Cached downloads remain in ignored `work/import` for recovery. A card can also
switch a model between GitHub and R2; switching an oversized GLB to GitHub is
disabled. Review previews before deciding which models demonstrate path tracing
well: glass-looking Sketchfab materials do not always export physical transmission.
Prefer modeled detail and simple material colors. Dense detail textures or baked
shadows/highlights/reflections can obscure the benefit of path tracing; texture
count alone does not identify baked lighting.

Material spheres, Toy Car and Sheen Chair share this same `models.json` selection,
review list and published `presets.json`. Their entries have `source: "viewer"`:
Material spheres are procedural and the two Khronos GLBs remain at their original
URLs. Only previews and attribution files are stored here (`delivery: "external"`);
the review UI permits removal but does not move these model sources to R2/GitHub.
Default cameras and the studio background are stored alongside the model metadata.
Regenerate them with the same importer, without Sketchfab credentials:

```bash
npm run import -- --headless --model spheres --model toycar --model sheenchair
```

Import one model with `--model ID_OR_URL_OR_UID`. Downloads and rendering are serial.
Completed models are checkpointed; re-running reuses cached GLBs and matching
previews. `--refresh` downloads and renders again. Defaults are 720 × 405 with WebP quality 80%,
256 offline samples, procedural studio lights and OIDN standard denoising on
WebGPU. Preview generation fails if WebGPU or OIDN is unavailable. Downloads prefer Sketchfab's optimized GLB; all textures are
checked and capped at 1024 pixels on their longest edge without upscaling.
Original downloads remain in ignored `work/import/<id>/download.glb`.

Before rendering or publication, gltf-transform converts PNG textures to
lossless WebP and compresses geometry/animation with Meshopt (16-bit positions,
12-bit normals, 14-bit UVs). JPEG textures remain unchanged. No mesh simplification
or scene flattening is applied. Selection entries may set `instance: true` to
reuse repeated meshes through glTF instancing while preserving their transforms
and materials. Results are cached under ignored
`work/import/<id>/compression` and are used only if smaller. The pipeline checks
extensions, credits, texture dimensions and the camera after compression, then
renders the compressed GLB with the viewer's bundled Meshopt decoder.

Generate camera contact sheets with `npm run cameras -- --headless`, optionally
`--model ID` and `--views '[{"azimuth":25,"elevation":3}]'`. Inspect
`work/cameras/<id>/contact-sheet.png` and copy the selected camera from
`candidates.json` into `models.json`. Dolly closer and shift the target towards
interesting details; the preferred composition can crop model edges.
The camera includes `position`, `target`, `fov`, and `space: "grounded"`:
coordinates apply after the viewer centers X/Z and grounds Y. Import embeds
that camera in the active GLB scene's `extras.mutracerCamera` and renders the
same view. The current MuTracer viewer reads it on a fresh load; restoring a
saved user view takes precedence. Final import verifies the loaded camera and
records the actual denoising pass and OIDN runtime information in
`work/import/<id>/render-result.json`.

Models marked `reviewOnly: true` stay in ignored `work/review`. They can appear
in the local list but cannot switch to public hosting, upload to R2 or enter
`presets.json`. Jaguar and Free Standard models currently remain local. Yamaha
and Gelatinous Cube are authorized for a noncommercial public demonstration
with `nonCommercial: true`. They retain their respective CC BY-NC-SA / CC BY-NC
4.0 licenses; modified ShareAlike assets retain the same license. The code's MIT
license does not apply to these assets. Open-source status alone is insufficient
to establish a noncommercial use.

For an untracked credential file, copy `.env.example` to `.env` and use:

```bash
node --env-file=.env scripts/import-models.mjs --headless
```

## Mixed GitHub / R2 hosting

All previews and attribution files live under `assets/<id>/` in GitHub.
GLBs up to 20 MB are stored alongside them. Larger GLBs are kept in ignored
`work/r2/<id>/model.glb` and marked `delivery: "r2"`. No large GLB is staged
into Git history. Files are ordinary Git objects, not Git LFS pointers.

The size checks use conservative decimal limits: 20,000,000 bytes per file
and 150,000,000 bytes for the current repository snapshot. These correspond to
jsDelivr's [documented default restrictions](https://github.com/jsdelivr/jsdelivr#restrictions).
Even a GLB below 20 MB can be switched to R2 to keep the whole snapshot below
the total limit. Screenshots and attribution always remain on GitHub.

For retained R2 models, configure an existing bucket, public custom domain and
CORS (`GET`, `HEAD` allowed from the viewer origin). Authenticate with
`npx wrangler login` or Cloudflare environment credentials, then run:

```bash
npm run upload:r2 -- --bucket YOUR_BUCKET --public-base https://YOUR_ASSET_DOMAIN
# Upload first if the public domain is not ready yet:
# npm run upload:r2 -- --bucket YOUR_BUCKET
# If credentials/settings are in .env:
# node --env-file=.env scripts/upload-r2.mjs
# Optional: --model perfume-bottle; --force to replace a recorded target URL
```

This checkout uses the `mutracer-assets` bucket. `r2-cors.json` contains the
read-only CORS policy allowing only `https://mutracer.meimu-studio.com`.
Localhost and other website origins are not allowed. This is browser CORS
enforcement, not authentication or a restriction on direct HTTP downloads:

```bash
npx wrangler r2 bucket cors set mutracer-assets --file r2-cors.json --force
```

Only R2 GLBs are uploaded. They use content hashes in object paths, Standard
storage and immutable cache headers. The command saves the resulting URLs in
`catalog.json`; it never commits or pushes to GitHub. Without `--public-base`,
it records bucket/object paths only. Re-run with `--public-base` once the domain
is ready; unchanged objects in the same bucket are not uploaded again. The
`MuTracer immutable GLB assets` Cache Rule makes the asset domain's `/models/*`
eligible for CDN cache and respects origin cache-control headers. Wrangler uploads are limited to 300 MiB;
larger files require an S3 multipart uploader. ZIP downloads/expanded archives
are limited to 512 MiB.

## Generate URLs and publish manually

After reviewing and uploading any retained R2 models:

```bash
npm run check
npm run catalog -- --version v0.1.0
npm test
git add assets models.json catalog.json presets.json
git commit -m "Add reviewed viewer models"
git tag v0.1.0
git push origin main
git push origin v0.1.0
```

For the first commit, also add the scripts, package files, README, LICENSE and
dotfiles. All GitHub commits, tags and pushes are manual. No script invokes
`git commit`, `git tag` or `git push`. `npm run catalog` only writes `presets.json`.
Use a new immutable tag for every published version; do not move old tags.
The generated URLs look like:

```text
https://cdn.jsdelivr.net/gh/pissang/mutracer-assets@v0.1.0/assets/wooden-chess/model.glb
https://cdn.jsdelivr.net/gh/pissang/mutracer-assets@v0.1.0/assets/wooden-chess/thumbnail.webp
```

`presets.json` is a viewer-compatible model list. R2 models have an R2 `url`
and a jsDelivr `thumbnail`. Add reviewed entries to the MuTracer viewer while
keeping the same IDs/order/cameras, author/source attribution and a visible CC license link. The `attributionUrl`
contains original descriptions and additional creator credits. Editing selection
or delivery in the review UI invalidates `presets.json`, so regenerate it before
your next commit.

## Licenses

Every Sketchfab download checks Sketchfab's current license and download availability.
Archive-based scenes retain their original license and creator credits; the catalog accepts CC BY 3.0 alongside CC0 and CC BY 4.0.
Public NC assets require an explicit `nonCommercial: true` decision. Free
Standard permits local previews but not standalone GLB redistribution.
`assets/<id>/attribution.json` retains the original author,
source, license URL, description and a modification notice. GLBs also embed
that attribution in `asset.extras`. Review descriptions for extra credits.
The tooling's MIT license does not relicense downloaded assets.

No credentials or signed download links are saved in published files.
`work/`, `.env` and `node_modules/` are ignored. The original MuTracer repository
does not contain these assets or pipeline tooling.
