class FontSelectorManager {
  static instances = [];
 
  static addInstance(instance) {
    this.instances.push(instance);
  }
 
  static reloadAll() {
    this.instances.forEach((instance) => instance.reload());
  }
 
  static closeAllDropdowns(exceptId = null) {
    this.instances.forEach((instance) => {
      if (instance.targetId !== exceptId) {
        instance.closeDropdown();
      }
    });
  }
}

class FontSelector {
  constructor(targetId, title = "") {
    this.targetId = targetId;
    this.title = title;
    this.savedFont = null;
    FontSelectorManager.addInstance(this);
    this.initialize();
  }
 
  createHTML() {
    return `<div class="fm-font-dropdown">
            <button class="fm-dropdown-trigger">
            <span id="fm-selected-font-${this.targetId}">${this.title}</span>
            </button>
            <div class="fm-dropdown-content" id="fm-fontDropdown-${this.targetId}"></div>
            </div>`;
  }
 
  initializeStyles() {
    let fmStyleSheet = document.createElement("style");
    Object.entries(fmFontData).forEach(([category, data]) => {
      data.fonts.forEach((font) => {
        fmStyleSheet.textContent += `.fm-font-${font.name.replace(/[\s-]/g, "_")}{font-family:"${font.name}",sans-serif; border-left:2px solid ${data.color}!important;}`;
      });
    });
    if (!$("fm-styles")) {
      fmStyleSheet.id = "fm-styles";
      document.head.appendChild(fmStyleSheet);
    }
  }
 
  createFontOption(font, color) {
    var langText = getSampleTextByLanguageCode();
    const option = document.createElement("div");
    option.className = `fm-font-option fm-font-${font.name.replace(/[\s-]/g,"_")}`;
    option.dataset.font = font.name;
    option.style.display = "flex";
    option.style.justifyContent = "space-between";
    option.style.alignItems = "center";
    const fontNameSpan = document.createElement("span");
    fontNameSpan.textContent = font.name;
    fontNameSpan.style.fontSize = "1.0em";
    const sampleTextSpan = document.createElement("span");
    sampleTextSpan.textContent = langText;
    sampleTextSpan.style.fontSize = "0.8em";
    option.appendChild(fontNameSpan);
    option.appendChild(sampleTextSpan);
    return option;
  }
  
  




  reload() {
    this.savedFont = $(`fm-selected-font-${this.targetId}`).textContent;
    this.initialize();
    if (this.savedFont && this.savedFont !== this.title) {
      const fmSelectedFont = $(`fm-selected-font-${this.targetId}`);
      fmSelectedFont.textContent = this.savedFont;
      const fontNameClass = this.savedFont.replace(/[\s-]/g, "_");
      fmSelectedFont.className = `fm-font-${fontNameClass}`;
    }
  }
 
  closeDropdown() {
const dropdown = $(`fm-fontDropdown-${this.targetId}`);
if (dropdown) {
dropdown.classList.remove("fm-show");
dropdown.style.removeProperty('top');
dropdown.style.removeProperty('left');
dropdown.style.removeProperty('maxHeight');
dropdown.style.removeProperty('maxWidth');
this.resetGridColumns(dropdown);
}
}

resetGridColumns(dropdown) {
const grids = dropdown.querySelectorAll('.fm-font-grid');
grids.forEach(g => g.style.removeProperty('grid-template-columns'));
}

setGridColumns(dropdown, cols) {
const grids = dropdown.querySelectorAll('.fm-font-grid');
grids.forEach(g => {
g.style.gridTemplateColumns = `repeat(${cols},1fr)`;
});
}

findHorizontalPosition(w, menuRect, triggerRect, vW, margin) {
const candidates = [];
if (menuRect) {
candidates.push(menuRect.right);
candidates.push(menuRect.left - w);
}
candidates.push(triggerRect.left);
candidates.push(Math.round((vW - w) / 2));
candidates.push(vW - w - margin);
candidates.push(margin);
for (const l of candidates) {
if (l >= margin && l + w <= vW - margin) return l;
}
if (w <= vW - margin * 2) return Math.max(margin, vW - w - margin);
return margin;
}

getFixedOffset(dropdown) {
dropdown.style.top = '0px';
dropdown.style.left = '0px';
const rect = dropdown.getBoundingClientRect();
return {x:rect.left,y:rect.top};
}

updateDropdownPosition(trigger, dropdown) {
const margin = 8;
const vH = window.innerHeight;
const vW = window.innerWidth;
const triggerRect = trigger.getBoundingClientRect();
dropdown.style.visibility = 'hidden';
dropdown.style.top = '0px';
dropdown.style.left = '0px';
dropdown.style.removeProperty('maxHeight');
dropdown.style.removeProperty('maxWidth');
this.resetGridColumns(dropdown);
const offset = this.getFixedOffset(dropdown);
const menuEl = trigger.closest('.fabricjs-object-menu');
const menuRect = menuEl ? menuEl.getBoundingClientRect() : null;
const maxAvailW = vW - margin * 2;
const maxAvailH = vH - margin * 2;
const columnOptions = [4,3,2,1];
let bestLeft = margin;
let bestTop = margin;
let bestCols = 1;
let bestMaxH = maxAvailH;
let needsMaxH = true;
for (const cols of columnOptions) {
this.setGridColumns(dropdown, cols);
const w = dropdown.scrollWidth;
const h = dropdown.scrollHeight;
if (w > maxAvailW) continue;
const left = this.findHorizontalPosition(w, menuRect, triggerRect, vW, margin);
let top = triggerRect.top;
if (h <= maxAvailH) {
if (top + h > vH - margin) top = vH - margin - h;
if (top < margin) top = margin;
bestLeft = left;
bestTop = top;
bestCols = cols;
needsMaxH = false;
break;
}
bestLeft = left;
bestTop = margin;
bestCols = cols;
bestMaxH = maxAvailH;
needsMaxH = true;
break;
}
this.setGridColumns(dropdown, bestCols);
if (needsMaxH) dropdown.style.maxHeight = `${bestMaxH}px`;
if (dropdown.scrollWidth > maxAvailW) dropdown.style.maxWidth = `${maxAvailW}px`;
dropdown.style.top = `${bestTop - offset.y}px`;
dropdown.style.left = `${bestLeft - offset.x}px`;
dropdown.style.visibility = '';
}
 
