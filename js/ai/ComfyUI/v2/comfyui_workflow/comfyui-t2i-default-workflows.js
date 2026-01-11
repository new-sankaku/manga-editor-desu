const ComfyUI_T2I_Z_Image_turbo={
"3": {
"inputs": {
"seed": 4963536264065,
"steps": 9,
"cfg": 1,
"sampler_name": "euler",
"scheduler": "simple",
"denoise": 1,
"model": [
"16",
0
],
"positive": [
"6",
0
],
"negative": [
"7",
0
],
"latent_image": [
"13",
0
]
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"6": {
"inputs": {
"text": "%prompt%",
"clip": [
"18",
0
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Positive Prompt)"
}
},
"7": {
"inputs": {
"text": "%negative%",
"clip": [
"18",
0
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Negative Prompt)"
}
},
"8": {
"inputs": {
"samples": [
"3",
0
],
"vae": [
"17",
0
]
},
"class_type": "VAEDecode",
"_meta": {
"title": "VAE Decode"
}
},
"9": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"8",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"13": {
"inputs": {
"width": 848,
"height": 1264,
"batch_size": 1
},
"class_type": "EmptySD3LatentImage",
"_meta": {
"title": "EmptySD3LatentImage"
}
},
"16": {
"inputs": {
"unet_name": "divingZImageTurboReal_v20Fp16.safetensors",
"weight_dtype": "default"
},
"class_type": "UNETLoader",
"_meta": {
"title": "Load Diffusion Model"
}
},
"17": {
"inputs": {
"vae_name": "ae.safetensors"
},
"class_type": "VAELoader",
"_meta": {
"title": "Load VAE"
}
},
"18": {
"inputs": {
"clip_name": "qwen_3_4b.safetensors",
"type": "lumina2",
"device": "default"
},
"class_type": "CLIPLoader",
"_meta": {
"title": "Load CLIP"
}
}
};



const ComfyUI_T2I_Qwen_Image_gguf={
"3": {
"inputs": {
"seed": 135839686362908,
"steps": 20,
"cfg": 2.5,
"sampler_name": "euler",
"scheduler": "simple",
"denoise": 1,
"model": [
"66",
0
],
"positive": [
"6",
0
],
"negative": [
"7",
0
],
"latent_image": [
"58",
0
]
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"6": {
"inputs": {
"text": "%prompt%",
"clip": [
"38",
0
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Positive Prompt)"
}
},
"7": {
"inputs": {
"text": "%negative%",
"clip": [
"38",
0
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Negative Prompt)"
}
},
"8": {
"inputs": {
"samples": [
"3",
0
],
"vae": [
"39",
0
]
},
"class_type": "VAEDecode",
"_meta": {
"title": "VAE Decode"
}
},
"38": {
"inputs": {
"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
"type": "qwen_image",
"device": "default"
},
"class_type": "CLIPLoader",
"_meta": {
"title": "Load CLIP"
}
},
"39": {
"inputs": {
"vae_name": "qwen_image_vae.safetensors"
},
"class_type": "VAELoader",
"_meta": {
"title": "Load VAE"
}
},
"58": {
"inputs": {
"width": 1328,
"height": 1328,
"batch_size": 1
},
"class_type": "EmptySD3LatentImage",
"_meta": {
"title": "EmptySD3LatentImage"
}
},
"60": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"8",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"66": {
"inputs": {
"shift": 3.1000000000000005,
"model": [
"76",
0
]
},
"class_type": "ModelSamplingAuraFlow",
"_meta": {
"title": "ModelSamplingAuraFlow"
}
},
"76": {
"inputs": {
"unet_name": "qwen-image-Q4_K_S.gguf"
},
"class_type": "UnetLoaderGGUF",
"_meta": {
"title": "Unet Loader (GGUF)"
}
}
};





const ComfyUI_T2I_BySDXL_faceDetailer_Lora={
"3": {
"inputs": {
"seed": 99978609226879,
"steps": 20,
"cfg": 5.5,
"sampler_name": "euler",
"scheduler": "karras",
"denoise": 1,
"model": [
"37",
0
],
"positive": [
"19",
0
],
"negative": [
"7",
0
],
"latent_image": [
"5",
0
]
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"4": {
"inputs": {
"ckpt_name": "illustrious\\waiIllustriousSDXL_v160.safetensors"
},
"class_type": "CheckpointLoaderSimple",
"_meta": {
"title": "Load Checkpoint"
}
},
"5": {
"inputs": {
"width": 1024,
"height": 1280,
"batch_size": 1
},
"class_type": "EmptyLatentImage",
"_meta": {
"title": "Empty Latent Image"
}
},
"7": {
"inputs": {
"text": "%negative%",
"clip": [
"37",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Prompt)"
}
},
"8": {
"inputs": {
"samples": [
"3",
0
],
"vae": [
"10",
0
]
},
"class_type": "VAEDecode",
"_meta": {
"title": "VAE Decode"
}
},
"9": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"32",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"10": {
"inputs": {
"vae_name": "aaaAnimeSDXLVAE_v2.safetensors"
},
"class_type": "VAELoader",
"_meta": {
"title": "Load VAE"
}
},
"19": {
"inputs": {
"text": [
"26",
0
],
"parser": "A1111",
"mean_normalization": false,
"multi_conditioning": true,
"use_old_emphasis_implementation": false,
"with_SDXL": false,
"ascore": 6,
"width": 1024,
"height": 1024,
"crop_w": 0,
"crop_h": 0,
"target_width": 1024,
"target_height": 1024,
"text_g": "",
"text_l": "",
"smZ_steps": 1,
"clip": [
"37",
1
]
},
"class_type": "smZ CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode++"
}
},
"26": {
"inputs": {
"wildcard_text": "%prompt%",
"populated_text": "%prompt%",
"mode": "populate",
"seed": 723760882467233,
"Select to add Wildcard": "Select the Wildcard to add to the text"
},
"class_type": "ImpactWildcardProcessor",
"_meta": {
"title": "ImpactWildcardProcessor"
}
},
"32": {
"inputs": {
"guide_size": 1024,
"guide_size_for": true,
"max_size": 1024,
"seed": 543226019240738,
"steps": 20,
"cfg": 5,
"sampler_name": "euler",
"scheduler": "normal",
"denoise": 0.5,
"feather": 5,
"noise_mask": true,
"force_inpaint": true,
"bbox_threshold": 0.5,
"bbox_dilation": 10,
"bbox_crop_factor": 3,
"sam_detection_hint": "center-1",
"sam_dilation": 0,
"sam_threshold": 0.93,
"sam_bbox_expansion": 0,
"sam_mask_hint_threshold": 0.7,
"sam_mask_hint_use_negative": "False",
"drop_size": 10,
"wildcard": "",
"cycle": 1,
"inpaint_model": false,
"noise_mask_feather": 20,
"tiled_encode": false,
"tiled_decode": false,
"image": [
"8",
0
],
"model": [
"37",
0
],
"clip": [
"4",
1
],
"vae": [
"10",
0
],
"positive": [
"19",
0
],
"negative": [
"7",
0
],
"bbox_detector": [
"35",
0
]
},
"class_type": "FaceDetailer",
"_meta": {
"title": "FaceDetailer"
}
},
"34": {
"inputs": {
"seed": 856085515005401,
"steps": 20,
"cfg": 8,
"sampler_name": "euler",
"scheduler": "normal",
"denoise": 1
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"35": {
"inputs": {
"model_name": "bbox/face_yolov8m.pt"
},
"class_type": "UltralyticsDetectorProvider",
"_meta": {
"title": "UltralyticsDetectorProvider"
}
},
"36": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"8",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"37": {
"inputs": {
"lora_name": "Illustrious\\kuro gyaru_XL_illustrious_V1.0.safetensors",
"strength_model": 1,
"strength_clip": 1,
"model": [
"4",
0
],
"clip": [
"4",
1
]
},
"class_type": "LoraLoader",
"_meta": {
"title": "Load LoRA"
}
}
};




const ComfyUI_T2I_BySDXL_faceDetailer={
"3": {
"inputs": {
"seed": 47186256557939,
"steps": 20,
"cfg": 5.5,
"sampler_name": "euler",
"scheduler": "karras",
"denoise": 1,
"model": [
"4",
0
],
"positive": [
"19",
0
],
"negative": [
"7",
0
],
"latent_image": [
"5",
0
]
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"4": {
"inputs": {
"ckpt_name": "illustrious\\waiIllustriousSDXL_v160.safetensors"
},
"class_type": "CheckpointLoaderSimple",
"_meta": {
"title": "Load Checkpoint"
}
},
"5": {
"inputs": {
"width": 1024,
"height": 1280,
"batch_size": 1
},
"class_type": "EmptyLatentImage",
"_meta": {
"title": "Empty Latent Image"
}
},
"7": {
"inputs": {
"text": "%negative%",
"clip": [
"4",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Prompt)"
}
},
"8": {
"inputs": {
"samples": [
"3",
0
],
"vae": [
"10",
0
]
},
"class_type": "VAEDecode",
"_meta": {
"title": "VAE Decode"
}
},
"9": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"32",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"10": {
"inputs": {
"vae_name": "aaaAnimeSDXLVAE_v2.safetensors"
},
"class_type": "VAELoader",
"_meta": {
"title": "Load VAE"
}
},
"19": {
"inputs": {
"text": [
"26",
0
],
"parser": "A1111",
"mean_normalization": false,
"multi_conditioning": true,
"use_old_emphasis_implementation": false,
"with_SDXL": false,
"ascore": 6,
"width": 1024,
"height": 1024,
"crop_w": 0,
"crop_h": 0,
"target_width": 1024,
"target_height": 1024,
"text_g": "",
"text_l": "",
"smZ_steps": 1,
"clip": [
"4",
1
]
},
"class_type": "smZ CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode++"
}
},
"26": {
"inputs": {
"wildcard_text": "%prompt%",
"populated_text": "%prompt%",
"mode": "populate",
"seed": 8887528043779,
"Select to add Wildcard": "Select the Wildcard to add to the text"
},
"class_type": "ImpactWildcardProcessor",
"_meta": {
"title": "ImpactWildcardProcessor"
}
},
"32": {
"inputs": {
"guide_size": 1024,
"guide_size_for": true,
"max_size": 1024,
"seed": 169038801105639,
"steps": 20,
"cfg": 5,
"sampler_name": "euler",
"scheduler": "normal",
"denoise": 0.5,
"feather": 5,
"noise_mask": true,
"force_inpaint": true,
"bbox_threshold": 0.5,
"bbox_dilation": 10,
"bbox_crop_factor": 3,
"sam_detection_hint": "center-1",
"sam_dilation": 0,
"sam_threshold": 0.93,
"sam_bbox_expansion": 0,
"sam_mask_hint_threshold": 0.7,
"sam_mask_hint_use_negative": "False",
"drop_size": 10,
"wildcard": "",
"cycle": 1,
"inpaint_model": false,
"noise_mask_feather": 20,
"tiled_encode": false,
"tiled_decode": false,
"image": [
"8",
0
],
"model": [
"4",
0
],
"clip": [
"4",
1
],
"vae": [
"10",
0
],
"positive": [
"19",
0
],
"negative": [
"7",
0
],
"bbox_detector": [
"35",
0
]
},
"class_type": "FaceDetailer",
"_meta": {
"title": "FaceDetailer"
}
},
"34": {
"inputs": {
"seed": 240955597841665,
"steps": 20,
"cfg": 8,
"sampler_name": "euler",
"scheduler": "normal",
"denoise": 1
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"35": {
"inputs": {
"model_name": "bbox/face_yolov8m.pt"
},
"class_type": "UltralyticsDetectorProvider",
"_meta": {
"title": "UltralyticsDetectorProvider"
}
},
"36": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"8",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
}
};


const ComfyUI_T2I_BySDXL={
3: {
inputs: {
seed: 0,
steps: 25,
cfg: 6.5,
sampler_name: "dpmpp_2m_sde",
scheduler: "exponential",
denoise: 1,
model: ["4",0],
positive: ["30",0],
negative: ["33",0],
latent_image: ["5",0],
},
class_type: "KSampler",
_meta: {
title: "KSampler",
},
},
4: {
inputs: {
ckpt_name: "sd_xl_refiner_1.0_0.9vae.safetensors",
},
class_type: "CheckpointLoaderSimple",
_meta: {
title: "Load Checkpoint",
},
},
5: {
inputs: {
width: 1024,
height: 1024,
batch_size: 1,
},
class_type: "EmptyLatentImage",
_meta: {
title: "Empty Latent Image",
},
},
8: {
inputs: {
samples: ["3",0],
vae: ["4",2],
},
class_type: "VAEDecode",
_meta: {
title: "VAE Decode",
},
},
28: {
inputs: {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
images: ["8",0],
},
class_type: "SaveImage",
_meta: {
title: "Save Image",
},
},
30: {
inputs: {
width: 4096,
height: 4096,
crop_w: 0,
crop_h: 0,
target_width: 4096,
target_height: 4096,
text_g: "%prompt%",
text_l: "%prompt%",
clip: ["4",1],
},
class_type: "CLIPTextEncodeSDXL",
_meta: {
title: "CLIPTextEncodeSDXL Positive",
},
},
33: {
inputs: {
width: 4096,
height: 4096,
crop_w: 0,
crop_h: 0,
target_width: 4096,
target_height: 4096,
text_g: "%negative%",
text_l: "%negative%",
clip: ["4",1],
},
class_type: "CLIPTextEncodeSDXL",
_meta: {
title: "CLIPTextEncodeSDXL Negative",
},
},
};
const ComfyUI_T2I_BySDXL_Lora={
3: {
inputs: {
seed: 0,
steps: 20,
cfg: 6.5,
sampler_name: "euler",
scheduler: "simple",
denoise: 1,
model: ["10",0],
positive: ["27",0],
negative: ["26",0],
latent_image: ["5",0],
},
class_type: "KSampler",
_meta: {
title: "KSampler",
},
},
4: {
inputs: {
ckpt_name: "sdXL_v10VAEFix.safetensors",
},
class_type: "CheckpointLoaderSimple",
_meta: {
title: "SDXL Base Model",
},
},
5: {
inputs: {
width: 1024,
height: 1024,
batch_size: 1,
},
class_type: "EmptyLatentImage",
_meta: {
title: "Empty Latent Image",
},
},
8: {
inputs: {
samples: ["3",0],
vae: ["4",2],
},
class_type: "VAEDecode",
_meta: {
title: "VAE Decode",
},
},
10: {
inputs: {
lora_name: "detailed(sdxl).safetensors",
strength_model: 0.5,
strength_clip: 1,
model: ["4",0],
clip: ["4",1],
},
class_type: "LoraLoader",
_meta: {
title: "SDXL LoRA",
},
},
23: {
inputs: {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
images: ["8",0],
},
class_type: "SaveImage",
_meta: {
title: "SDXL Refiner+LoRA Image",
},
},
26: {
inputs: {
text: "%negative%",
clip: ["10",1],
},
class_type: "CLIPTextEncode",
_meta: {
title: "CLIP Text Encode (Negative)",
},
},
27: {
inputs: {
text: "%prompt%",
clip: ["10",1],
},
class_type: "CLIPTextEncode",
_meta: {
title: "CLIP Text Encode (Positive Prompt)",
},
},
};
const ComfyUI_T2I_BySDXL_Refiner={
4: {
inputs: {
ckpt_name: "sd_xl_base_1.0_0.9vae.safetensors",
},
class_type: "CheckpointLoaderSimple",
_meta: {
title: "Load Checkpoint",
},
},
5: {
inputs: {
width: 1024,
height: 1024,
batch_size: 1,
},
class_type: "EmptyLatentImage",
_meta: {
title: "Empty Latent Image",
},
},
8: {
inputs: {
samples: ["38",0],
vae: ["37",0],
},
class_type: "VAEDecode",
_meta: {
title: "VAE Decode",
},
},
28: {
inputs: {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
images: ["8",0],
},
class_type: "SaveImage",
_meta: {
title: "Save Image",
},
},
30: {
inputs: {
width: 4096,
height: 4096,
crop_w: 0,
crop_h: 0,
target_width: 4096,
target_height: 4096,
text_g: "%prompt%",
text_l: "%prompt%",
clip: ["4",1],
},
class_type: "CLIPTextEncodeSDXL",
_meta: {
title: "CLIPTextEncodeSDXL Positive",
},
},
33: {
inputs: {
width: 4096,
height: 4096,
crop_w: 0,
crop_h: 0,
target_width: 4096,
target_height: 4096,
text_g: "%negative%",
text_l: "%negative%",
clip: ["4",1],
},
class_type: "CLIPTextEncodeSDXL",
_meta: {
title: "CLIPTextEncodeSDXL Negative",
},
},
36: {
inputs: {
add_noise: "enable",
noise_seed: 0,
steps: 30,
cfg: 6.5,
sampler_name: "dpmpp_2m_sde",
scheduler: "exponential",
start_at_step: 0,
end_at_step: 25,
return_with_leftover_noise: "enable",
model: ["4",0],
positive: ["30",0],
negative: ["33",0],
latent_image: ["5",0],
},
class_type: "KSamplerAdvanced",
_meta: {
title: "KSampler (Advanced)",
},
},
37: {
inputs: {
vae_name: "sdxl_vae.safetensors",
},
class_type: "VAELoader",
_meta: {
title: "Load VAE",
},
},
38: {
inputs: {
add_noise: "disable",
noise_seed: 0,
steps: 30,
cfg: 6.5,
sampler_name: "dpmpp_2m_sde",
scheduler: "karras",
start_at_step: 25,
end_at_step: 10000,
return_with_leftover_noise: "disable",
model: ["39",0],
positive: ["40",0],
negative: ["41",0],
latent_image: ["36",0],
},
class_type: "KSamplerAdvanced",
_meta: {
title: "KSampler (Advanced)",
},
},
39: {
inputs: {
ckpt_name: "sd_xl_refiner_1.0.safetensors",
},
class_type: "CheckpointLoaderSimple",
_meta: {
title: "Load Checkpoint",
},
},
40: {
inputs: {
ascore: 6,
width: 1024,
height: 1024,
text: "%prompt%",
clip: ["39",1],
},
class_type: "CLIPTextEncodeSDXLRefiner",
_meta: {
title: "CLIPTextEncodeSDXLRefiner Positive",
},
},
41: {
inputs: {
ascore: 3,
width: 1024,
height: 1024,
text: "%negative%",
clip: ["39",1],
},
class_type: "CLIPTextEncodeSDXLRefiner",
_meta: {
title: "CLIPTextEncodeSDXLRefiner Negative",
},
},
};
const ComfyUI_T2I_BySD15={
3: {
inputs: {
seed: 0,
steps: 25,
cfg: 6.5,
sampler_name: "dpmpp_2m",
scheduler: "karras",
denoise: 1,
model: ["4",0],
positive: ["6",0],
negative: ["7",0],
latent_image: ["5",0],
},
class_type: "KSampler",
_meta: {
title: "KSampler",
},
},
4: {
inputs: {
ckpt_name: "dreamshaper_8.safetensors",
},
class_type: "CheckpointLoaderSimple",
_meta: {
title: "Load Checkpoint Negative",
},
},
5: {
inputs: {
width: 512,
height: 512,
batch_size: 1,
},
class_type: "EmptyLatentImage",
_meta: {
title: "Empty Latent Image",
},
},
6: {
inputs: {
text: "%prompt%",
clip: ["4",1],
},
class_type: "CLIPTextEncode",
_meta: {
title: "CLIP Text Encode (Positive)",
},
},
7: {
inputs: {
text: "%negative%",
clip: ["4",1],
},
class_type: "CLIPTextEncode",
_meta: {
title: "CLIP Text Encode (Negative)",
},
},
8: {
inputs: {
samples: ["3",0],
vae: ["4",2],
},
class_type: "VAEDecode",
_meta: {
title: "VAE Decode",
},
},
9: {
inputs: {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
images: ["8",0],
},
class_type: "SaveImage",
_meta: {
title: "Save Image",
},
},
};
const ComfyUI_T2I_BySD15_VAE={
3: {
inputs: {
seed: 0,
steps: 25,
cfg: 6.5,
sampler_name: "dpmpp_2m",
scheduler: "karras",
denoise: 1,
model: ["4",0],
positive: ["6",0],
negative: ["7",0],
latent_image: ["5",0],
},
class_type: "KSampler",
_meta: {
title: "KSampler",
},
},
4: {
inputs: {
ckpt_name: "dreamshaper_8.safetensors",
},
class_type: "CheckpointLoaderSimple",
_meta: {
title: "Load Checkpoint",
},
},
5: {
inputs: {
width: 512,
height: 512,
batch_size: 1,
},
class_type: "EmptyLatentImage",
_meta: {
title: "Empty Latent Image",
},
},
6: {
inputs: {
text: "%prompt%",
clip: ["4",1],
},
class_type: "CLIPTextEncode",
_meta: {
title: "CLIP Text Encode (Positive)",
},
},
7: {
inputs: {
text: "%negative%",
clip: ["4",1],
},
class_type: "CLIPTextEncode",
_meta: {
title: "CLIP Text Encode (Negative)",
},
},
8: {
inputs: {
samples: ["3",0],
vae: ["15",0],
},
class_type: "VAEDecode",
_meta: {
title: "VAE Decode",
},
},
9: {
inputs: {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
images: ["8",0],
},
class_type: "SaveImage",
_meta: {
title: "Save Image",
},
},
15: {
inputs: {
vae_name: "vae-ft-mse-840000-ema-pruned.safetensors",
},
class_type: "VAELoader",
_meta: {
title: "Load VAE",
},
},
};
const ComfyUI_T2I_BySD15_Lora={
"3": {
"inputs": {
"seed": 0,
"steps": 25,
"cfg": 6.5,
"sampler_name": "dpmpp_2m",
"scheduler": "karras",
"denoise": 1,
"model": [
"17",
0
],
"positive": [
"6",
0
],
"negative": [
"7",
0
],
"latent_image": [
"5",
0
]
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"4": {
"inputs": {
"ckpt_name": "SD1.0\\anime\\coffeensfw_v10.safetensors"
},
"class_type": "CheckpointLoaderSimple",
"_meta": {
"title": "Load Checkpoint"
}
},
"5": {
"inputs": {
"width": 512,
"height": 512,
"batch_size": 1
},
"class_type": "EmptyLatentImage",
"_meta": {
"title": "Empty Latent Image"
}
},
"6": {
"inputs": {
"text": "%prompt%",
"clip": [
"17",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Positive)"
}
},
"7": {
"inputs": {
"text": "%negative%",
"clip": [
"17",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Negative)"
}
},
"8": {
"inputs": {
"samples": [
"3",
0
],
"vae": [
"15",
0
]
},
"class_type": "VAEDecode",
"_meta": {
"title": "VAE Decode"
}
},
"9": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"8",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"15": {
"inputs": {
"vae_name": "vae-ft-mse-840000-ema-pruned.safetensors"
},
"class_type": "VAELoader",
"_meta": {
"title": "Load VAE"
}
},
"17": {
"inputs": {
"lora_name": "SD_1.0\\ChinaDressShunV1.safetensors",
"strength_model": 1,
"strength_clip": 1,
"model": [
"4",
0
],
"clip": [
"4",
1
]
},
"class_type": "LoraLoader",
"_meta": {
"title": "Load LoRA"
}
}
};
const ComfyUI_I2I_BySD15SDXL={
"3": {
"inputs": {
"seed": 0,
"steps": 20,
"cfg": 8,
"sampler_name": "dpmpp_2m",
"scheduler": "normal",
"denoise": 0.8700000000000001,
"model": [
"14",
0
],
"positive": [
"6",
0
],
"negative": [
"7",
0
],
"latent_image": [
"12",
0
]
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"6": {
"inputs": {
"text": "%prompt%",
"clip": [
"14",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Positive)"
}
},
"7": {
"inputs": {
"text": "%negative%",
"clip": [
"14",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIP Text Encode (Negative)"
}
},
"8": {
"inputs": {
"samples": [
"3",
0
],
"vae": [
"14",
2
]
},
"class_type": "VAEDecode",
"_meta": {
"title": "VAE Decode"
}
},
"9": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"8",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"10": {
"inputs": {
"image": "temp_20241023235005_173_3.png",
"upload": "image"
},
"class_type": "LoadImage",
"_meta": {
"title": "Load Image"
}
},
"12": {
"inputs": {
"pixels": [
"10",
0
],
"vae": [
"14",
2
]
},
"class_type": "VAEEncode",
"_meta": {
"title": "VAE Encode"
}
},
"14": {
"inputs": {
"ckpt_name": "illustrious\\waiNSFWIllustrious_v50.safetensors"
},
"class_type": "CheckpointLoaderSimple",
"_meta": {
"title": "Load Checkpoint"
}
}
};



const ComfyUI_T2I_ByFluxDiffusion={
"6": {
"inputs": {
"text":"%prompt%",
"clip": [
"11",
0
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIPTextEncode_Prompt"
}
},
"8": {
"inputs": {
"samples": [
"13",
0
],
"vae": [
"10",
0
]
},
"class_type": "VAEDecode",
"_meta": {
"title": "VAE Decode"
}
},
"9": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"8",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"10": {
"inputs": {
"vae_name": "ae.safetensors"
},
"class_type": "VAELoader",
"_meta": {
"title": "Load VAE"
}
},
"11": {
"inputs": {
"clip_name1": "t5xxl_fp16.safetensors",
"clip_name2": "clip_l.safetensors",
"type": "flux"
},
"class_type": "DualCLIPLoader",
"_meta": {
"title": "DualCLIPLoader"
}
},
"12": {
"inputs": {
"unet_name": "%model%",
"weight_dtype": "default"
},
"class_type": "UNETLoader",
"_meta": {
"title": "Load Diffusion Model"
}
},
"13": {
"inputs": {
"noise": [
"25",
0
],
"guider": [
"22",
0
],
"sampler": [
"16",
0
],
"sigmas": [
"17",
0
],
"latent_image": [
"27",
0
]
},
"class_type": "SamplerCustomAdvanced",
"_meta": {
"title": "SamplerCustomAdvanced"
}
},
"16": {
"inputs": {
"sampler_name": "%sampler%"
},
"class_type": "KSamplerSelect",
"_meta": {
"title": "KSamplerSelect"
}
},
"17": {
"inputs": {
"scheduler": "simple",
"steps":"25",
"denoise": 1,
"model": [
"30",
0
]
},
"class_type": "BasicScheduler",
"_meta": {
"title": "BasicScheduler"
}
},
"22": {
"inputs": {
"model": [
"30",
0
],
"conditioning": [
"26",
0
]
},
"class_type": "BasicGuider",
"_meta": {
"title": "BasicGuider"
}
},
"25": {
"inputs": {
"noise_seed": "100"
},
"class_type": "RandomNoise",
"_meta": {
"title": "RandomNoise"
}
},
"26": {
"inputs": {
"guidance": 3.5,
"conditioning": [
"6",
0
]
},
"class_type": "FluxGuidance",
"_meta": {
"title": "FluxGuidance"
}
},
"27": {
"inputs": {
"width":"1024",
"height":"1024",
"batch_size": 1
},
"class_type": "EmptySD3LatentImage",
"_meta": {
"title": "EmptySD3LatentImage"
}
},
"30": {
"inputs": {
"max_shift": 1.15,
"base_shift": 0.5,
"width":"1024",
"height":"1024",
"model": [
"12",
0
]
},
"class_type": "ModelSamplingFlux",
"_meta": {
"title": "ModelSamplingFlux"
}
}
};

const ComfyUI_T2I_ByFluxNF4={
"6": {
"inputs": {
"text":"%prompt%",
"clip": [
"37",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIPTextEncode_Prompt"
}
},
"8": {
"inputs": {
"samples": [
"31",
0
],
"vae": [
"37",
2
]
},
"class_type": "VAEDecode",
"_meta": {
"title": "VAE Decode"
}
},
"9": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"8",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"27": {
"inputs": {
"width":"1024",
"height":"1024",
"batch_size": 1
},
"class_type": "EmptySD3LatentImage",
"_meta": {
"title": "EmptySD3LatentImage"
}
},
"31": {
"inputs": {
"seed":"100",
"steps":"25",
"cfg":"5.0",
"sampler_name":"%sampler%",
"scheduler": "simple",
"denoise": 1,
"model": [
"37",
0
],
"positive": [
"35",
0
],
"negative": [
"33",
0
],
"latent_image": [
"27",
0
]
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"33": {
"inputs": {
"text":"%prompt%",
"clip": [
"37",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIPTextEncode_Prompt"
}
},
"35": {
"inputs": {
"guidance": 3.5,
"conditioning": [
"6",
0
]
},
"class_type": "FluxGuidance",
"_meta": {
"title": "FluxGuidance"
}
},
"37": {
"inputs": {
"ckpt_name": "Flux\\fluxDevSchnellBaseUNET_fluxSchnellFLANFP8.safetensors"
},
"class_type": "CheckpointLoaderNF4",
"_meta": {
"title": "CheckpointLoaderNF4"
}
}
};

const ComfyUI_T2I_ByFluxSimple={
"6": {
"inputs": {
"text":"%prompt%",
"clip": [
"30",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIPTextEncode_Prompt"
}
},
"8": {
"inputs": {
"samples": [
"31",
0
],
"vae": [
"30",
2
]
},
"class_type": "VAEDecode",
"_meta": {
"title": "VAE Decode"
}
},
"9": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"8",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"27": {
"inputs": {
"width":"1024",
"height":"1024",
"batch_size": 1
},
"class_type": "EmptySD3LatentImage",
"_meta": {
"title": "EmptySD3LatentImage"
}
},
"30": {
"inputs":{"ckpt_name":"%model%"},
"class_type": "CheckpointLoaderSimple",
"_meta": {
"title": "Load Checkpoint"
}
},
"31": {
"inputs": {
"seed":"100",
"steps":"25",
"cfg":"5.0",
"sampler_name":"%sampler%",
"scheduler": "simple",
"denoise": 1,
"model": [
"30",
0
],
"positive": [
"35",
0
],
"negative": [
"33",
0
],
"latent_image": [
"27",
0
]
},
"class_type": "KSampler",
"_meta": {
"title": "KSampler"
}
},
"33": {
"inputs": {
"text":"%prompt%",
"clip": [
"30",
1
]
},
"class_type": "CLIPTextEncode",
"_meta": {
"title": "CLIPTextEncode_Prompt"
}
},
"35": {
"inputs": {
"guidance": 3.5,
"conditioning": [
"6",
0
]
},
"class_type": "FluxGuidance",
"_meta": {
"title": "FluxGuidance"
}
}
};

