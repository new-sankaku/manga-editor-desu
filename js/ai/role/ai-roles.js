// AIロール定義とロール判定
const AI_ROLES={
Text2Image: "Text2Image",
Image2Image: "Image2Image",
Image2Prompt_DEEPDOORU: "Image2Prompt_DEEPDOORU",
Image2Prompt_CLIP: "Image2Prompt_CLIP",
RemoveBG: "RemoveBG",
ADetailer: "ADetailer",
Upscaler: "Upscaler",
Inpaint: "Inpaint",
PutPrompt: "PutPrompt",
PutSeed: "PutSeed",
I2I_Angle: "I2I_Angle",
Temp: "Temp",
Text2Prompt: "Text2Prompt",
Image2Prompt_LLM: "Image2Prompt_LLM",
Text2Text: "Text2Text",
};

const roles={
A1111: [
AI_ROLES.Text2Image,
AI_ROLES.Image2Image,
AI_ROLES.Image2Prompt_DEEPDOORU,
AI_ROLES.Image2Prompt_CLIP,
AI_ROLES.RemoveBG,
AI_ROLES.ADetailer,
AI_ROLES.PutPrompt,
AI_ROLES.PutSeed
],
GROK: [
AI_ROLES.Text2Prompt,
AI_ROLES.Image2Prompt_LLM,
AI_ROLES.Text2Text
],
OLLAMA: [
AI_ROLES.Text2Prompt,
AI_ROLES.Image2Prompt_LLM,
AI_ROLES.Text2Text
],
COMFYUI: [
AI_ROLES.Text2Image,
AI_ROLES.RemoveBG,
AI_ROLES.Upscaler,
AI_ROLES.Image2Image,
AI_ROLES.Inpaint,
AI_ROLES.I2I_Angle
],
RUNPOD_COMFYUI: [
AI_ROLES.Text2Image,
AI_ROLES.RemoveBG,
AI_ROLES.Upscaler,
AI_ROLES.Image2Image,
AI_ROLES.Inpaint,
AI_ROLES.I2I_Angle
],
FAL_AI: [
AI_ROLES.Text2Image,
AI_ROLES.Image2Image,
AI_ROLES.Upscaler,
AI_ROLES.RemoveBG
]
};

// 使用サービス表の行定義。マトリクスUIと接続状態チェックの両方がこれを見る
const ROLE_MATRIX_ROWS=[
{role:AI_ROLES.Text2Image,labelKey:'roleText2Image'},
{role:AI_ROLES.Image2Image,labelKey:'roleImage2Image'},
{role:AI_ROLES.Inpaint,labelKey:'roleInpaint'},
{role:AI_ROLES.Upscaler,labelKey:'roleUpscaler'},
{role:AI_ROLES.RemoveBG,labelKey:'roleRemoveBG'},
{role:AI_ROLES.I2I_Angle,labelKey:'roleAngle'},
{role:AI_ROLES.Image2Prompt_CLIP,labelKey:'roleInterrogateCLIP'},
{role:AI_ROLES.Image2Prompt_DEEPDOORU,labelKey:'roleInterrogateDEEPDOORU'},
{role:AI_ROLES.Text2Prompt,labelKey:'roleText2Prompt'},
{role:AI_ROLES.Image2Prompt_LLM,labelKey:'roleImage2PromptLLM'},
{role:AI_ROLES.Text2Text,labelKey:'roleText2Text'}
];

const ROLE_NONE='none';

function hasNotRole(role) {
return!(hasRole(role));
}

function hasRole(role) {
if(providerRegistry.getProviderForRole(role)!==null){
return true;
}
return false;
}
