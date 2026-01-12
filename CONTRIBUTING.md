# Contributing to Manga Editor Desu!

Thank you for your interest in contributing! This guide will help you get started.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Submitting Changes](#submitting-changes)
- [Translation Guide](#translation-guide)

---

## Getting Started

### Prerequisites

- Git
- Node.js (for linting tools)
- A modern web browser (Chrome recommended)
- Python 3 (optional, for local server)

### Clone the Repository

```bash
git clone https://github.com/new-sankaku/manga-editor-desu.git
cd manga-editor-desu
npm install
```

---

## Development Setup

### Running Locally

**Option 1: Direct file access**
```bash
start index.html
```

**Option 2: Local server (recommended for full functionality)**
```bash
python 99_server.py
```
Then open `http://localhost:8000`

### Why use a local server?
Some browser security features restrict `file://` protocol access. Using a local server ensures all features work correctly.

---

## Code Style

### Formatting Rules

This project uses a specific formatting style:

- **No indentation** - Code has no leading tabs or spaces
- **Minimal whitespace** - Remove unnecessary spaces around operators, commas, etc.
- **camelCase** - Use camelCase for variables and functions
- **PascalCase** - Use PascalCase for classes
- **UPPER_SNAKE_CASE** - Use for constants (or camelCase)

### Auto-Format

Run the formatter before committing:

```bash
npm run format
```

This removes:
- Leading indentation
- Trailing whitespace
- Spaces around operators
- Spaces after commas/semicolons
- Spaces inside parentheses

It preserves:
- Spaces inside string literals
- Spaces inside comments
- Line breaks

### ESLint

```bash
# Check for issues
npm run lint

# Auto-fix issues
npm run lint:fix
```

### Logging

**Do NOT use `console.log()`**. Use the Logger system instead:

```javascript
// Create a logger for your module
var myLogger = new SimpleLogger('moduleName', LogLevel.DEBUG);

// Use it
myLogger.debug("Debug message");
myLogger.info("Info message");
myLogger.warn("Warning message");
myLogger.error("Error message");
```

Logger is defined in `js/core/logger.js`.
Log levels: `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`, `SILENT`

### API Response Properties

When working with external APIs:
- Keep API response property names as-is (e.g., `response.prompt_id`)
- Use camelCase for local variables (e.g., `var promptId = response.prompt_id;`)

---

## Project Structure

```
manga-editor-desu/
├── index.html          # Main entry point
├── js/                 # JavaScript source files
│   ├── core/           # Core functionality
│   ├── ui/             # UI components
│   └── shortcut.js     # Keyboard shortcuts
├── css/                # Stylesheets
├── 99_server.py        # Local development server
├── package.json        # Node.js dependencies
└── eslint.config.mjs   # ESLint configuration
```

### Excluded Directories

The following directories should not be searched or modified:
- `json_js/`
- `test/`
- `third/`
- `01_build/`
- `02_images_svg/`
- `03_images/`
- `99_doc/`
- `font/`

---

## Making Changes

### History Management (Undo/Redo)

When making changes that affect canvas history:

**Single operation:**
```javascript
// Automatic history save
canvas.add(object);
saveStateByManual();
```

**Multiple operations (prevent intermediate states):**
```javascript
changeDoNotSaveHistory();
canvas.remove(oldObject);
canvas.add(newObject);
changeDoSaveHistory();
saveStateByManual();  // Only final state is saved
```

**Per-object history control:**
```javascript
activeObject.saveHistory = false;  // Disable for this object
```

### Image Data Storage

When saving image data to `imageMap`:

- **Always use** `data:` URLs or JSON strings
- **Never use** `blob:` URLs (they become invalid after session ends)
- Use `convertImageMapBlobUrls()` to convert blob URLs before saving
- Use `JSON.stringify()` for objects (like 2D arrays)

### Browser Storage (localStorage)

The app uses `localStorage` for persisting user preferences. Here are the keys used:

| Key | Purpose | Location |
|-----|---------|----------|
| `localSettingsData` | API settings, generation parameters | `js/project-management.js` |
| `mode` | Dark/light mode preference | `js/ui/util/mode-change.js` |
| `language` | UI language setting | `js/ui/third/i18next.js` |
| `uiSettings` | Prompt Helper UI settings | `js/ui/imagePromptHelper/prompt-helper.js` |
| `CustomSet` | Custom prompt presets | `js/ui/imagePromptHelper/prompt-helper.js` |
| `startupIntroShown` | First-time tutorial flag | `js/ui/third/intro.js` |

**Guidelines:**
- Keep localStorage keys descriptive and unique
- Always use `JSON.stringify()` / `JSON.parse()` for objects
- Document new keys in this table when adding storage features

---

## Submitting Changes

### Bug Reports

1. Go to [Issues](https://github.com/new-sankaku/manga-editor-desu/issues)
2. Create a new issue with **[Bug]** in the title
3. Include:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Browser and OS version
   - Screenshots if applicable

### Feature Requests

1. Go to [Issues](https://github.com/new-sankaku/manga-editor-desu/issues)
2. Create a new issue with **[Feature Request]** in the title
3. Describe the feature and its use case

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run `npm run format` and `npm run lint`
5. Commit with a clear message
6. Push to your fork
7. Open a Pull Request

---

## Translation Guide

Translations are stored in `js/ui/third/i18next.js` in the `resources` constant.

### Adding New Translations

1. Create a new date-keyed entry (YYYYMMDD format)
2. Place it above existing entries
3. Add translations for all 10 languages:
   - `ja` - Japanese
   - `en` - English
   - `ko` - Korean
   - `fr` - French
   - `zh` - Chinese
   - `ru` - Russian
   - `es` - Spanish
   - `pt` - Portuguese
   - `th` - Thai
   - `de` - German

### Translation Tips

- Keep translations short (UI space is limited)
- Maintain consistency with existing terminology
- Test in the UI to ensure text fits

### Example

```javascript
const resources = {
  // New entry - add at top
  "20250112": {
    ja: "新しいテキスト",
    en: "New text",
    ko: "새 텍스트",
    fr: "Nouveau texte",
    zh: "新文本",
    ru: "Новый текст",
    es: "Nuevo texto",
    pt: "Novo texto",
    th: "ข้อความใหม่",
    de: "Neuer Text"
  },
  // Existing entries below...
};
```

---

## Questions?

- **GitHub Issues:** [https://github.com/new-sankaku/manga-editor-desu/issues](https://github.com/new-sankaku/manga-editor-desu/issues)

Thank you for contributing!
