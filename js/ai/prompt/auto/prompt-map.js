class PromptMultiKeyMap{
constructor(){
this.storyOrderMap=new Map();
this.typeMap=new Map();
this.typeSubtypeMap=new Map();
this.typeSubtypePlayMap=new Map();
this.typePlayMap=new Map();
}

add(item){
const{storyOrder,type,subtype,play}=item;
const orderKey=Number(storyOrder);

if(!this.storyOrderMap.has(orderKey)){
this.storyOrderMap.set(orderKey,[]);
}
this.storyOrderMap.get(orderKey).push(item);

if(!this.typeMap.has(type)){
this.typeMap.set(type,[]);
}
this.typeMap.get(type).push(item);

const typeSubtypeKey=type+":"+subtype;
if(!this.typeSubtypeMap.has(typeSubtypeKey)){
this.typeSubtypeMap.set(typeSubtypeKey,[]);
}
this.typeSubtypeMap.get(typeSubtypeKey).push(item);

const typeSubtypePlayKey=type+":"+subtype+":"+play;
if(!this.typeSubtypePlayMap.has(typeSubtypePlayKey)){
this.typeSubtypePlayMap.set(typeSubtypePlayKey,[]);
}
this.typeSubtypePlayMap.get(typeSubtypePlayKey).push(item);

const typePlayKey=type+":"+play;
if(!this.typePlayMap.has(typePlayKey)){
this.typePlayMap.set(typePlayKey,[]);
}
this.typePlayMap.get(typePlayKey).push(item);
}

getByStoryOrder(storyOrder){
const items=this.storyOrderMap.get(Number(storyOrder))||[];
return items.length>0?items[Math.floor(Math.random()*items.length)]:null;
}

getAllByStoryOrder(storyOrder){
return this.storyOrderMap.get(Number(storyOrder))||[];
}

getRandomByStoryOrders(...storyOrders){
const flattenedOrders=storyOrders.flat();
const allItems=[];
flattenedOrders.forEach(order=>{
const items=this.storyOrderMap.get(Number(order))||[];
allItems.push(...items);
});
return allItems.length>0?allItems[Math.floor(Math.random()*allItems.length)]:null;
}

getByStoryOrderRange(start,end){
const items=[];
this.storyOrderMap.forEach((list,order)=>{
if(order>=start&&order<=end){
items.push(...list);
}
});
return items;
}

getRandomByStoryOrderRange(start,end){
const items=this.getByStoryOrderRange(start,end);
return items.length>0?items[Math.floor(Math.random()*items.length)]:null;
}

getRandomByType(type){
const items=this.typeMap.get(type)||[];
return items.length>0?items[Math.floor(Math.random()*items.length)]:null;
}

getRandomByTypeAndSubtype(type,subtype){
const key=type+":"+subtype;
const items=this.typeSubtypeMap.get(key)||[];
return items.length>0?items[Math.floor(Math.random()*items.length)]:null;
}

getRandomByTypeSubtypeAndPlay(type,subtype,play){
const key=type+":"+subtype+":"+play;
const items=this.typeSubtypePlayMap.get(key)||[];
return items.length>0?items[Math.floor(Math.random()*items.length)]:null;
}

getRandomByTypeAndPlay(type,play){
const key=type+":"+play;
const items=this.typePlayMap.get(key)||[];
return items.length>0?items[Math.floor(Math.random()*items.length)]:null;
}
}

