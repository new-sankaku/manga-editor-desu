const ComfyUI_T2I_BySDXL_faceDetailer_Lora = {
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
      "filename_prefix": "after",
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
      "filename_prefix": "before",
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




const ComfyUI_T2I_BySDXL_faceDetailer = {
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
      "filename_prefix": "after",
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
      "filename_prefix": "before",
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


const ComfyUI_T2I_BySDXL = {
  3: {
    inputs: {
      seed: 0,
      steps: 25,
      cfg: 6.5,
      sampler_name: "dpmpp_2m_sde",
      scheduler: "exponential",
      denoise: 1,
      model: ["4", 0],
      positive: ["30", 0],
      negative: ["33", 0],
      latent_image: ["5", 0],
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
      samples: ["3", 0],
      vae: ["4", 2],
    },
    class_type: "VAEDecode",
    _meta: {
      title: "VAE Decode",
    },
  },
  28: {
    inputs: {
      filename_prefix: "ComfyUI",
      images: ["8", 0],
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
      clip: ["4", 1],
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
      clip: ["4", 1],
    },
    class_type: "CLIPTextEncodeSDXL",
    _meta: {
      title: "CLIPTextEncodeSDXL Negative",
    },
  },
};
const ComfyUI_T2I_BySDXL_Lora = {
  3: {
    inputs: {
      seed: 0,
      steps: 20,
      cfg: 6.5,
      sampler_name: "euler",
      scheduler: "simple",
      denoise: 1,
      model: ["10", 0],
      positive: ["27", 0],
      negative: ["26", 0],
      latent_image: ["5", 0],
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
      samples: ["3", 0],
      vae: ["4", 2],
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
      model: ["4", 0],
      clip: ["4", 1],
    },
    class_type: "LoraLoader",
    _meta: {
      title: "SDXL LoRA",
    },
  },
  23: {
    inputs: {
      filename_prefix: "ComfyUI",
      images: ["8", 0],
    },
    class_type: "SaveImage",
    _meta: {
      title: "SDXL Refiner+LoRA Image",
    },
  },
  26: {
    inputs: {
      text: "%negative%",
      clip: ["10", 1],
    },
    class_type: "CLIPTextEncode",
    _meta: {
      title: "CLIP Text Encode (Negative)",
    },
  },
  27: {
    inputs: {
      text: "%prompt%",
      clip: ["10", 1],
    },
    class_type: "CLIPTextEncode",
    _meta: {
      title: "CLIP Text Encode (Positive Prompt)",
    },
  },
};
const ComfyUI_T2I_BySDXL_Refiner = {
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
      samples: ["38", 0],
      vae: ["37", 0],
    },
    class_type: "VAEDecode",
    _meta: {
      title: "VAE Decode",
    },
  },
  28: {
    inputs: {
      filename_prefix: "ComfyUI",
      images: ["8", 0],
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
      clip: ["4", 1],
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
      clip: ["4", 1],
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
      model: ["4", 0],
      positive: ["30", 0],
      negative: ["33", 0],
      latent_image: ["5", 0],
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
      model: ["39", 0],
      positive: ["40", 0],
      negative: ["41", 0],
      latent_image: ["36", 0],
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
      clip: ["39", 1],
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
      clip: ["39", 1],
    },
    class_type: "CLIPTextEncodeSDXLRefiner",
    _meta: {
      title: "CLIPTextEncodeSDXLRefiner Negative",
    },
  },
};
const ComfyUI_T2I_BySD15 = {
  3: {
    inputs: {
      seed: 0,
      steps: 25,
      cfg: 6.5,
      sampler_name: "dpmpp_2m",
      scheduler: "karras",
      denoise: 1,
      model: ["4", 0],
      positive: ["6", 0],
      negative: ["7", 0],
      latent_image: ["5", 0],
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
      clip: ["4", 1],
    },
    class_type: "CLIPTextEncode",
    _meta: {
      title: "CLIP Text Encode (Positive)",
    },
  },
  7: {
    inputs: {
      text: "%negative%",
      clip: ["4", 1],
    },
    class_type: "CLIPTextEncode",
    _meta: {
      title: "CLIP Text Encode (Negative)",
    },
  },
  8: {
    inputs: {
      samples: ["3", 0],
      vae: ["4", 2],
    },
    class_type: "VAEDecode",
    _meta: {
      title: "VAE Decode",
    },
  },
  9: {
    inputs: {
      filename_prefix: "Result",
      images: ["8", 0],
    },
    class_type: "SaveImage",
    _meta: {
      title: "Save Image",
    },
  },
};
const ComfyUI_T2I_BySD15_VAE = {
  3: {
    inputs: {
      seed: 0,
      steps: 25,
      cfg: 6.5,
      sampler_name: "dpmpp_2m",
      scheduler: "karras",
      denoise: 1,
      model: ["4", 0],
      positive: ["6", 0],
      negative: ["7", 0],
      latent_image: ["5", 0],
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
      clip: ["4", 1],
    },
    class_type: "CLIPTextEncode",
    _meta: {
      title: "CLIP Text Encode (Positive)",
    },
  },
  7: {
    inputs: {
      text: "%negative%",
      clip: ["4", 1],
    },
    class_type: "CLIPTextEncode",
    _meta: {
      title: "CLIP Text Encode (Negative)",
    },
  },
  8: {
    inputs: {
      samples: ["3", 0],
      vae: ["15", 0],
    },
    class_type: "VAEDecode",
    _meta: {
      title: "VAE Decode",
    },
  },
  9: {
    inputs: {
      filename_prefix: "Result",
      images: ["8", 0],
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
const ComfyUI_T2I_BySD15_Lora = {
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
      "filename_prefix": "Result",
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
const ComfyUI_I2I_BySD15SDXL = {
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