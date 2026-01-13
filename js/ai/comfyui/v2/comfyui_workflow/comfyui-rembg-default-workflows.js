const ComfyUI_Rembg_ByInspyrenet={
"3": {
"inputs": {
"image": "00033-3787218852.png",
"upload": "image"
},
"class_type": "LoadImage",
"_meta": {
"title": "Load Image"
}
},
"23": {
"inputs": {
"torchscript_jit": "default",
"image": [
"3",
0
]
},
"class_type": "InspyrenetRembg",
"_meta": {
"title": "Inspyrenet Rembg"
}
},
"30": {
"inputs": {
filename_prefix: "%date:yyyy-MM-dd%/ComfyUI_%date:yyyyMMdd_hhmmss_SSS%",
"images": [
"23",
0
]
},
"class_type": "SaveImage",
"_meta": {
"title": "Save Image"
}
}
}