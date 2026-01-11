// ja en ko fr zh ru es pt th de
// "20250322": {
//   ja: {},
//   en: {},
//   ko: {},
//   fr: {},
//   zh: {},
//   ru: {},
//   es: {},
//   pt: {},
//   th: {},
//   de: {}
// },


//マージされるので日付単位で分けて入れたらOK
const resources = {
"20260111": {
"ja": {"unsupportedProjectFileFormat": "非対応のファイル形式", "unsupportedProjectFileFormatMessage": ".zipまたは.lz4ファイルを選択してください"},
"en": {"unsupportedProjectFileFormat": "Unsupported file format", "unsupportedProjectFileFormatMessage": "Please select a .zip or .lz4 file"},
"ko": {"unsupportedProjectFileFormat": "지원되지 않는 파일 형식", "unsupportedProjectFileFormatMessage": ".zip 또는 .lz4 파일을 선택하세요"},
"fr": {"unsupportedProjectFileFormat": "Format de fichier non pris en charge", "unsupportedProjectFileFormatMessage": "Veuillez sélectionner un fichier .zip ou .lz4"},
"zh": {"unsupportedProjectFileFormat": "不支持的文件格式", "unsupportedProjectFileFormatMessage": "请选择.zip或.lz4文件"},
"ru": {"unsupportedProjectFileFormat": "Неподдерживаемый формат файла", "unsupportedProjectFileFormatMessage": "Пожалуйста, выберите файл .zip или .lz4"},
"es": {"unsupportedProjectFileFormat": "Formato de archivo no compatible", "unsupportedProjectFileFormatMessage": "Por favor seleccione un archivo .zip o .lz4"},
"pt": {"unsupportedProjectFileFormat": "Formato de arquivo não suportado", "unsupportedProjectFileFormatMessage": "Por favor, selecione um arquivo .zip ou .lz4"},
"th": {"unsupportedProjectFileFormat": "รูปแบบไฟล์ไม่รองรับ", "unsupportedProjectFileFormatMessage": "กรุณาเลือกไฟล์ .zip หรือ .lz4"},
"de": {"unsupportedProjectFileFormat": "Nicht unterstütztes Dateiformat", "unsupportedProjectFileFormatMessage": "Bitte wählen Sie eine .zip- oder .lz4-Datei"}
},
"20250413": {
"ja": {"upscaleButton": "画像を高解像度化します", "cropButton": "Crop", "importButton": "インポート", "exitModeButton": "モード解除"},
"en": {"upscaleButton": "Upscale image", "cropButton": "Crop", "importButton": "Import", "exitModeButton": "Exit Mode"},
"ko": {"upscaleButton": "이미지 확대", "cropButton": "자르기", "importButton": "가져오기", "exitModeButton": "모드 해제"},
"fr": {"upscaleButton": "Améliorer l'image", "cropButton": "Rogner", "importButton": "Importer", "exitModeButton": "Quitter le mode"},
"zh": {"upscaleButton": "提升图像分辨率", "cropButton": "裁剪", "importButton": "导入", "exitModeButton": "退出模式"},
"ru": {"upscaleButton": "Увеличить разрешение", "cropButton": "Обрезка", "importButton": "Импорт", "exitModeButton": "Выйти из режима"},
"es": {"upscaleButton": "Mejorar resolución", "cropButton": "Recorte", "importButton": "Importar", "exitModeButton": "Salir del modo"},
"pt": {"upscaleButton": "Aumentar resolução", "cropButton": "Cortar", "importButton": "Importar", "exitModeButton": "Sair do modo"},
"th": {"upscaleButton": "เพิ่มความละเอียดภาพ", "cropButton": "ครอป", "importButton": "นำเข้า", "exitModeButton": "ออกจากโหมด"},
"de": {"upscaleButton": "Bild verbessern", "cropButton": "Zuschneiden", "importButton": "Importieren", "exitModeButton": "Modus beenden"}
},

"20250322": {
ja: {missingNode:"ノード情報無し", missingDescription:"ComfyUI接続未経験かノード無し。WorkflowをダウンロードしてComfyUIに適用してComfyUI ManagerからInstall Missing Custom Nodesを実行してください"},
en: {missingNode:"No node info", missingDescription:"No ComfyUI connection experience or no nodes. Download Workflow, apply to ComfyUI and run Install Missing Custom Nodes from ComfyUI Manager"},
ko: {missingNode:"노드 정보 없음", missingDescription:"ComfyUI 연결 경험이 없거나 노드가 없습니다. 워크플로우를 다운로드하여 ComfyUI에 적용하고 ComfyUI Manager에서 누락된 사용자 정의 노드 설치를 실행하세요"},
fr: {missingNode:"Aucune info de nœud", missingDescription:"Pas d'expérience de connexion ComfyUI ou nœuds manquants. Téléchargez le workflow, appliquez-le à ComfyUI et exécutez Installer les nœuds personnalisés manquants depuis le gestionnaire ComfyUI"},
zh: {missingNode:"无节点信息", missingDescription:"未连接ComfyUI或节点缺失。下载工作流，应用到ComfyUI并从ComfyUI管理器运行安装缺失的自定义节点"},
ru: {missingNode:"Нет информации о узле", missingDescription:"Нет опыта подключения к ComfyUI или отсутствуют узлы. Загрузите рабочий процесс, примените его к ComfyUI и запустите установку отсутствующих пользовательских узлов из менеджера ComfyUI"},
es: {missingNode:"Sin información de nodo", missingDescription:"Sin experiencia de conexión a ComfyUI o nodos ausentes. Descargue el flujo de trabajo, aplíquelo a ComfyUI y ejecute Instalar nodos personalizados faltantes desde el Administrador de ComfyUI"},
pt: {missingNode:"Sem informação de nó", missingDescription:"Sem experiência de conexão ComfyUI ou nós ausentes. Baixe o fluxo de trabalho, aplique ao ComfyUI e execute Instalar nós personalizados ausentes do Gerenciador ComfyUI"},
th: {missingNode:"ไม่มีข้อมูลโหนด", missingDescription:"ไม่มีประสบการณ์การเชื่อมต่อ ComfyUI หรือไม่มีโหนด ดาวน์โหลดเวิร์กโฟลว์ ใช้กับ ComfyUI และเรียกใช้การติดตั้งโหนดที่ขาดหายไปจาก ComfyUI Manager"},
de: {missingNode:"Keine Knoteninfo", missingDescription:"Keine ComfyUI-Verbindungserfahrung oder keine Knoten. Workflow herunterladen, auf ComfyUI anwenden und Fehlende benutzerdefinierte Knoten installieren vom ComfyUI Manager ausführen"}
},
"20250321": {
 ja: {
 rought_error:"不明なエラー",
 rough_target:"ラフ対象が選択されていません",
 rough_target_message:"ラフは図形、アイコン、フリー吹き出しに適用できます。",
 "Rough":"ラフ(β)",
 "strokeColor":"線色",
 "fillStyle":"塗りスタイル",
 "fill_style":"塗りスタイル",
 "fillWeight":"塗りの太さ",
 "rough_style":"基本スタイル",
 "roughness":"ラフ度",
 "bowing":"曲がり具合",
 "strokeWidth":"線の太さ",
 "rough_hachure":"ハッチング設定",
 "hachureAngle":"ハッチング角度",
 "hachureGap":"ハッチング間隔",
 "rough_curve":"曲線",
 "curveStepCount":"曲線数",
 "curveFitting":"曲線フィット",
 "simplification":"単純化",
 "rough_on_off":"ラフ ON/OFF",
 "rough_on":"ラフ ON",
 "rough_off":"ラフ OFF",
 "Multi":"マルチストローク",
 "MultiFill":"マルチフィル",    
 side_label_rough:"ラフ", 
 auto_generate:"自動生成", 
 prompt:"プロンプト(β)", 
 prompt_gallery:"プロンプトギャラリー", 
 loading_image:"読み込み中", 
 image_load_error:"画像がありません"
 },
 en: {
 rought_error:"Unknown error",
 rough_target:"No rough target selected",
 rough_target_message:"Rough can be applied to shapes, icons, and free bubbles.",
 "Rough":"Rough(β)",
 "strokeColor":"Stroke color",
 "fillStyle":"Fill style",
 "fill_style":"Fill style",
 "fillWeight":"Fill weight",
 "rough_style":"Basic style",
 "roughness":"Roughness",
 "bowing":"Bowing",
 "strokeWidth":"Stroke width",
 "rough_hachure":"Hachure settings",
 "hachureAngle":"Hachure angle",
 "hachureGap":"Hachure gap",
 "rough_curve":"Curve",
 "curveStepCount":"Curve steps",
 "curveFitting":"Curve fitting",
 "simplification":"Simplification",
 "rough_on_off":"Rough ON/OFF",
 "rough_on":"Rough ON",
 "rough_off":"Rough OFF",
 "Multi":"Multi-stroke",
 "MultiFill":"Multi-fill",
 side_label_rough:"Rough", 
 auto_generate:"Auto Generate", 
 prompt:"Prompt(β)", 
 prompt_gallery:"Prompt Gallery", 
 loading_image:"Loading", 
 image_load_error:"No image"
 },
 ko: {
 rought_error:"알 수 없는 오류",
 rough_target:"선택된 러프 대상 없음",
 rough_target_message:"러프는 도형, 아이콘, 자유 말풍선에 적용할 수 있습니다.",
 "Rough":"러프(β)",
 "strokeColor":"선 색상",
 "fillStyle":"채우기 스타일",
 "fill_style":"채우기 스타일",
 "fillWeight":"채우기 두께",
 "rough_style":"기본 스타일",
 "roughness":"거친 정도",
 "bowing":"굽힘 정도",
 "strokeWidth":"선 두께",
 "rough_hachure":"해칭 설정",
 "hachureAngle":"해칭 각도",
 "hachureGap":"해칭 간격",
 "rough_curve":"곡선",
 "curveStepCount":"곡선 단계",
 "curveFitting":"곡선 맞춤",
 "simplification":"단순화",
 "rough_on_off":"러프 켜기/끄기",
 "rough_on":"러프 켜기",
 "rough_off":"러프 끄기",
 "Multi":"멀티 스트로크",
 "MultiFill":"멀티 채우기",
 side_label_rough:"러프", 
 auto_generate:"자동 생성", 
 prompt:"프롬프트(β)", 
 prompt_gallery:"프롬프트 갤러리", 
 loading_image:"로딩 중", 
 image_load_error:"이미지 없음"
 },
 fr: {
 rought_error:"Erreur inconnue",
 rough_target:"Aucune cible brute sélectionnée",
 rough_target_message:"L'effet brut peut être appliqué aux formes, icônes et bulles libres.",
 "Rough":"Brut(β)",
 "strokeColor":"Couleur de trait",
 "fillStyle":"Style de remplissage",
 "fill_style":"Style de remplissage",
 "fillWeight":"Épaisseur de remplissage",
 "rough_style":"Style de base",
 "roughness":"Rugosité",
 "bowing":"Courbure",
 "strokeWidth":"Épaisseur de trait",
 "rough_hachure":"Paramètres de hachure",
 "hachureAngle":"Angle de hachure",
 "hachureGap":"Espacement de hachure",
 "rough_curve":"Courbe",
 "curveStepCount":"Nombre de pas",
 "curveFitting":"Ajustement de courbe",
 "simplification":"Simplification",
 "rough_on_off":"Brut ON/OFF",
 "rough_on":"Brut ON",
 "rough_off":"Brut OFF",
 "Multi":"Multi-traits",
 "MultiFill":"Multi-remplissage",
 side_label_rough:"Brut", 
 auto_generate:"Génération auto", 
 prompt:"Invite(β)", 
 prompt_gallery:"Galerie d'invites", 
 loading_image:"Chargement", 
 image_load_error:"Pas d'image"
 },
 zh: {
 rought_error:"未知错误",
 rough_target:"未选择粗糙目标",
 rough_target_message:"粗糙效果可应用于形状、图标和自由气泡。",
 "Rough":"粗糙(β)",
 "strokeColor":"线条颜色",
 "fillStyle":"填充样式",
 "fill_style":"填充样式",
 "fillWeight":"填充厚度",
 "rough_style":"基本样式",
 "roughness":"粗糙度",
 "bowing":"弯曲度",
 "strokeWidth":"线条宽度",
 "rough_hachure":"阴影设置",
 "hachureAngle":"阴影角度",
 "hachureGap":"阴影间距",
 "rough_curve":"曲线",
 "curveStepCount":"曲线步数",
 "curveFitting":"曲线拟合",
 "simplification":"简化",
 "rough_on_off":"粗糙开/关",
 "rough_on":"粗糙开",
 "rough_off":"粗糙关",
 "Multi":"多重线条",
 "MultiFill":"多重填充",
 side_label_rough:"粗糙", 
 auto_generate:"自动生成", 
 prompt:"提示(β)", 
 prompt_gallery:"提示画廊", 
 loading_image:"加载中", 
 image_load_error:"没有图像"
 },
 ru: {
 rought_error:"Неизвестная ошибка",
 rough_target:"Не выбрана цель для эффекта",
 rough_target_message:"Эффект можно применить к фигурам, иконкам и свободным пузырям.",
 "Rough":"Эффект(β)",
 "strokeColor":"Цвет линии",
 "fillStyle":"Стиль заливки",
 "fill_style":"Стиль заливки",
 "fillWeight":"Вес заливки",
 "rough_style":"Базовый стиль",
 "roughness":"Шероховатость",
 "bowing":"Изгиб",
 "strokeWidth":"Толщина линии",
 "rough_hachure":"Настройки штриховки",
 "hachureAngle":"Угол штриховки",
 "hachureGap":"Интервал штриховки",
 "rough_curve":"Кривая",
 "curveStepCount":"Шаги кривой",
 "curveFitting":"Подгонка кривой",
 "simplification":"Упрощение",
 "rough_on_off":"Эффект ВКЛ/ВЫКЛ",
 "rough_on":"Эффект ВКЛ",
 "rough_off":"Эффект ВЫКЛ",
 "Multi":"Мульти-штрих",
 "MultiFill":"Мульти-заливка",
 side_label_rough:"Эффект", 
 auto_generate:"Автогенерация", 
 prompt:"Промпт(β)", 
 prompt_gallery:"Галерея промптов", 
 loading_image:"Загрузка", 
 image_load_error:"Нет изображения"
 },
 es: {
 rought_error:"Error desconocido",
 rough_target:"No hay objetivo rugoso seleccionado",
 rough_target_message:"El efecto rugoso se puede aplicar a formas, iconos y burbujas libres.",
 "Rough":"Rugoso(β)",
 "strokeColor":"Color de trazo",
 "fillStyle":"Estilo de relleno",
 "fill_style":"Estilo de relleno",
 "fillWeight":"Peso de relleno",
 "rough_style":"Estilo básico",
 "roughness":"Rugosidad",
 "bowing":"Curvatura",
 "strokeWidth":"Grosor de trazo",
 "rough_hachure":"Ajustes de rayado",
 "hachureAngle":"Ángulo de rayado",
 "hachureGap":"Espacio de rayado",
 "rough_curve":"Curva",
 "curveStepCount":"Pasos de curva",
 "curveFitting":"Ajuste de curva",
 "simplification":"Simplificación",
 "rough_on_off":"Rugoso ON/OFF",
 "rough_on":"Rugoso ON",
 "rough_off":"Rugoso OFF",
 "Multi":"Multi-trazo",
 "MultiFill":"Multi-relleno",
 side_label_rough:"Rugoso", 
 auto_generate:"Generación auto", 
 prompt:"Prompt(β)", 
 prompt_gallery:"Galería de prompts", 
 loading_image:"Cargando", 
 image_load_error:"No hay imagen"
 },
 pt: {
 rought_error:"Erro desconhecido",
 rough_target:"Nenhum alvo áspero selecionado",
 rough_target_message:"O efeito áspero pode ser aplicado a formas, ícones e balões livres.",
 "Rough":"Áspero(β)",
 "strokeColor":"Cor do traço",
 "fillStyle":"Estilo de preenchimento",
 "fill_style":"Estilo de preenchimento",
 "fillWeight":"Peso do preenchimento",
 "rough_style":"Estilo básico",
 "roughness":"Aspereza",
 "bowing":"Curvatura",
 "strokeWidth":"Espessura do traço",
 "rough_hachure":"Config. de hachura",
 "hachureAngle":"Ângulo de hachura",
 "hachureGap":"Espaço de hachura",
 "rough_curve":"Curva",
 "curveStepCount":"Passos da curva",
 "curveFitting":"Ajuste de curva",
 "simplification":"Simplificação",
 "rough_on_off":"Áspero ON/OFF",
 "rough_on":"Áspero ON",
 "rough_off":"Áspero OFF",
 "Multi":"Multi-traço",
 "MultiFill":"Multi-preenchimento",
 side_label_rough:"Áspero", 
 auto_generate:"Geração auto", 
 prompt:"Prompt(β)", 
 prompt_gallery:"Galeria de prompts", 
 loading_image:"Carregando", 
 image_load_error:"Sem imagem"
 },
 th: {
 rought_error:"ข้อผิดพลาดที่ไม่รู้จัก",
 rough_target:"ไม่ได้เลือกเป้าหมายแบบหยาบ",
 rough_target_message:"สามารถใช้เอฟเฟกต์หยาบกับรูปทรง ไอคอน และบอลลูนอิสระได้",
 "Rough":"หยาบ(β)",
 "strokeColor":"สีเส้น",
 "fillStyle":"สไตล์การเติม",
 "fill_style":"สไตล์การเติม",
 "fillWeight":"น้ำหนักการเติม",
 "rough_style":"สไตล์พื้นฐาน",
 "roughness":"ความหยาบ",
 "bowing":"ความโค้ง",
 "strokeWidth":"ความหนาเส้น",
 "rough_hachure":"ตั้งค่าลายเส้น",
 "hachureAngle":"มุมลายเส้น",
 "hachureGap":"ช่องว่างลายเส้น",
 "rough_curve":"เส้นโค้ง",
 "curveStepCount":"จำนวนขั้นโค้ง",
 "curveFitting":"การปรับโค้ง",
 "simplification":"การทำให้ง่าย",
 "rough_on_off":"หยาบ เปิด/ปิด",
 "rough_on":"หยาบ เปิด",
 "rough_off":"หยาบ ปิด",
 "Multi":"หลายเส้น",
 "MultiFill":"หลายการเติม",
 side_label_rough:"หยาบ", 
 auto_generate:"สร้างอัตโนมัติ", 
 prompt:"พรอมต์(β)", 
 prompt_gallery:"แกลเลอรีพรอมต์", 
 loading_image:"กำลังโหลด", 
 image_load_error:"ไม่มีภาพ"
 },
 de: {
 rought_error:"Unbekannter Fehler",
 rough_target:"Kein Rau-Ziel ausgewählt",
 rough_target_message:"Rau-Effekt kann auf Formen, Icons und freie Sprechblasen angewendet werden.",
 "Rough":"Rau(β)",
 "strokeColor":"Strichfarbe",
 "fillStyle":"Füllstil",
 "fill_style":"Füllstil",
 "fillWeight":"Füllgewicht",
 "rough_style":"Grundstil",
 "roughness":"Rauheit",
 "bowing":"Biegung",
 "strokeWidth":"Strichbreite",
 "rough_hachure":"Schraffur-Einstellungen",
 "hachureAngle":"Schraffur-Winkel",
 "hachureGap":"Schraffur-Abstand",
 "rough_curve":"Kurve",
 "curveStepCount":"Kurvenschritte",
 "curveFitting":"Kurvenanpassung",
 "simplification":"Vereinfachung",
 "rough_on_off":"Rau EIN/AUS",
 "rough_on":"Rau EIN",
 "rough_off":"Rau AUS",
 "Multi":"Mehrfach-Strich",
 "MultiFill":"Mehrfach-Füllung",
 side_label_rough:"Rau", 
 auto_generate:"Auto-Generierung", 
 prompt:"Prompt(β)", 
 prompt_gallery:"Prompt-Galerie", 
 loading_image:"Wird geladen", 
 image_load_error:"Kein Bild"
 }
},
"20250301_v2": {
ja: {view_Layer:"レイヤー",view_AI:"AI"},
en: {view_Layer:"Layer",view_AI:"AI"},
ko: {view_Layer:"레이어",view_AI:"AI"},
fr: {view_Layer:"Calque",view_AI:"IA"},
zh: {view_Layer:"图层",view_AI:"AI"},
ru: {view_Layer:"Слой",view_AI:"ИИ"},
es: {view_Layer:"Capa",view_AI:"IA"},
pt: {view_Layer:"Camada",view_AI:"IA"},
th: {view_Layer:"เลเยอร์",view_AI:"เอไอ"},
de: {view_Layer:"Ebene",view_AI:"KI"}
},
"20250301": {
ja: {terms_of_service:"利用規約"},
en: {terms_of_service:"Terms of Service"},
ko: {terms_of_service:"서비스 이용약관"},
fr: {terms_of_service:"Conditions d'utilisation"},
zh: {terms_of_service:"服务条款"},
ru: {terms_of_service:"Условия использования"},
es: {terms_of_service:"Términos de servicio"},
pt: {terms_of_service:"Termos de serviço"},
th: {terms_of_service:"ข้อกำหนดการให้บริการ"},
de: {terms_of_service:"Nutzungsbedingungen"}
},
"base": {
  ja: base_ja,en: base_en,ko: base_ko,fr: base_fr,zh: base_zh,ru: base_ru,es: base_es,pt: base_pt,th: base_th,de: base_de
}
};

