(function(fabric){

fabric.util.getRandom=function(max,min){
min=min ? min : 0;
return Math.random()*((max ? max : 1)-min)+min;
};

fabric.util.clamp=function (n,max,min) {
if (typeof min!=='number') min=0;
return n>max ? max : n<min ? min : n;
};

})(fabric);