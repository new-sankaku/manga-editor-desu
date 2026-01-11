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
"filename_prefix": "ComfyUI",
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
"filename_prefix": "ComfyUI",
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
"filename_prefix": "ComfyUI",
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