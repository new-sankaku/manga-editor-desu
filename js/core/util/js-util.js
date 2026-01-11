function generateRandomInt(maxValue) {
if(maxValue==0){
return 0;
}

const intMaxValue=parseInt(maxValue,10);
if (isNaN(intMaxValue)) {
return 0;
}
var result=parseInt(Math.floor(Math.random()*(intMaxValue+1)),10);
if(result===0){
return 1;
}
return result;
}

function getRandomNumber(min,max) {
return Math.floor(Math.random()*(max-min+1))+min;
}

