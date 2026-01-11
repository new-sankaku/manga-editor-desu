const iphHtmlContent=`
  <div class="iph-container">
    <div class="iph-top-bar">
      <input type="text" id="iph-name-input" data-i18n="[placeholder]name">
      <button id="iph-save-button" data-i18n="save"></button>
      <select id="iph-language-dropdown" class="iph-dropdown" hidden>
        <option value="en" data-i18n="english" data-flag="gb">English</option>
        <option value="ja" data-i18n="japanese" data-flag="jp">日本語</option>
      </select>
      <select id="iph-model-dropdown" class="iph-dropdown" hidden>
        <option value="SDXL">SDXL</option>
        <option value="Pony">Pony</option>
      </select>
    </div>
    <div class="iph-upper-section">
      <div class="iph-column iph-column-2">
        <h5 data-i18n="category"></h5>
        <div id="iph-category-container" class="iph-scroll-area"></div>
      </div>
      <div class="iph-column iph-column-6">
        <h5 data-i18n="subcategory"></h5>
        <div id="iph-sub-category-container" class="iph-scroll-area"></div>
      </div>
      <div class="iph-column iph-column-2">
        <h5>
          <span data-i18n="selected"></span>
          <button id="iph-download-button" class="iph-icon-button" disabled data-i18n="[title]download">
            <i class="fas fa-download"></i>
          </button>
          <button id="iph-copy-button" class="iph-icon-button" disabled data-i18n="[title]copy">
            <i class="fas fa-copy"></i>
          </button>
        </h5>
        <div id="iph-selected-tags" class="iph-scroll-area"></div>
        <textarea id="iph-free-input" data-i18n="[placeholder]freeInput"></textarea>
      </div>
    </div>
    <div id="iph-image-container"></div>
  </div>
`;