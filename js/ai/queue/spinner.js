function removeSpinner(spinnerId) {
var removeSpinner=$(spinnerId);
if (removeSpinner) {
removeSpinner.remove();
}
}
function createSpinner(index) {
var spinner=document.createElement('span');
spinner.id='spinner-'+index;
spinner.className='spinner-border text-danger ms-1 spinner-border-sm';

var areaHeader=document.querySelector("#layer-panel .area-header");
areaHeader.appendChild(spinner);
index++;

return spinner;
}
function createSpinnerSuccess(index) {
var spinner=document.createElement('span');
spinner.id='spinner-'+index;
spinner.className='spinner-border text-success ms-1 spinner-border-sm';

var areaHeader=document.querySelector("#layer-panel .area-header");
areaHeader.appendChild(spinner);
index++;

return spinner;
}