function mergeResources(resources) {
const mergedResources = {};

if (resources.base) {
  Object.keys(resources.base).forEach(function(lang) {
    mergedResources[lang] = {
      translation: Object.assign({}, resources.base[lang])
    };
  });
}

Object.keys(resources)
  .filter(function(key) { return key !== 'base'; })
  .sort()
  .forEach(function(dateKey) {
    Object.keys(resources[dateKey]).forEach(function(lang) {
      if (!mergedResources[lang]) {
        mergedResources[lang] = { translation: {} };
      }
      
      Object.assign(
        mergedResources[lang].translation,
        resources[dateKey][lang]
      );
    });
  });

return mergedResources;
}

const mergedResources = mergeResources(resources);
let savedLanguage = localStorage.getItem("language") || "en";

i18next.init(
{
  lng: savedLanguage,
  resources: mergedResources,
},
function (err, t) {
  updateContent();
  setLanguage(savedLanguage);
}
);

function updateContent() {
document.querySelectorAll("[data-i18n]").forEach(function (element) {
  const key = element.getAttribute("data-i18n");
  const translation = i18next.t(key);
  if (translation) {
    if (element.tagName === "OPTION") {
      element.textContent = translation;
    } else {
      element.innerHTML = translation;
    }
  } else {
    console.warn(`Translation for key "${key}" not found.`);
  }
});
document.querySelectorAll("[data-i18n-label]").forEach(function (element) {
  const key = element.getAttribute("data-i18n-label");
  element.setAttribute("data-label", i18next.t(key));
});
}

function changeLanguage(lng, event) {
if (event) {
  event.preventDefault();
}
i18next.changeLanguage(lng, function (err, t) {
  if (!err) {
    createToast("Save Language", "successfully!");
    localStorage.setItem("language", lng);
    updateContent();
    setLanguage(lng);
    updateLayerPanel();
    savedLanguage = lng;
    if (objectMenu && objectMenu.style.display === "flex") {
      showObjectMenu(lastClickType);
    }
  } else {
    console.error("Failed to change language:", err);
  }
});
recreateFloatingWindow();
}

function getTranslation(key, defaultText) {
const translatedText = i18next.t(key);
return translatedText !== key ? translatedText : defaultText;
}

function getText(key) {
const translatedText = i18next.t(key);
return translatedText !== key ? translatedText : key;
}