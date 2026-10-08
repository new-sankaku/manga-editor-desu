# halftone
Convert a square image to 45° angled, circle shaped halftone.

"Halftone is the reprographic technique that simulates continuous tone imagery through the use of dots, varying either in size or in spacing, thus genereting a gradient effect".
For more information about halftone images please refer to [Wikipedia](https://en.wikipedia.org/wiki/Halftone#cite_note-campbell-1)

### Installation

This project is built on top of [ImageMagick](http://www.imagemagick.org/script/index.php) and [paper.js](http://paperjs.org/). You first need to install ImageMagick, cairo and pango. Please follow installation documentation from [paper.js](https://github.com/paperjs/paper.js) and [gm](https://github.com/aheckmann/gm). Then:


```sh
git clone https://github.com/Postcard/halftone.git
cd halftone
npm run build 
```

### Example

```
import halftone from './dist/index';

let options = {
	size: 1024,
	density: 3,
	outputFile: 'halftone.jpg'
}

halftone('./resources/portrait.jpg').then((outputFile) => {
	console.log(`Halftone image successfully created at ${outputFile}`)
})
```

![halftone.jpg](https://s3-eu-west-1.amazonaws.com/figure-partage/halftone.png)

