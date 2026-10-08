# halftone-webgl

GPU-accelerated halftone effects for the web. Lightweight, interactive, Webflow-friendly.

<!-- badges -->
<!-- [![npm](https://img.shields.io/npm/v/halftone-webgl)](https://www.npmjs.com/package/halftone-webgl) -->
<!-- [![bundle](https://img.shields.io/bundlephobia/minzip/halftone-webgl)](https://bundlephobia.com/package/halftone-webgl) -->

## Features

- **GPU-powered** — Fragment-shader halftone math, runs entirely on the GPU
- **6 dot shapes** — circle, square, diamond, line, cross, ellipse
- **4 color modes** — mono, auto (source colors), CMYK separation, duotone
- **10 mouse interactions** — reveal, magnify, warp, ripple, vortex, colorShift, focus, comet, sparkle
- **Any source** — static images, video, webcam, or no source at all
- **Content overlay** — Children are auto-promoted above the canvas; buttons/links pause interaction on hover
- **Zero-config** — Works with just data attributes, no JavaScript required
- **~21 KB gzipped** (includes OGL WebGL abstraction)

## Quick Start (CDN)

Add a script tag and use data attributes — no build step needed.

```html
<script src="https://unpkg.com/halftone-webgl/dist/halftone-webgl.min.js"></script>

<div data-hwgl-element
     data-hwgl-source="photo.jpg"
     data-hwgl-shape="circle"
     data-hwgl-color-mode="mono"
     data-hwgl-interaction="sparkle"
     style="width: 100%; height: 400px;">
  <h1>Your content here</h1>
</div>
```

The library auto-initializes on `DOMContentLoaded` for every element with `data-hwgl-element`.

### Video Source

```html
<div data-hwgl-element
     data-hwgl-source="video.mp4"
     data-hwgl-interaction="sparkle"
     style="width: 100%; height: 400px;">
</div>
```

### Webcam Source

```html
<div data-hwgl-element
     data-hwgl-source="webcam"
     data-hwgl-interaction="warp"
     style="width: 100%; height: 400px;">
</div>
```

## Quick Start (npm)

```bash
npm install halftone-webgl
```

```js
import HalftoneWebGL from 'halftone-webgl';

const ht = new HalftoneWebGL({
  container: '#my-element',
  source: 'photo.jpg',
  shape: 'circle',
  colorMode: 'mono',
  interaction: 'sparkle',
});

// Update options at runtime
ht.set('frequency', 60);
ht.set({ shape: 'diamond', colorMode: 'cmyk' });

// Load a new source
await ht.loadSource('video.mp4');

// Clean up
ht.destroy();
```

## Data Attributes API

Every configuration option can be set via a `data-hwgl-*` attribute on the container element.

| Attribute | Config Key | Type | Default |
|---|---|---|---|
| `data-hwgl-element` | *(marker)* | — | — |
| `data-hwgl-source` | `source` | string | `null` |
| `data-hwgl-frequency` | `frequency` | number | `40` |
| `data-hwgl-angle` | `angle` | number | `0` |
| `data-hwgl-shape` | `shape` | string | `'circle'` |
| `data-hwgl-scale` | `scale` | number | `1.0` |
| `data-hwgl-softness` | `softness` | number | `0.5` |
| `data-hwgl-gap` | `gap` | number | `0` |
| `data-hwgl-contrast` | `contrast` | number | `1.8` |
| `data-hwgl-brightness` | `brightness` | number | `1.0` |
| `data-hwgl-invert` | `invert` | boolean | `false` |
| `data-hwgl-min-dot` | `minDot` | number | `0` |
| `data-hwgl-color-mode` | `colorMode` | string | `'mono'` |
| `data-hwgl-color` | `color` | hex string | `'#E85002'` |
| `data-hwgl-color-b` | `colorB` | hex string | `'#000000'` |
| `data-hwgl-bg-color` | `bgColor` | hex string | `'#050510'` |
| `data-hwgl-cmyk-angles` | `cmykAngles` | comma-separated | `15,75,0,45` |
| `data-hwgl-fit` | `fit` | string | `'cover'` |
| `data-hwgl-interaction` | `interaction` | string | `'none'` |
| `data-hwgl-radius` | `radius` | number | `0.3` |
| `data-hwgl-strength` | `strength` | number | `0.5` |
| `data-hwgl-trail-fade` | `trailFade` | number | `0.03` |
| `data-hwgl-dpr` | `dpr` | `'auto'` or number | `'auto'` |
| `data-hwgl-z-index` | `zIndex` | number | `0` |
| `data-hwgl-pause-selector` | `pauseSelector` | CSS selector | `'a, button, [data-hwgl-pause]'` |

## JavaScript API

### Constructor

```js
const ht = new HalftoneWebGL({
  container: '#my-element', // CSS selector or DOM element (required)
  source: 'photo.jpg',     // any config option can be passed here
  // ...
});
```

### Methods

#### `set(key, value)` / `set({ ... })`

Update one or more configuration options at runtime.

```js
ht.set('frequency', 60);
ht.set({ shape: 'diamond', colorMode: 'cmyk', contrast: 2.5 });
```

#### `loadSource(src)`

Load a new image, video, or webcam source. Returns a Promise.

```js
await ht.loadSource('photo.jpg');       // image URL
await ht.loadSource('video.mp4');       // video URL
await ht.loadSource('webcam');          // webcam
await ht.loadSource(myVideoElement);    // HTMLVideoElement
await ht.loadSource(myImageElement);    // HTMLImageElement
```

#### `resize()`

Manually trigger a resize. Automatically called via ResizeObserver — you rarely need this.

#### `pause()` / `resume()`

Stop or start the animation loop.

```js
ht.pause();
ht.resume();
```

#### `snapshot(type?, quality?)`

Capture the current frame as a data URL.

```js
const dataUrl = ht.snapshot();                        // PNG
const dataUrl = ht.snapshot('image/jpeg', 0.92);      // JPEG at 92% quality
```

#### `destroy()`

Clean up all resources — stops animation, removes the canvas, releases video/webcam streams, clears event listeners.

```js
ht.destroy();
```

### Properties

| Property | Type | Description |
|---|---|---|
| `canvas` | `HTMLCanvasElement` | The WebGL canvas element |
| `config` | `object` | Copy of the current configuration |
| `isPlaying` | `boolean` | Whether the animation loop is running |

### Events

```js
ht.on('ready', () => { /* first frame rendered */ });
ht.on('sourceload', () => { /* source texture loaded */ });
ht.on('resize', ({ w, h }) => { /* container resized */ });
ht.on('error', (err) => { /* something went wrong */ });
```

| Event | Data | Description |
|---|---|---|
| `ready` | — | First frame rendered or source loaded |
| `sourceload` | — | Source texture loaded successfully |
| `resize` | `{ w, h }` | Container was resized |
| `error` | `Error` | An error occurred |

## Configuration Reference

### Screen

| Option | Type | Range | Default | Description |
|---|---|---|---|---|
| `frequency` | number | 5–150 | `40` | Dot density (dots per row) |
| `angle` | number | degrees | `0` | Screen rotation angle |

### Dot

| Option | Type | Values / Range | Default | Description |
|---|---|---|---|---|
| `shape` | string | `circle` `square` `diamond` `line` `cross` `ellipse` | `'circle'` | Dot shape |
| `scale` | number | 0.1–2 | `1.0` | Dot size multiplier |
| `softness` | number | 0–1 | `0.5` | Edge softness |
| `gap` | number | 0–1 | `0` | Gap between dots |

### Tone

| Option | Type | Range | Default | Description |
|---|---|---|---|---|
| `contrast` | number | 0.2–5 | `1.8` | Tonal contrast |
| `brightness` | number | 0.1–3 | `1.0` | Brightness multiplier |
| `invert` | boolean | — | `false` | Invert tones |
| `minDot` | number | 0–1 | `0` | Minimum dot size |

### Color

| Option | Type | Values / Range | Default | Description |
|---|---|---|---|---|
| `colorMode` | string | `mono` `auto` `cmyk` `duotone` | `'mono'` | Color rendering mode |
| `color` | hex string | — | `'#E85002'` | Primary dot color (mono highlight, duotone highlight) |
| `colorB` | hex string | — | `'#000000'` | Secondary color (duotone shadow) |
| `bgColor` | hex string | — | `'#050510'` | Background color |
| `cmykAngles` | number[4] | degrees | `[15, 75, 0, 45]` | Per-channel screen angles [C, M, Y, K] |

### Source

| Option | Type | Values | Default | Description |
|---|---|---|---|---|
| `source` | string / null | URL, `'webcam'`, null | `null` | Image/video URL or webcam |
| `fit` | string | `cover` `contain` `fill` | `'cover'` | How the source fits the container |

### Interaction

| Option | Type | Values / Range | Default | Description |
|---|---|---|---|---|
| `interaction` | string | `none` `reveal` `magnify` `warp` `ripple` `vortex` `colorShift` `focus` `comet` `sparkle` | `'none'` | Mouse interaction effect |
| `radius` | number | 0–1 | `0.3` | Interaction area radius |
| `strength` | number | 0–1 | `0.5` | Interaction intensity |
| `trailFade` | number | 0–1 | `0.03` | Trail fade rate (comet/sparkle) |

### Container

| Option | Type | Values | Default | Description |
|---|---|---|---|---|
| `dpr` | `'auto'` / number | — | `'auto'` | Device pixel ratio (auto caps at 2) |
| `zIndex` | number | — | `0` | Canvas z-index |
| `pauseSelector` | string | CSS selector | `'a, button, [data-hwgl-pause]'` | Elements that pause interaction on hover |

## Content Overlay Pattern

Any children inside the halftone container are automatically promoted above the canvas:

```html
<div data-hwgl-element data-hwgl-source="bg.jpg" data-hwgl-interaction="sparkle"
     style="height: 400px;">
  <!-- These sit above the halftone canvas automatically -->
  <h1>Heading</h1>
  <p>Paragraph text — fully selectable.</p>
  <button>Clickable button</button>
</div>
```

**How it works:**
- The canvas is injected with `position: absolute; pointer-events: none`
- Child elements get `position: relative; z-index: 1`
- Buttons, links, and `[data-hwgl-pause]` elements pause the interaction effect on hover so they're easy to click

Custom elements can opt into pause behavior:

```html
<div data-hwgl-pause>This pauses interaction on hover</div>
```

## Browser Support

Requires **WebGL 1** — supported in all modern browsers (Chrome, Firefox, Safari, Edge).

## License

MIT
