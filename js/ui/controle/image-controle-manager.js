function imageControleTogglePanel(panelId) {
var panel=$(panelId);
if (panel) {
var content=panel.querySelector('.controls-mini');
if (content) {
console.log("imageControleTogglePanel hidden");
content.classList.toggle('hidden');
} else {
console.error('Element with class "control-content" not found in panel:',panelId);
}
} else {
console.error('Panel with ID not found:',panelId);
}
}
