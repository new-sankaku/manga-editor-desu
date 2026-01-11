let anims=[...document.querySelectorAll("[anim]")];

let click=(el,cb)=>el.addEventListener("click",cb);
let toggle=(el)=>{
el.classList.toggle("toggled");
};

let clickTog=(el)=>{
click(el,()=>toggle(el));
};
anims.map(clickTog);
