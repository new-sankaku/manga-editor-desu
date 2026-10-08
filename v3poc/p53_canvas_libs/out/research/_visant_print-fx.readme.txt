# @visant/print-fx

Isomorphic **print-effects engine**: CMYK halftone, risograph emulation, and 14 GLSL post-fx shaders. The same code runs in the browser (a `WebGLRenderingContext` from a `<canvas>`) and on the server ([headless-gl](https://github.com/stackgl/headless-gl)) — and the CPU halftone path needs no GL at all.

It powers the Visant Labs **ImageLab** (halftone / riso / shader effects) and is the shared substrate so the browser canvases and the server render pipeline can never drift.

## What's inside

| Surface | What it does |
| --- | --- |
| **Halftone** | CMYK halftone as an **SVG** string (per-channel rotated dot grids). Rasterize with any canvas → PNG/JPEG. Pure JS, no GL. |
| **Riso** | Risograph fragment shader (ink layers, 5 dither modes, halftone shapes, misregistration, paper/ink grain) + `applyRisoUniforms` to bind a `RisoSettings` to any GL context. |
| **Shaders** | 14 post-fx GLSL fragment shaders (vhs, ascii, dither, duotone, halftone, glitch, crt, …) behind a registry. |
| **GL runner** | Framework-agnostic compile / fullscreen-quad / texture / readPixels helpers + a per-context program cache. Bring your own context. |
| **Presets** | Halftone / riso / texture preset catalogs — single source of truth. |

> The engine owns context lifecycle? No — **you** do. The package never creates or destroys GL contexts itself (so the server can keep its singleton + mutex, and the browser its per-canvas context). It only knows how to compile, draw, and read.

## Install

```bash
npm i @visant/print-fx
# server-side riso/shaders also need headless-gl; rasterizing the halftone SVG needs node-canvas:
npm i gl canvas
```

`gl` and `canvas` are **optional** peer dependencies, imported lazily only from `@visant/print-fx/adapters/node`. Browser builds pull in neither.

## Exports

| Entry | Purpose |
| --- | --- |
| `.` | everything below, flat |
| `./halftone` | `generateHalftoneSvg`, `HalftoneSettings`, `HALFTONE_DEFAULTS` |
| `./riso` | `RISO_VERTEX_SHADER`, `RISO_FRAGMENT_SHADER`, `applyRisoUniforms`, maps, types |
| `./shaders` | `getShaderDefinition`, `getHalftoneShaderSource`, `registerShader`, registry, types |
| `./gl` | `compileShader`, `createProgram`, `setupFullscreenQuad`, `uploadTexture`, `readPixels`, `deleteRenderResources`, `getOrCreateProgram` |
| `./presets` | `HALFTONE_PRESETS_DATA`, `RISO_FULL_PRESETS_DATA`, `TEXTURE_PRESETS_DATA`, `SHADER_TYPES` |
| `./adapters/node` | `createNodeAdapter()`, `createHeadlessGLContext()`, `destroyHeadlessGLContext()` |
| `./adapters/browser` | `createCanvas`, `getWebGLContext`, `loadImage`, `toBlob` |

## Halftone — CMYK SVG (browser or node)

```ts
import { generateHalftoneSvg, HALFTONE_DEFAULTS } from '@visant/print-fx/halftone';

const svg = generateHalftoneSvg(rgbaPixels, width, height, {
  ...HALFTONE_DEFAULTS,
  frequency: 45,
  paperColor: '#ede6d6',
});
// → an <svg> string. Rasterize it with any canvas to get a PNG.
```

## Post-fx shader on the server (headless-gl)

```ts
import { getShaderDefinition } from '@visant/print-fx/shaders';
import { getOrCreateProgram, setupFullscreenQuad, uploadTexture, readPixels, deleteRenderResources } from '@visant/print-fx/gl';
import { createHeadlessGLContext } from '@visant/print-fx/adapters/node';

const VERTEX = `attribute vec2 a_position; attribute vec2 a_texCoord; varying vec2 v_texCoord;
void main(){ gl_Position = vec4(a_position,0.,1.); v_texCoord = a_texCoord; }`;

const gl = await createHeadlessGLContext(width, height);
const { fragmentShaderSource } = getShaderDefinition('vhs');
const program = getOrCreateProgram(gl, 'vhs', VERTEX, fragmentShaderSource);
gl.useProgram(program);
const buffers = setupFullscreenQuad(gl, program);
const tex = uploadTexture(gl, rgbaPixels, width, height);
gl.uniform1i(gl.getUniformLocation(program, 'iChannel0'), 0);
gl.uniform2f(gl.getUniformLocation(program, 'iResolution'), width, height);
gl.viewport(0, 0, width, height);
gl.drawArrays(gl.TRIANGLES, 0, 6);
const out = readPixels(gl, width, height);
deleteRenderResources(gl, { textures: [tex], buffers });
```

## Riso in the browser

```ts
import { RISO_VERTEX_SHADER, RISO_FRAGMENT_SHADER, applyRisoUniforms } from '@visant/print-fx/riso';
import { getWebGLContext, createCanvas } from '@visant/print-fx/adapters/browser';
import { getOrCreateProgram, setupFullscreenQuad, uploadTexture } from '@visant/print-fx/gl';

const gl = getWebGLContext(createCanvas(width, height))!;
const program = getOrCreateProgram(gl, 'riso', RISO_VERTEX_SHADER, RISO_FRAGMENT_SHADER);
gl.useProgram(program);
setupFullscreenQuad(gl, program);
const tex = uploadTexture(gl, rgbaPixels, width, height);
gl.activeTexture(gl.TEXTURE0);
gl.bindTexture(gl.TEXTURE_2D, tex);
applyRisoUniforms(gl, program, risoSettings, width, height);
gl.drawArrays(gl.TRIANGLES, 0, 6);
```

## Note on the two halftone paths

There are **two** halftone implementations of the same effect, kept distinct on purpose:

- `generateHalftoneSvg` (this package) — the CPU/SVG path used server-side, with explicit per-channel CMYK dot placement.
- A WebGL fragment-shader halftone (rotating-grid GPU dots) used by the browser ImageLab live preview, plus the `halftone` post-fx shader here.

They are different render strategies, not pixel-equivalent variants, so the package ships the SVG generator (deterministic, GL-free) under `./halftone` and the GPU halftone under `./shaders`.

## License

MIT
