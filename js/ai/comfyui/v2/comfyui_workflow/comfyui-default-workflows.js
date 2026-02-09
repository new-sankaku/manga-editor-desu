const comfyuiDefaultWorkflows=[
{
name: "inspyrenet.json",
type: "REMBG",
workflow: ComfyUI_Rembg_ByInspyrenet,
enabled: true
},

{
name: "SDXL.json",
type: "T2I",
workflow: ComfyUI_T2I_BySDXL,
enabled: true
},
{
name: "SDXL_Lora.json",
type: "T2I",
workflow: ComfyUI_T2I_BySDXL_Lora,
enabled: false
},
{
name: "SDXL_faceDetailer.json",
type: "T2I",
workflow: ComfyUI_T2I_BySDXL_faceDetailer,
enabled: false
},
{
name: "SDXL_faceDetailer_Lora.json",
type: "T2I",
workflow: ComfyUI_T2I_BySDXL_faceDetailer_Lora,
enabled: false
},
{
name: "SDXL_Refiner.json",
type: "T2I",
workflow: ComfyUI_T2I_BySDXL_Refiner,
enabled: false
},
{
name: "SD15.json",
type: "T2I",
workflow: ComfyUI_T2I_BySD15,
enabled: false
},
{
name: "SD15_VAE.json",
type: "T2I",
workflow: ComfyUI_T2I_BySD15_VAE,
enabled: false
},
{
name: "SD15_Lora.json",
type: "T2I",
workflow: ComfyUI_T2I_BySD15_Lora,
enabled: false
},

{
name: "FluxSimple.json",
type: "T2I",
workflow: ComfyUI_T2I_ByFluxSimple,
enabled: false
},
{
name: "FluxNF4.json",
type: "T2I",
workflow: ComfyUI_T2I_ByFluxNF4,
enabled: false
},
{
name: "FluxDiffusion.json",
type: "T2I",
workflow: ComfyUI_T2I_ByFluxDiffusion,
enabled: false
},

{
name: "Z_Image_turbo.json",
type: "T2I",
workflow: ComfyUI_T2I_Z_Image_turbo,
enabled: false
},
{
name: "Qwen_Image_gguf.json",
type: "T2I",
workflow: ComfyUI_T2I_Qwen_Image_gguf,
enabled: false
},



{
name: "SD15_SDXL.json",
type: "I2I",
workflow: ComfyUI_I2I_BySD15SDXL,
enabled: true
},

{
name: "Upscaler.json",
type: "Upscaler",
workflow: ComfyUI_Upscaler,
enabled: true
},

{
name: "Inpaint_SDXL.json",
type: "Inpaint",
workflow: ComfyUI_Inpaint_BySDXL,
enabled: true
},

];
