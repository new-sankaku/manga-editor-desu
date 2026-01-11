[English](https://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker) | 
[日本語](https://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker/blob/main/README_JP.md) | 
[中文](https://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker/blob/main/README_CN.md)

# Manga Editor Desu! Pro Edition

A manga creation web application that connects to ComfyUI, A1111 WebUI, and Forge.  
You can use the demo website or download it to run in your browser.  
*Note: As the development of A1111/Forge is uncertain, we plan to only support ComfyUI in the future.

Support Status:
- ComfyUI: SD1.5, SDXL, Pony, Flux1 (You can also use your own Workflows)
- WebUI: SD1.5, SDXL, Pony
- Forge: SD1.5, SDXL, Pony, Flux1
*Image generation is done via ComfyUI or A1111 WebUI or Forge API.

All features can be used with just the demo website.
[Web Site: Desu!](https://new-sankaku.github.io/manga-editor-desu/)


If you want to download the files locally (which runs faster), use:
git clone https://github.com/new-sankaku/manga-editor-desu.git
cd manga-editor-desu
start index.html


The application supports various features such as image drag and drop, file selection import, Text2Image function, Image2Image function, and more.
For beginners, standard panel layouts are pre-installed, making it easy to create manga.
It also includes a knife tool for professional panel cutting, allowing you to freely cut panels. The functionality continues to evolve, and regular updates are recommended.

## Main Page
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/01_mainpage.webp" width="700">

### Image Drop
https://github.com/user-attachments/assets/7cf94e6c-fc39-4aed-a0a1-37ca70260fe4

### Speech Bubble(Template)
https://github.com/user-attachments/assets/6f1dae5f-b50f-4b04-8875-f0b07111f2ab

### Image Prompt Helper
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/03_prompthelper.webp" width="700">

## Support Language
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/02_trans.webp" height="400">

## Grid Line / Knife Mode
<div style="display: flex; align-items: flex-start;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/05_gridline.webp" height="350">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/06_knifemode.webp" height="350">
</div>

## Dark Mode
<div style="display: flex; align-items: flex-start;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/09_darkmode.webp" height="350">
</div>

## Blend Mode Sample
<div style="display: flex; align-items: flex-start;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/12_blend.webp" height="350">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/13_blend.webp" height="350">
</div>

## Effect
<div style="display: flex; align-items: flex-start;">
    <img src="https://new-sankaku.github.io/SP-MangaEditer-docs/04_gpix01.webp" height="350">
    <img src="https://new-sankaku.github.io/SP-MangaEditer-docs/04_gpix02.webp" height="350">
</div>

## Text, Speech Bubbles, Pen
<div style="display: flex; align-items: flex-start;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/08_speechbubble.webp" height="350">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/07_font.webp" height="350">
</div>



## Features
- **Multilingual Support**: English, Japanese, Korean, French, Chinese, Russian, Spanish, Portuguese
- **Page Presets**: Preset comic panel layouts.
- **Panels**: Create and customize panels. Adjust shape, color, line width, etc.
- **Speech Bubbles**: Over 40 speech bubble styles, each style can be configured with background color, line color, and transparency.
- **Custom Speech Bubbles**: Create speech bubbles by specifying coordinates or freehand. 7 types of lines available. Smoothing processing also available.
- **Random Cut**: Random panel cutting function that specifies the number of vertical and horizontal cuts, tilt angle, and line start position
- **Multiple Page Creation**: Function to cut multiple pages at once using random cut information
- **Auto Fit**: Generated images or dropped images in comic panels are automatically scaled and trimmed appropriately.
- **Overlay**: Display images dropped outside the frame as overlays.
- **Layers**: Manage images, text, and panels as layers familiar to graphic designers and artists.
- **Image Editing Functions**: Adjust angle, position, scale, changes along X and Y axes, horizontal flip, vertical flip.
- **Image Effects**: Sepia, grayscale, gamma, blur, vibrance, pixelation.
- **Image Effects (Glfx)**: Unsharp mask, zoom blur, dot screen, hex pixelate, ink, hue/saturation.
- **Text**: Vertical writing, horizontal writing, bold, shadow, outline, neon, various fonts suitable for comics.
- **Image Text**: Preset image text.
- **Tone Function**: Tone function common in manga backgrounds.
- **Effect 1**: One-click color image to black and white tone processing.
- **Effect 2**: 25 types of blend modes similar to those in Adobe Photoshop.
- **Effect 3**: Glow (blurred outline light) to image contours.
- **Undo/Redo Function**: Freely undo or redo changes during editing.
- **Project Save/Load**: Save and load work in progress, continue working from where you left off.
- **Settings Save/Load**: Save and load settings changed in extensions, enabling a consistent, hassle-free workflow.
- **Image Export**: Export completed pages in formats suitable for printing or digital distribution.
- **Text2Image**: Generate images directly in panels via WebUI, Forge, ComfyUI.
- **Image2Image**: Generate images directly in panels via WebUI.
- **Prompt Queue**: Batch queue prompts to easily generate different character versions in the same page or panel.
- **Pen/Eraser Tool**: Basic pen and eraser tools, change line width, color, line style, shadow. Erase lines or parts of images.
- **Canvas Zoom In/Zoom Out**: Basic pen and eraser tools, change line width, color, line style, shadow. Erase lines or parts of images.

# Installation
https://github.com/new-sankaku/manga-editor-desu.git
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/02_.webp" width="700">

## Development

### ESLint (Code Quality)
```bash
# Install dependencies
npm install

# Run lint check
npm run lint

# Auto-fix issues
npm run lint:fix
```

#### Naming Conventions
- Functions/Variables: `camelCase`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE` or `camelCase`

## How to Contribute
- **Bug Reports**: If you find a bug, please create a new issue in [Issues](https://github.com/new-sankaku/manga-editor-desu/issues) and include **[Bug]** in the title.
- **Feature Suggestions**: If you have ideas for new features, please create a new issue in [Issues](https://github.com/new-sankaku/manga-editor-desu/issues) and include **[Feature Request]** in the title.
- **Documentation Improvements**: If there are typos or errors in the documentation, please submit a pull request with possible corrections. You can also add it to [Issues](https://github.com/new-sankaku/manga-editor-desu/issues) if necessary.

## Communication
If you have questions or discussions about the project, please post in [Issues](https://github.com/new-sankaku/manga-editor-desu/issues) or join the [Discord](https://discord.gg/XCp7dyHj3N) server.

Thank you!