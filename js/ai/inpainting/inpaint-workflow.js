// Inpaintワークフロー連携
var inpaintWorkflowLogger=new SimpleLogger('inpaintWorkflow',LogLevel.DEBUG);

var InpaintWorkflow=(function(){

async function generate(imageDataUrl,maskDataUrl,prompt,negativePrompt,denoise){
if(!socket) comfyuiConnect();

var selectedWorkflow=await comfyUIWorkflowRepository.getEnabledWorkflowByType("Inpaint");
if(!selectedWorkflow){
createToastError("Inpaint Error","No Inpaint workflow configured");
return null;
}

var classTypeLists=getClassTypeOnlyByJson(selectedWorkflow);
if(!checkWorkflowNodeVsComfyUI(classTypeLists)){
return null;
}

var imageFilename="inpaint_"+generateFilename();
await comfyuiUploadBase64Image(imageDataUrl,imageFilename);

var maskFilename="mask_"+generateFilename();
await comfyuiUploadBase64Image(maskDataUrl,maskFilename);

var builder=createWorkflowBuilder(selectedWorkflow);
builder.updateNodesByInputName({
seed:Math.floor(Math.random()*50000000),
noise_seed:Math.floor(Math.random()*537388471760656),
denoise:denoise
});
builder.updateNodesByInputName({
image:imageFilename
});
builder.updateValueByTargetValue("inpaint_mask.png",maskFilename);
builder.updateValueByTargetValue("%prompt%",prompt||"");
builder.updateValueByTargetValue("%negative%",negativePrompt||"");
builder.replaceDatePlaceholders();
var workflow=builder.build();

inpaintWorkflowLogger.debug("Inpaint workflow ready, queuing...");

try{
var result=await comfyui_put_queue_v2(workflow);
if(!result||result.error){
var msg=result?result.message:"Unknown error";
createToastError("Inpaint Error",msg);
return null;
}
inpaintWorkflowLogger.debug("Inpaint generation complete");
return result;
}catch(error){
inpaintWorkflowLogger.error("Inpaint generation error:",error);
var help=getText("comfyUI_workflowErrorHelp");
createToastError("Inpaint Error",[error.message,help],8000);
return null;
}
}

return{
generate:generate
};
})();
