<div align="center">
	<img src="https://github.com/9am/9am.github.io/assets/1435457/3310c374-8cd7-4c2b-ad68-c349ede61598" alt="img-tissue" width="180" height="180" />
	<h1>&lt;img-halftone&gt;</h1>
	<p>A web component turns &lt;img&gt; into halftone.🥑</p>
    <p>
        <a href="https://github.com/9am/img-halftone/blob/main/LICENSE">
            <img alt="GitHub" src="https://img.shields.io/github/license/9am/img-halftone?style=flat-square&color=success">
        </a>
        <a href="https://www.npmjs.com/package/@9am/img-halftone">
            <img alt="npm" src="https://img.shields.io/npm/v/@9am/img-halftone?style=flat-square&color=orange">
        </a>
        <a href="https://www.npmjs.com/package/@9am/img-halftone">
            <img alt="npm" src="https://img.shields.io/npm/dt/@9am/img-halftone?style=flat-square&color=blue">
        </a>
        <a href="https://bundlephobia.com/package/@9am/img-halftone@latest">
            <img alt="npm bundle size" src="https://img.shields.io/bundlephobia/minzip/@9am/img-halftone?style=flat-square">
        </a>
    </p>
</div>

## Features
- 🎨 Print halftone image with **CMYK**.
- ⚙️  Halftone is performed in **web worker**.
- 📜 Render with **Canvas** or **HTML element**.
- 🧩 Various **dot shapes** supported.
- 🔖 **Alt** support for **Accessibility**.
- 🛎 A **loading** className on the host.
- 💽 **≈ 3kB** minzipped.

## Demo

|Description|Live demo|
|:---------:|:-------:|
|Default setting with a zoom-in-out animation|[**codepen**](https://codepen.io/9am/pen/jOQdrmX)|
|Render with different `varient`|[**codepen**](https://codepen.io/9am/pen/vYQbaRJ)|
|Render with different `cellsize`|[**codepen**](https://codepen.io/9am/pen/OJadweB)|
|Render with different `shape`|[**codepen**](https://codepen.io/9am/pen/YzRBOKY)|
|Concurrent processing|[**codepen**](https://codepen.io/9am/pen/XWyOBjL)|


## Usage

#### Install

```sh
npm install @9am/img-halftone
```

```js
import '@9am/img-halftone'
```

#### Or use a CDN link

```html
<script type="module" src="https://cdn.skypack.dev/@9am/img-halftone"></script>
```

```html
<script src="https://www.unpkg.com/@9am/img-halftone"></script>
```

#### HTML

```html
<img-halftone src="img.png"></img-halftone>
```

## Documentation

### &lt;img-halftone&gt; attributes

|Name|Type|Default|Description|
|:--:|:--:|:-----:|:----------|
|`src`|{string}|**Required**|The image URL|
|`alt`|{string}|img-halftone|The alternative text description|
|`varient`|{canvas \| grid}|canvas|The Render type </br> *(Notice: using 'grid' with small cellsize will cause layout performance problem.)*|
|`cellsize`|{number}|4|The cell size for each dot in pixel|
|`shape`|{circle \| triangle \| rectangle \| hexagon }|circle|The shape of dots|

## License
[MIT](LICENSE)
