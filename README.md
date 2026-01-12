[English](https://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker) |
[日本語](https://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker/blob/main/README_JP.md) |
[中文](https://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker/blob/main/README_CN.md)

# Manga Editor Desu! Pro Edition

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub Stars](https://img.shields.io/github/stars/new-sankaku/manga-editor-desu?style=social)](https://github.com/new-sankaku/manga-editor-desu)

A web-based manga creation tool with AI image generation support. Create professional manga pages directly in your browser.

**[Try the Demo](https://new-sankaku.github.io/manga-editor-desu/)** - No installation required!

<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/01_mainpage.webp" width="700">

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [AI Image Generation Setup](#ai-image-generation-setup)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Gallery](#gallery)
- [FAQ](#faq)
- [Support](#support)
- [License](#license)

---

## Features

### Core Features
- **Panel Layouts** - Pre-built templates and custom panel creation with knife tool
- **Speech Bubbles** - 40+ styles with customizable colors and transparency
- **Text Tools** - Vertical/horizontal text, manga fonts, shadows, outlines, neon effects
- **Layer Management** - Organize images, text, and panels with familiar layer controls
- **Undo/Redo** - Full history support for all editing operations

### Image Editing
- **Auto-Fit** - Images automatically scale and trim to fit panels
- **Adjustments** - Rotation, position, scale, flip horizontal/vertical
- **Effects** - Sepia, grayscale, blur, pixelation, gamma, vibrance
- **Advanced Effects** - Unsharp mask, zoom blur, dot screen, hex pixelate, ink, hue/saturation
- **Blend Modes** - 25 Photoshop-style blend modes
- **Tone Processing** - Convert color images to manga-style tones

### AI Integration
- **Text2Image** - Generate images directly in panels
- **Image2Image** - Transform existing images with AI
- **Prompt Queue** - Batch generate multiple variations
- **Supported Backends:**
  - ComfyUI (SD1.5, SDXL, Pony, Flux1, Custom Workflows)
  - A1111 WebUI (SD1.5, SDXL, Pony)
  - Forge (SD1.5, SDXL, Pony, Flux1)

### Export & Save
- **Project Save/Load** - Continue work anytime with `.json` project files
- **Settings Save/Load** - Preserve your workflow preferences
- **Image Export** - Export pages for print or digital distribution

### Supported Languages
English, Japanese, Korean, French, Chinese, Russian, Spanish, Portuguese, Thai, German

<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/02_trans.webp" height="300">

---

## Quick Start

### Option 1: Use Online (Recommended)
Visit **[https://new-sankaku.github.io/manga-editor-desu/](https://new-sankaku.github.io/manga-editor-desu/)**

No setup required. Works with all features including AI generation when connected to a local backend.

### Option 2: Run Locally
```bash
git clone https://github.com/new-sankaku/manga-editor-desu.git
cd manga-editor-desu
start index.html
```

---

## Requirements

### Browser Support
- Chrome (Recommended)
- Firefox
- Edge
- Safari

### For AI Image Generation (Optional)
One of the following:
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Stable Diffusion WebUI (A1111)](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
- [Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge)

---

## AI Image Generation Setup

### ComfyUI Setup

1. Start ComfyUI with API access enabled:
   ```bash
   python main.py --listen --enable-cors-header
   ```

2. In Manga Editor, click the **Settings** icon
3. Select **ComfyUI** as the backend
4. Enter the API URL (default: `http://127.0.0.1:8188`)
5. Click **Connect**

### A1111 WebUI / Forge Setup

1. Start WebUI with API access:
   ```bash
   ./webui.sh --api --cors-allow-origins=*
   ```
   Or add to `webui-user.bat`:
   ```
   set COMMANDLINE_ARGS=--api --cors-allow-origins=*
   ```

2. In Manga Editor, click the **Settings** icon
3. Select **WebUI** or **Forge** as the backend
4. Enter the API URL (default: `http://127.0.0.1:7860`)
5. Click **Connect**

---

## Keyboard Shortcuts

| Action | Windows/Linux | Mac |
|--------|---------------|-----|
| Undo | `Ctrl + Z` | `Cmd + Z` |
| Redo | `Ctrl + Y` | `Cmd + Y` |
| Copy | `Ctrl + C` | `Cmd + C` |
| Paste | `Ctrl + V` | `Cmd + V` |
| Delete | `Delete` / `Backspace` | `Delete` / `Backspace` |
| Save Project | `Ctrl + S` | `Cmd + S` |
| Load Project | `Ctrl + O` | `Cmd + O` |
| Toggle Grid | `Ctrl + G` | `Ctrl + G` |
| Toggle Layers Panel | `Ctrl + L` | `Ctrl + L` |
| Toggle Controls | `Ctrl + K` | `Ctrl + K` |
| Zoom In | `Ctrl + 8` | `Ctrl + 8` |
| Zoom Out | `Ctrl + 9` | `Ctrl + 9` |
| Zoom Fit | `Ctrl + 0` | `Ctrl + 0` |
| Move Object | `Arrow Keys` | `Arrow Keys` |
| Move Object (Fast) | `Shift + Arrow Keys` | `Shift + Arrow Keys` |
| Layer Up | `Ctrl + Up` | `Cmd + Up` |
| Layer Down | `Ctrl + Down` | `Cmd + Down` |
| Deselect | `Escape` | `Escape` |

---

## Gallery

### Image Drop
https://github.com/user-attachments/assets/7cf94e6c-fc39-4aed-a0a1-37ca70260fe4

### Speech Bubbles
https://github.com/user-attachments/assets/6f1dae5f-b50f-4b04-8875-f0b07111f2ab

### Prompt Helper
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/03_prompthelper.webp" width="700">

### Grid & Knife Mode
<div style="display: flex; gap: 10px;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/05_gridline.webp" height="300">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/06_knifemode.webp" height="300">
</div>

### Dark Mode
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/09_darkmode.webp" height="300">

### Blend Modes
<div style="display: flex; gap: 10px;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/12_blend.webp" height="300">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/13_blend.webp" height="300">
</div>

### Effects
<div style="display: flex; gap: 10px;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/04_gpix01.webp" height="300">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/04_gpix02.webp" height="300">
</div>

### Text & Speech Bubbles
<div style="display: flex; gap: 10px;">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/08_speechbubble.webp" height="300">
<img src="https://new-sankaku.github.io/SP-MangaEditer-docs/07_font.webp" height="300">
</div>

---

## FAQ

### Q: Can I use this without AI image generation?
**A:** Yes! All editing features work standalone. AI generation is optional and requires a separate backend (ComfyUI/WebUI/Forge).

### Q: Why won't my AI backend connect?
**A:** Common solutions:
1. Ensure CORS headers are enabled (`--cors-allow-origins=*` or `--enable-cors-header`)
2. Check the API URL is correct
3. Verify the backend is running
4. Try using `http://127.0.0.1` instead of `localhost`

### Q: Can I use custom ComfyUI workflows?
**A:** Yes! You can import and use your own ComfyUI workflows.

### Q: Where are my projects saved?
**A:** Projects are saved as `.json` files to your local downloads folder. Load them anytime to continue editing.

### Q: What data is stored in my browser?
**A:** The app uses browser localStorage to remember your preferences:
- Language and dark/light mode settings
- API connection settings (URL, parameters)
- Custom prompt presets
- Tutorial completion status

This data stays in your browser and is never sent to any server.

### Q: How do I clear saved settings?
**A:** Open browser DevTools (F12) → Application tab → Local Storage → Clear the site data. Or use your browser's "Clear site data" feature.

### Q: Is my data sent anywhere?
**A:** No. Everything runs in your browser. AI requests go only to your local backend.

---

## Support

- **Bug Reports & Feature Requests:** [GitHub Issues](https://github.com/new-sankaku/manga-editor-desu/issues)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

---

Made with love for manga creators worldwide.
