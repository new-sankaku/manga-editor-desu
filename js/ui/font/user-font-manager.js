//User Font Manager
const fmUserFontManager = {
  tagify: null,
  createModal() {
    const modalHTML = `<div class="fm-modalOverlay" id="fm-modalOverlay">
<div class="fm-fontManagerModal" id="fm-fontManagerModal">
<span class="fm-modalCloseButton" onclick="fontManager.closeUserFontManager()">&times;</span>
<div id="fm-errorMessage" class="fm-errorMessage">${getText("existsFontError")}</div>
<div class="fm-modalLayout">
<div class="fm-fontInputSection">
<div class="fm-fontInputContainer">
<h3 data-i18n="ft_addLocalFontTitle"></h3>
<h4 data-i18n="ft_addLocalFontTitle_warning"></h4>
<textarea id="fm-localFontInput" data-i18n-placeholder="ft_placeholderLocal" placeholder="Arial&#10;Helvetica&#10;Times New Roman"></textarea>
<button onclick="fontManager.registerLocalFont()" data-i18n="ft_add">追加</button>
</div>
<div class="fm-fontInputContainer">
<h3 data-i18n="ft_addWebFontTitle"></h3>
<textarea id="fm-webFontUrlInput" data-i18n-placeholder="ft_placeholderWeb" placeholder="https://fonts.googleapis.com/css2?amily=Roboto"></textarea>
<button onclick="fontManager.registerWebFont()" data-i18n="ft_add"></button>
</div>
<div class="fm-fontInputContainer">
<h3 data-i18n="ft_addFileFontTitle"></h3>
<input type="file" id="fm-fontFileUpload" accept=".ttf,.otf,.woff,.woff2" multiple>
<div class="fm-uploadInstructions" data-i18n="ft_instruction"></div>
</div>
</div>
<div class="fm-fontListSection">
<div class="fm-sectionTitle" data-i18n="ft_registered"></div>
<div id="fm-registeredFontList"></div>
</div>
</div>
</div>
</div>`;

const style = document.createElement('style');
style.textContent = `
  .fm-errorMessage {
    color: #FAD26A;
    padding: 2px;
    margin: 0 0 15px 0;
    text-align: center;
  }
`;
document.head.appendChild(style);

    document.body.insertAdjacentHTML("beforeend", modalHTML);
    this.initializeTagify();
    this.setupFileUploadHandler();
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      const key = element.getAttribute("data-i18n");
      element.textContent = i18next.t(key);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
      const key = element.getAttribute("data-i18n-placeholder");
      element.placeholder = i18next.t(key);
    });
  },
  initializeTagify() {
    this.tagify = new Tagify($("fm-registeredFontList"), {
      enforceWhitelist: true,
      whitelist: [],
      transformTag: (tag) => {
        tag.style = `--tag-bg:${tag.color || "#4CAF50"}`;
      },
      dropdown: {
        enabled: 0,
      },
      userInput: false,
    });
    this.tagify.on("remove", (event) => {
      fontManager.unregisterFont(event.detail.data);
    });
  },
  setupFileUploadHandler() {
    $("fm-fontFileUpload").addEventListener("change", async (event) => {
      const files = event.target.files;
      for (const file of files) {
        try {
          const buffer = await file.arrayBuffer();
          const fontName = file.name.replace(/\.[^/.]+$/, "");
          await fontManager.registerFontFromBuffer(buffer, fontName);
        } catch (error) {
          fontLogger.error("error, ", error);
        }
      }
    });
  },
  async updateFontList() {
    // console.log("fmUserFontManager updateFontList start");
    if (!this.tagify) return;

    const fonts = await fmFontRepository.getAllFonts();
    // console.log(
    //   "fmUserFontManager updateFontList all fonts ",
    //   JSON.stringify(fonts)
    // );
    const formattedFonts = fonts.map((font) => ({
      value: font.name,
      color:
        font.type === "local"
          ? "#4CAF50"
          : font.type === "web"
          ? "#2196F3"
          : "#FF9800",
    }));
    this.tagify.settings.whitelist = formattedFonts;
    this.tagify.removeAllTags();
    this.tagify.addTags(formattedFonts);
  },
};