const promptMultiKeyMap = new PromptMultiKeyMap();
promptMultiKeyMap.add({storyOrder:100000,type: "opening",subtype: "grab",name: "集団に胸揉まれる",positive: "clothed_male_nude_female, multiple boys, 1girl, group, grabbing_another's_breast, groping, grabbing from behind,looking_at_another,completely_nude, Teary-eyed, sad, looking_down,",negative: "sex, insertion, kiss, grin, grinding, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:200000,type: "solo",subtype: "masturbation",name: "オナニー",positive: "male masturbation",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:200000,type: "solo",subtype: "masturbation",name: "オナニー",positive: "female masturbation",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:300000,type: "foreplay",subtype: "kiss",name: "キス",positive: "kiss",negative: "0",play: "M<-->F"});
promptMultiKeyMap.add({storyOrder:300000,type: "foreplay",subtype: "breast",name: "愛撫胸",positive: "grabbing  breast",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:300000,type: "foreplay",subtype: "nipple",name: "愛撫乳首",positive: "nipple tweak",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:300000,type: "foreplay",subtype: "fingering",name: "愛撫マンコ",positive: "fingering",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:300000,type: "foreplay",subtype: "grab",name: "揉み",positive: "groping",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:300000,type: "foreplay",subtype: "cunnilingus",name: "クンニ",positive: "cunnilingus",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "grinding",name: "股コキ",positive: "grinding",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "hairjob",name: "髪コキ",positive: "hairjob",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "handjob",name: "手コキ",positive: "handjob",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "handjob",name: "手コキ_立ち",positive: "1boy, (reach-around:1.3), handjob, (standing:1.2), penis, penis out, femdom, from front, female_pervert, clothed_female_nude_male, nude_male, completely_nude, female_pov,Glansjob, Cooperative handjob, Reach-around, Reverse grip handjob,",negative: "sex, insertion, kiss, grin, grinding, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "handjob",name: "手コキ_立ち1",positive: "handjob, standing, ",negative: "sex, insertion, kiss, grin, grinding, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "handjob",name: "手コキ_座り",positive: "handjob, sitting, ",negative: "sex, insertion, kiss, grin, grinding, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "handjob",name: "手コキ_亀頭責め_低確率",positive: "Glansjob, handjob, POV, edging handjob,, ",negative: "sex, insertion, kiss, grin, grinding,Blowjob, kiss, fellatio,,",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "handjob",name: "手コキ_授乳",positive: "1boy, nursing handjob, breast sucking,Sucking nipples, penis,looking down,(looking at another:1.2),sitting girl,Baby Play, Embrace, Perspective, depth,clothed female nude male,  upper body, from front, wide shot, pillow, POV, ",negative: "sex, insertion, kiss, grin, grinding,Blowjob, kiss, fellatio, Feet, thighs, knees",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "buttjob",name: "尻コキ",positive: "grinding, buttjob, ass, penis, back, ",negative: "bar_censor, censored, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "buttjob",name: "尻コキ_立ち",positive: "grinding, buttjob, ass, penis, back, standing, ",negative: "bar_censor, censored, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "buttjob",name: "尻コキ_バック",positive: "grinding, buttjob, ass, penis, back, lying, ",negative: "bar_censor, censored, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "footjob",name: "足コキ_立ち",positive: "penis, footjob, foot focus, standing, from below, thighhighs, toenail polish, toenails, hands on own hips",negative: "sex, insertion, kiss, grin, grinding, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "footjob",name: "足コキ",positive: "footjob",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "footjob",name: "足コキ_座り",positive: "feet, footjob, from below, toes, tongue, femdom, sitting, testicles, knees together feet apart, soles, spread toes,",negative: "sex, insertion, kiss, grin, grinding,",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "footjob",name: "足コキ_うつ伏せ_視線無し",positive: "footjob, foot focus, feet up, ass, Lying, (on their stomach:1.2),(the pose:1.2), looking_at_another, ",negative: "sex, insertion, kiss, grin, grinding, thigh_sex, breast,eye, nose, mouth, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:400000,type: "foreplay_job",subtype: "footjob",name: "足コキ_うつ伏せ_視線有り",positive: "footjob, foot focus, feet up, ass, Lying, (on their stomach:1.2),(the pose:1.2), looking_at_another, ",negative: "sex, insertion, kiss, grin, grinding, thigh_sex, breast,",play: "F->M"});
promptMultiKeyMap.add({storyOrder:410000,type: "foreplay_2job",subtype: "handjob",name: "2手コキ_立ち",positive: "double handjob, standing, ",negative: "sex, insertion, kiss, grin, grinding, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:410000,type: "foreplay_2job",subtype: "handjob",name: "2手コキ_座り",positive: "double handjob, sitting, ",negative: "sex, insertion, kiss, grin, grinding, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズリ",positive: "paizuri",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズリ_寝転び_女が上",positive: "penis, nipple, paizuri, straddling paizuri, (girl_on_top:1.2), (lying_on_person:1.2),  Kneeling, ",negative: "bar_censor, censored, boy_on_top, pillow, sheets, looking at viewer,",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズリ_寝転び_女が下",positive: "penis, nipple, paizuri, straddling paizuri, (boy_on_top:1.2), lying, POV",negative: "bar_censor, censored, girl_on_top, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズリ_垂直_膝立ち",positive: "nipple, perpendicular paizuri, paizuri, from side, kneeling, ",negative: "bar_censor, censored,  fellatio, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズリ_膝上",positive: "nipple, penis, paizuri on lap, kneeling, ",negative: "bar_censor, censored,  fellatio, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズリ_ご奉仕",positive: "nipple, penis, paizuri on lap, kneeling, seiza, sitting, from front, lying, POV",negative: "bar_censor, censored,  fellatio, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズリフェラ_寝転び_女が下",positive: "penis, nipple, paizuri, straddling paizuri, (girl_on_top:1.2), (lying_on_person:1.2),  Kneeling,fellatio ",negative: "bar_censor, censored, boy_on_top, pillow, sheets, looking at viewer,",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズリフェラ_寝転び_女が下1",positive: "penis, nipple, paizuri, straddling paizuri, (boy_on_top:1.2), lying, POV, fellatio",negative: "bar_censor, censored, girl_on_top, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズリフェラ_膝上",positive: "nipple, penis, paizuri on lap, kneeling, fellatio",negative: "bar_censor, censored,   ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "paizuri",name: "パイズフェラ_ご奉仕",positive: "nipple, penis, paizuri on lap, kneeling, seiza, sitting, from front, lying, POV, fellatio",negative: "bar_censor, censored,  ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "irrumatio",name: "イラマチオ",positive: "deepthroat, throat bulge, Testicles, ",negative: "sex, insertion, grin, grinding, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "irrumatio",name: "イラマチオ_ハンドオン",positive: "irrumatio, deepthroat, throat bulge, head grab, hands on another's head , hand on another's head, pubic hair, wet_clothes, wet_shirt, wet, Testicles",negative: "sex, insertion, grin, grinding, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "irrumatio",name: "イラマチオ_アフター",positive: "dropping, Saliva, crying with eyes open, crying, cum in nose, streaming_tears, pubic hair, wet_clothes, wet_shirt, wet, Testicles, after ejaculation ,after fellatio ,cum ,cumdrip, cum_on_clothes, cum_on_hands, cum_on_hair, cum_on_breasts, cum in mouth ,cum in nose ,cum on body ,cum on penis ,cum on tongue ,cum string ,facial ,fellatio ,open mouth ,oral ,penis ,saliva ,tongue ,tongue out , blush, ",negative: "insertion, grin, grinding, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "fellatio",name: "フェラ",positive: "fellatio",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "fellatio",name: "フェラ_舐め",positive: "licking_penis",negative: "sex, insertion, grin, grinding, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "fellatio",name: "フェラ_亀頭舐め",positive: "Glansjob, handjob, POV, edging handjob, cloth glansjob, panties, (edging blowjob:1.2),kissing penis,",negative: "sex, insertion, kiss, grin, grinding, kiss, deepthroat,,",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "fellatio",name: "フェラ_アフター",positive: "after ejaculation ,after fellatio ,cum ,cumdrip, cum_on_clothes, cum_on_hands, cum_on_hair, cum_on_breasts, cum in mouth ,cum in nose ,cum on body ,cum on penis ,cum on tongue ,cum string ,facial ,fellatio ,open mouth ,oral ,penis ,saliva ,tongue ,tongue out , blush, ",negative: "insertion, grin, grinding, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "fellatio",name: "2フェラ",positive: "2girls, cooperative fellatio,",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "fellatio",name: "フェラ_POV＋",positive: "fellatio,POV",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "fellatio",name: "フェラ_POV＋服＋",positive: "fellatio,POV, pov_crotch",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "fellatio",name: "フェラ_唾液汗＋",positive: "fellatio,(dropping:1.3), (Saliva:1.3), sweatdrop, sweat, ",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:420000,type: "foreplay",subtype: "fellatio",name: "フェラ_涙＋",positive: "fellatio, crying with eyes open, crying, cum in nose, streaming_tears,",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "missionary",name: "正常位",positive: "couple, sex, insertion, ,penis, pussy, ,missionary position, man on top, lying",negative: "bar_censor, censored, ass",play: "M<-->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "missionary",name: "正常位_胸揉まれ",positive: "couple, sex, insertion, ,penis, pussy, ,missionary position, boy grabbing girls breasts by hands",negative: "bar_censor, censored, ",play: "M<-->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "missionary",name: "正常位_大しゅきホールド",positive: "couple, sex, insertion, ,arms_around_neck , mutual_hug, legs around waist, Deep kiss, leg lock, carrying, mutual hug, missionary position, boy on top , lying, ",negative: "bar_censor, censored, ",play: "M<-->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "missionary",name: "正常位_手つなぎ",positive: "couple, sex, insertion, penis, pussy, ,missionary position, (holding hands:1.2), POV, hands, ",negative: "bar_censor, censored, ",play: "M<-->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "missionary",name: "正常位_腕掴まれ_低確率",positive: "couple, sex, insertion, penis, pussy, ,missionary position, (holding_another's_arm:1.2), arm, grabbing_another's_arm ",negative: "insertion, grin, grinding, pose, hand, arms behind back, breast_hold",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "missionary",name: "正常位_マンぐり返し",positive: "couple, sex, insertion, penis, pussy, ,missionary position, spread legs, (legs up:1.2), mating press, boy on top, piledriver (sex),  Sole, from above, holding, depth, perspective,from above, POV, Floating hips, shadow, ",negative: "insertion, grin, grinding, pillow",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "standing",name: "立位対面_低確",positive: "couple, sex, (insertion:1.1), ,penis, (standing sex:1.1),  wide hip, big hip, looking_ahead,  (grabbing_another's_ass:1.2), hug, ",negative: "bar_censor, censored, looking_at_viewer, carrying, carrying person, leglock, Standing on one leg, standing split, standing_on_one_leg, crossed_legs, spread_legs, standing_split, leg lift, arms_around_neck, sex from behind, standing missionary,reverse suspended congress, suspended congress",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "standing",name: "立位対面_抱え込み",positive: "couple, sex, insertion, ,penis, standing_sex, (carrying:1.2), (carrying person:1.2), lifting, holding from front, Sole, pussy, suspended_congress, leg lock, arms_around_neck, kiss, looking_at_another, ",negative: "bar_censor, censored, looking_at_viewer",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "standing",name: "立位背面_立ち",positive: "couple, sex, insertion, ,penis, standing_sex, sex from behind, arm_held_back",negative: "bar_censor, censored, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "standing",name: "立位背面_片足上げ",positive: "couple, sex, insertion, ,penis, standing_split, sex from behind, arm_held_back, standing on one leg, leg up, leg hold, standing sex, ",negative: "bar_censor, censored, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "standing",name: "立位背面_抱え込み",positive: "couple, sex, insertion, ,penis, pussy, standing_sex, thigh strap, (carrying:1.2), (carrying person:1.2), lifting from front, holding from front, looking_at_viewer, from ftont, Sole, pussy, suspended_congress, spread_legs, ",negative: "bar_censor, censored, looking_at_viewer",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "scissors",name: "座位対面_膝立ち",positive: "couple, sex, insertion, ,arms_around_neck , mutual_hug, legs around waist, Deep kiss, leg lock, carrying, mutual hug, Scissors Position, Kneeling,",negative: "bar_censor, censored, Sit upright, seiza, bald_girl, standing, sitting",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "scissors",name: "座位背面_膝立ち1",positive: "couple, sex, insertion, ,(sex from behind:1.3),  (hug_from_behind:1.3), (Hands On Ground, Hands On floor:0.8), breast_lift, arms_at_sides, Kneeling, ",negative: "bar_censor, censored, Sit upright, seiza, bald_girl, standing, sitting",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "scissors",name: "座位対面",positive: "couple, sex, insertion, ,upright_straddle, sitting on lap",negative: "bar_censor, censored, bald_girl, standing, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:500000,type: "sex",subtype: "scissors",name: "座位背面",positive: "couple, sex, insertion, ,reverse_upright_straddle, sitting on lap, sitting on person, sex from behind, grabbing from behind, grabbing another's breast, back, ",negative: "bar_censor, censored, bald_girl, standing, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "cowgirl",name: "騎乗位",positive: "couple, sex, insertion, ,girl on top, cowgirl , POV, thigh_sex, grinding, from front, Hips move back and forth,",negative: "0",play: "F->M"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "cowgirl",name: "騎乗位ガニ股",positive: "couple, sex, insertion, ,spread legs, squatting cowgirl position, girl on top, cowgirl , POV,Hands on the ground, Grab waist, ",negative: "bar_censor, censored, ass",play: "F->M"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "cowgirl",name: "騎乗位背面_ピストン上",positive: "couple, sex, insertion, ,spread legs, reverse cowgirl position, squatting cowgirl position, squatting cowgirl position, Back, buttocks, looking_at_another,penis, faceless, Stretched",negative: "bar_censor, censored, navel, waist, looking_at_viewer, breast, ",play: "F->M"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "cowgirl",name: "騎乗位背面_ピストン下",positive: "couple, sex, insertion, ,spread legs, reverse cowgirl position, squatting cowgirl position, Back, buttocks, looking_at_another,penis, faceless, Stretched",negative: "bar_censor, censored, navel, waist, looking_at_viewer, breast, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "lying",name: "測位対面",positive: "couple, sex, insertion, ,penis, pussy, ,(hug:1.1), buttocks, hug, embracing, close together, bed, (spooning:1.2),  lying, looking at another, kiss",negative: "from_behind, back hug, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "lying",name: "測位背面",positive: "couple, sex, insertion, ,penis, pussy, ,(Back hug:1.1), buttocks, hug, embracing, close together, bed, (from side:1.3), looking_at_another , (spooning:1.2), (on side:1.2), (fetal position girl:1.2)",negative: "bar_censor, censored, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "back",name: "バック",positive: "couple, sex, insertion, ,penis, pussy, ,doggystyle,sex from behind , ,  bent_over, top-down_bottom-up",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "back",name: "立ちバック",positive: "couple, sex, insertion, ,penis, pussy, ,doggystyle,sex from behind , ,  hands on own knees,hands on own thighs,bent_over, standing, standing_sex,frontbend,leaning forward,arm held back,",negative: "bar_censor, censored, Kneeling",play: "M->F"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "back",name: "寝バック",positive: "couple, sex, insertion, ,penis, pussy, ,doggystyle,sex from behind , ,  prone_bone, pillow_hug, sheet_grab, lying,deep penetration ",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:510000,type: "sex",subtype: "back",name: "寝バック+枕",positive: "couple, sex, insertion, ,penis, pussy, ,doggystyle,sex from behind , ,  prone_bone, sheet_grab, lying, deep penetration ",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:600000,type: "sex",subtype: "press",name: "種付けプレス",positive: "couple, sex, insertion, ,penis, pussy, ,mating_press,boy on top,deep penetration, folded , leg lock, puckered anus, anus, ass, testicles, vaginal, ",negative: "bar_censor, censored, (hair:1.2), socks, ponytail, ",play: "M->F"});
promptMultiKeyMap.add({storyOrder:700000,type: "ejaculation",subtype: "cum",name: "ぶっかけ",positive: "cum",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:700000,type: "ejaculation",subtype: "cum",name: "中だし口",positive: "cum in mouth",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:700000,type: "ejaculation",subtype: "cum",name: "中だしまんこ",positive: "cum in pussy",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:700000,type: "ejaculation",subtype: "cum",name: "ぶっかけ髪",positive: "cum on hair",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:700000,type: "ejaculation",subtype: "cum",name: "ぶっかけまんこ",positive: "cum on pussy",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:700000,type: "ejaculation",subtype: "cum",name: "ぶっかけボディ",positive: "cum on body",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:700000,type: "ejaculation",subtype: "cum",name: "ぶっかけお腹",positive: "cum on stomach",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:700000,type: "ejaculation",subtype: "cum",name: "ぶっかけ服",positive: "cum on clothes",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:800000,type: "sex_after",subtype: "sex",name: "セックス後",positive: "after sex",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:800000,type: "sex_after",subtype: "insert",name: "挿入後",positive: "after insertion",negative: "0",play: "M->F"});
promptMultiKeyMap.add({storyOrder:800000,type: "sex_after",subtype: "rape",name: "レイプ後",positive: "after rape",negative: "0",play: "M->F"});


// console.log(promptMultiKeyMap.getByStoryOrder(10000));
// console.log(promptMultiKeyMap.getRandomByStoryOrderRange(11000, (11000+99) ));
// console.log(promptMultiKeyMap.getRandomByType("foreplay"));
// console.log(promptMultiKeyMap.getRandomByTypeAndSubtype("foreplay", "kiss"));