  initializeDropdown() {
    const container = $(this.targetId);
    if (!container) return;
    container.innerHTML = this.createHTML();
 
    const fmDropdown = $(`fm-fontDropdown-${this.targetId}`);
    const fmTrigger = container.querySelector(".fm-dropdown-trigger");
    const fmSelectedFont = $(`fm-selected-font-${this.targetId}`);
 
    Object.entries(fmFontData).forEach(([category, data]) => {
      const categoryDiv = document.createElement("div");
      categoryDiv.className = "fm-font-category";
 
      const titleDiv = document.createElement("div");
      titleDiv.className = "fm-category-title";
      titleDiv.textContent = getText(category);
      titleDiv.style.borderColor = data.color;
 
      const gridDiv = document.createElement("div");
      gridDiv.className = "fm-font-grid";
      if (data.fonts.length == 0) {
        return;
      }
 
      data.fonts.forEach((font) => {
        const option = this.createFontOption(font, data.color);
        option.addEventListener("click", () => {

          const activeObject = canvas.getActiveObject();
          if(activeObject){
            activeObject.fontFamily=font.name;
            canvas.requestRenderAll();
          }
          fmSelectedFont.textContent = font.name;
          fmSelectedFont.className = `fm-font-${font.name.replace(/[\s-]/g,"_")}`;
          fmDropdown.classList.remove("fm-show");
          this.savedFont = font.name;
          const event = new CustomEvent(this.targetId, {
            detail: {
              fontName: font.name,
            },
          });
          document.dispatchEvent(event);
        });
        gridDiv.appendChild(option);
      });
 
      categoryDiv.appendChild(titleDiv);
      categoryDiv.appendChild(gridDiv);
      fmDropdown.appendChild(categoryDiv);
    });
 
    fmTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const isCurrentlyShown = fmDropdown.classList.contains("fm-show");
      FontSelectorManager.closeAllDropdowns(
        isCurrentlyShown ? null : this.targetId
      );
      fmDropdown.classList.toggle("fm-show");
      
      if (!isCurrentlyShown) {
        this.updateDropdownPosition(fmTrigger, fmDropdown);
      }
    });

    document.addEventListener("scroll", () => {
      if (fmDropdown.classList.contains("fm-show")) {
        this.closeDropdown();
      }
    });
  }
 
  initialize() {
    this.initializeStyles();
    this.initializeDropdown();
  }
}
 
document.addEventListener("DOMContentLoaded", async () => {
  await fontManager.init();
  new FontSelector("fontSelector", "Arial");

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".fm-font-dropdown")) {
      FontSelectorManager.closeAllDropdowns();
    }
  });
});


function getSampleTextByLanguageCode() {
  const currentLang = i18next.language;
  switch (currentLang) {
    case 'en':
      return 'ABC';
    case 'ja':
      return 'サンプル ABC';
    case 'ko':
      return '샘플 ABC';
    case 'fr':
      return 'ABC';
    case 'zh':
      return '示例 ABC';
    case 'ru':
      return 'Пример ABC';
    case 'es':
      return 'Ejemplo ABC';
    case 'pt':
      return 'ABC';
    case 'de':
      return 'Beispiel ABC';
    default:
      return 'Sample ABC';
  }
}
