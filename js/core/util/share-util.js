function openWindow(url) {
var width=700;
var height=700;
var left=(screen.width/2)-(width/2);
var top=(screen.height/2)-(height/2);
window.open(url,'ShareWindow','toolbar=no, location=no, status=no, menubar=no, scrollbars=no, resizable=no, width='+width+', height='+height+', top='+top+', left='+left);
}

function snsTweet(){
clipCopy();

var tweetText="\nCreated by Manga Editor Desu!\n#Manga_Editor_Desu\n[Web site]\nhttps://new-sankaku.github.io/SP-MangaEditer/\n[Webui extension]\nhttps://github.com/new-sankaku/stable-diffusion-webui-simple-manga-maker";
var tweetUrl="https://twitter.com/intent/tweet?text="+encodeURIComponent(tweetText);
openWindow(tweetUrl);
}
