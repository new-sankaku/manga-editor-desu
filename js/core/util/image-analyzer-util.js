function createGrid(svgData,pixelRatio=1) {
console.log("createGrid start");

const {viewBox,pathData}=svgData;
const gridWidth=Math.floor(viewBox.width*pixelRatio);
const gridHeight=Math.floor(viewBox.height*pixelRatio);

const grid=Array(gridHeight)
.fill()
.map(()=>Array(gridWidth).fill(0));
const scale=gridWidth/viewBox.width;
const context=document
.createElement("canvas")
.getContext("2d",{willReadFrequently: true});

context.canvas.width=gridWidth;
context.canvas.height=gridHeight;
context.save();
context.scale(scale,scale);
context.fillStyle="white";
context.fillRect(0,0,viewBox.width,viewBox.height);
context.fillStyle="black";

if (pathData.type==="ellipse") {
context.beginPath();
context.ellipse(
pathData.cx,
pathData.cy,
pathData.rx,
pathData.ry,
0,
0,
Math.PI*2
);
context.fill();
} else {
context.fill(new Path2D(pathData.d));
}

context.restore();
const imageData=context.getImageData(0,0,gridWidth,gridHeight);
grid.forEach((row,y)=>
row.forEach(
(cell,x)=>
(grid[y][x]=imageData.data[(y*gridWidth+x)*4]===0 ? 1 : 0)
)
);

return {grid,scale,viewBox};
}

function findLargestRectangle(grid) {
console.log("findLargestRectangle start");

const heights=Array(grid[0].length).fill(0);
let maxRect={x: 0,y: 0,width: 0,height: 0};
let maxArea=0;

for (let row=0;row<grid.length;row++) {
grid[0].forEach(
(cell,col)=>(heights[col]=grid[row][col] ? heights[col]+1 : 0)
);
const stack=[];
let col=0;

while (col<grid[0].length) {
if (!stack.length||heights[stack[stack.length-1]]<=heights[col]) {
stack.push(col++);
} else {
const height=heights[stack.pop()];
const width=
stack.length===0 ? col : col-stack[stack.length-1]-1;
const area=height*width;

if (area>maxArea) {
maxArea=area;
const originalX=
stack.length===0 ? 0 : stack[stack.length-1]+1;
const originalY=row-height+1;
const centerX=originalX+width/2;
const centerY=originalY+height/2;

const newWidth=width*textFrameScaling;
const newHeight=height*textFrameScaling;
maxRect={
x: centerX-newWidth/2,
y: centerY-newHeight/2,
width: newWidth,
height: newHeight,
};
}
}
}

while (stack.length) {
const height=heights[stack.pop()];
const width=
stack.length===0 ? col : col-stack[stack.length-1]-1;
const area=height*width;

if (area>maxArea) {
maxArea=area;
const originalX=stack.length===0 ? 0 : stack[stack.length-1]+1;
const originalY=row-height+1;
const centerX=originalX+width/2;
const centerY=originalY+height/2;

const newWidth=width*textFrameScaling;
const newHeight=height*textFrameScaling;
maxRect={
x: centerX-newWidth/2,
y: centerY-newHeight/2,
width: newWidth,
height: newHeight,
};
}
}
}

return maxRect;
}
