let tippyInstances = []; 

function removeTooltips() {
  tippyInstances.forEach(instance => {
    instance.destroy();
  });
  tippyInstances = [];
}

const theme = "light";

function addTooltipByElement(element, translationKey) {
  if (!element) {
    uiLogger.warn(`Element with ID ${elementId} not found`);
    return;
  }
  const tooltipText = getText(translationKey);
  const instance = tippy(element, {
    content: tooltipText,
    arrow: true,
    theme: theme,
    delay: [800, 0], 
    duration: 0,
    placement: 'bottom',
  });
  tippyInstances.push(instance);
}

function addTooltip(elementId, translationKey) {
  const element = $(elementId);
  if (!element) {
    uiLogger.warn(`Element with ID ${elementId} not found`);
    return;
  }

  const tooltipText = getText(translationKey);
  
  const instance = tippy(element, {
    content: tooltipText,
    arrow: true,
    theme: theme,
    duration: 1000,
  });
  
  tippyInstances.push(instance);
}

function setLanguage(language) {
  i18next.changeLanguage(language, () => {
    uiLogger.debug("setLanguage start");
    removeTooltips();

    addTooltip('zoomIn', 'zoomIn');
    addTooltip('zoomOut', 'zoomOut');
    addTooltip('zoomFit', 'zoomFit');
    addTooltip('clearMode', 'clearMode');
    addTooltip('undo', 'undo');
    addTooltip('redo', 'redo');
  });
}

