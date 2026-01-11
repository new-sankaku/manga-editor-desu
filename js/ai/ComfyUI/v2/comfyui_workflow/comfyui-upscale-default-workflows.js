const ComfyUI_Upscaler={
"1": {
"inputs": {
"image": "RealESRGAN_00001_.png"
},
"class_type": "LoadImage",
"_meta": {
"title": "Load Image"
}
},
"4": {
"inputs": {
"model_name": "RealESRGAN_x4plus_anime_6B.pth"
},
"class_type": "UpscaleModelLoader",
"_meta": {
"title": "Load Upscale Model"
}
},
"5": {
"inputs": {
"upscale_model": [
"4",
0
],
"image": [
"1",
0
]
},
"class_type": "ImageUpscaleWithModel",
"_meta": {
"title": "Upscale Image (using Model)"
}
},
"6": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"7",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
},
"7": {
"inputs": {
"upscale_method": "lanczos",
"megapixels": 4.000000000000001,
"resolution_steps":10,
"image": [
"5",
0
]
},
"class_type": "ImageScaleToTotalPixels",
"_meta": {
"title": "Scale Image to Total Pixels"
}
}
};