(()=>{
'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const DAY=864e5, KEY='navaja-demo-v1';
const eur=n=>Number(n||0).toLocaleString('es-ES',{style:'currency',currency:'EUR'});
const uid=()=>Math.random().toString(36).slice(2,9);
const PAGE=window.APP_PAGE, TABS=window.APP_TABS;
const CHECK='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
const SCISSORS='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4L8.12 15.88M14.47 14.48L20 20M8.12 8.12L12 12"/></svg>';
const STAR='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.5 1.3 6.6L12 17.2 6.1 20.5l1.3-6.6L2.5 9.4l6.6-.8z"/></svg>';
const ICONS={check:CHECK,tijera:SCISSORS,estrella:STAR};

/* ---------- valores por defecto ---------- */
const defCfg=()=>({
  name:'La Navaja',tagline:'Barber\u00eda cl\u00e1sica',logo:'',c1:'#1B1D22',c2:'#C9A15B',fg:'#F3EEE4',stampIcon:'tijera',stripes:true,
  program:'sellos',stamps:6,pointsPerEuro:10,pointsGoal:250,cashbackPct:5,cashbackMin:5,reward:'Un corte de pelo gratis',
  minWait:30,coupon:'PRIMERCORTE',refBonus:1,qrUrl:'',tiersOn:true,
  tiers:[{name:'De confianza',visits:5,perk:'Toalla caliente de cortes\u00eda'},{name:'De la casa',visits:15,perk:'5 % de descuento en cada servicio'}],
  welcome:'Guarda tu tarjeta de La Navaja en el m\u00f3vil y consigue un corte gratis.',
  rules:'Cada visita suma un sello, pidas corte, barba o los dos.\nCuando completes la tarjeta, tu pr\u00f3ximo corte es gratis.\nLos sellos no caducan.\nEl sello lo pone tu barbero escaneando tu tarjeta.',
  terms:'El premio no es acumulable con otras promociones ni canjeable por dinero. Un sello por visita.',
  address:'Calle Mayor 14, local 2',hours:'Martes a viernes 10:00 a 20:00\nS\u00e1bados 9:00 a 15:00\nDomingo y lunes cerrado',phone:'600 123 456',
  services:[{name:'Corte',price:14},{name:'Corte y barba',price:20},{name:'Barba',price:8},{name:'Afeitado a navaja',price:12},{name:'Corte infantil',price:10}]
});
const defTpl=()=>[
 {k:'sello',label:'Cada visita',when:'Cada vez que el barbero da un sello, puntos o saldo',auto:true,body:'\u00a1Gracias por venir, {nombre}! {progreso}'},
 {k:'premio',label:'Premio listo',when:'Cuando el cliente completa la tarjeta',auto:true,body:'\u00a1Tu premio te espera! \ud83c\udf81 {premio}. Ense\u00f1a la tarjeta en caja.'},
 {k:'falta',label:'Te falta poco',when:'Clientes que est\u00e1n cerca del premio',auto:false,body:'{nombre}, te falta poco para tu premio. {progreso} P\u00e1sate esta semana.'},
 {k:'echamos',label:'Te echamos de menos',when:'Clientes que llevan m\u00e1s de 3 semanas sin venir',auto:false,body:'Ya toca repasar ese corte, {nombre} \u2702\ufe0f Hace tiempo que no pasas por {negocio}. {progreso}'},
 {k:'cumple',label:'Cumplea\u00f1os',when:'El d\u00eda del cumplea\u00f1os del cliente',auto:false,body:'\u00a1Feliz cumplea\u00f1os, {nombre}! \ud83c\udf82 P\u00e1sate esta semana y la toalla caliente va de nuestra parte.'},
 {k:'cerca',label:'Cerca del local',when:'Cuando el cliente pasa cerca de la barber\u00eda',auto:false,body:'\ud83d\udccd Est\u00e1s cerca de {negocio}, {nombre}. \u00bfUn repaso r\u00e1pido? {progreso}'},
 {k:'resena',label:'Pide una rese\u00f1a',when:'Un d\u00eda despu\u00e9s de una visita',auto:false,body:'\u00a1Gracias por venir, {nombre}! \u00bfNos dejas una rese\u00f1a en Google? \u2b50'},
 {k:'invita',label:'Trae a un amigo',when:'Para captar clientes nuevos',auto:false,body:'Trae a un amigo con tu c\u00f3digo {codigo}: cuando se apunte, los dos sum\u00e1is un extra \ud83c\udf81'},
 {k:'nivel',label:'Nuevo nivel',when:'Cuando el cliente sube de nivel',auto:true,body:'\u00a1Enhorabuena, {nombre}! \ud83c\udf89 Ya eres cliente {nivel}: {ventaja}.'},
 {k:'mes',label:'Aviso del mes',when:'Una promoci\u00f3n puntual para todos',auto:false,body:'Este martes, corte y barba a precio especial, solo con la tarjeta \u2702\ufe0f'}
];
const defTeam=()=>[{id:'t1',name:'Tom\u00e1s',pin:'1111'},{id:'t2',name:'Gabi',pin:'2222'},{id:'t3',name:'Leo',pin:'3333'}];

let S=null;
const U={tab:TABS[0],pcid:null,tid:null,scid:null,svc:0,amt:'',offline:false,ignoreWait:false,week:'last',queue:[],confirm:null,msg:null,ssearch:'',csearch:''};
function load(){try{const r=localStorage.getItem(KEY);if(r){const o=JSON.parse(r);if(o&&o.cfg&&o.customers)return o}}catch(e){}return null}
/* ---------- guardado: nube compartida si hay servidor, si no solo este navegador ---------- */
const API='api/state',ME='navaja-me',SECS=['cfg','tpl','team','props'];
let MODE='local',VER=0,B={c:{},s:{},m:''},SAVES=0,INFLIGHT=false,AGAIN=false,FORCE=false,PENDING=false,_t;
const meGet=()=>{try{return localStorage.getItem(ME)}catch(e){return null}};
const meSet=id=>{try{id?localStorage.setItem(ME,id):localStorage.removeItem(ME)}catch(e){}};
const strip=c=>JSON.stringify({...c,u:undefined});
function snapshot(){const b={c:{},s:{},m:String(S.lastPcid)};S.customers.forEach(c=>{b.c[c.id]=strip(c)});SECS.forEach(k=>{b.s[k]=JSON.stringify(S[k])});return b}
function stampChanges(){const now=Date.now();S.at=S.at||{};S.del=S.del||{};
  const ids=new Set(S.customers.map(c=>c.id));
  S.customers.forEach(c=>{if(B.c[c.id]!==strip(c)||c.u==null)c.u=now});
  Object.keys(B.c).forEach(id=>{if(!ids.has(id))S.del[id]=now});
  SECS.forEach(k=>{if(B.s[k]!==JSON.stringify(S[k])||S.at[k]==null)S.at[k]=now});
  if(B.m!==String(S.lastPcid)||S.at.m==null)S.at.m=now}
function cache(){try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}}
function save(replace){SAVES++;PENDING=true;if(replace===true)FORCE=true;clearTimeout(_t);_t=setTimeout(flush,MODE==='cloud'?350:250)}
async function flush(){
  PENDING=false;
  if(MODE!=='cloud'){cache();return}
  if(INFLIGHT){AGAIN=true;return}
  INFLIGHT=true;const sc=SAVES,replace=FORCE;FORCE=false;
  try{stampChanges();cache();const snap=snapshot();
    const r=await fetch(API,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({state:S,replace})});
    const j=await r.json();
    if(r.ok&&j&&j.state){if(SAVES===sc||j.stale)adopt(j.state,j.ver);else{VER=j.ver;B=snap}}
  }catch(e){}
  INFLIGHT=false;
  if(AGAIN||SAVES!==sc){AGAIN=false;flush()}
}
function editing(){const a=document.activeElement;return !!a&&/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)&&a.type!=='checkbox'&&a.type!=='radio'&&a.type!=='button'}
function adopt(state,ver){S=state;VER=ver;B=snapshot();cache();if(!editing())render()}
async function poll(){
  if(MODE!=='cloud'||INFLIGHT||PENDING||document.hidden||editing())return;
  try{const r=await fetch(API+'?v='+VER+'&t='+Date.now(),{cache:'no-store'});const j=await r.json();
    if(r.ok&&!j.same&&j.state&&j.ver!==VER&&!PENDING&&!INFLIGHT)adopt(j.state,j.ver)}catch(e){}
}
function toast(t){const e=$('#toast');if(!e)return;e.textContent=t;e.classList.add('on');clearTimeout(toast._t);toast._t=setTimeout(()=>e.classList.remove('on'),2600)}

/* ---------- l\u00f3gica ---------- */
const cust=id=>S.customers.find(c=>c.id===id);
const team=id=>S.team.find(m=>m.id===id);
const goalOf=()=>S.cfg.program==='sellos'?S.cfg.stamps:S.cfg.program==='puntos'?S.cfg.pointsGoal:S.cfg.cashbackMin;
function rewardReady(c){const f=S.cfg;return f.program==='sellos'?c.stamps>=f.stamps:f.program==='puntos'?c.points>=f.pointsGoal:c.balance>=f.cashbackMin}
function pct(c){const f=S.cfg;const v=f.program==='sellos'?c.stamps/f.stamps:f.program==='puntos'?c.points/f.pointsGoal:c.balance/f.cashbackMin;return Math.max(0,Math.min(1,v||0))}
function progressText(c){const f=S.cfg;if(rewardReady(c))return '\u00a1Tienes el premio listo!';
  if(f.program==='sellos')return 'Llevas '+c.stamps+' de '+f.stamps+' sellos.';
  if(f.program==='puntos')return 'Llevas '+c.points+' de '+f.pointsGoal+' puntos.';
  return 'Tu saldo es '+eur(c.balance)+'.'}
function shortProgress(c){const f=S.cfg;return f.program==='sellos'?Math.min(c.stamps,f.stamps)+'/'+f.stamps:f.program==='puntos'?c.points+' pts':eur(c.balance)}
function sortedTiers(){return S.cfg.tiers.filter(t=>t.name).sort((a,b)=>a.visits-b.visits)}
function levelOf(c){if(!S.cfg.tiersOn)return null;return sortedTiers().filter(t=>c.visits>=t.visits).pop()||null}
function nextLevel(c){if(!S.cfg.tiersOn)return null;return sortedTiers().find(t=>t.visits>c.visits)||null}
function fill(body,c){const lv=levelOf(c)||S.cfg.tiers[0]||{name:'',perk:''};
  return String(body).replace(/\{(\w+)\}/g,(m,k)=>({nombre:c.name,negocio:S.cfg.name,premio:S.cfg.reward,progreso:progressText(c),codigo:c.code,nivel:lv.name,ventaja:lv.perk}[k]??m))}
function pushNotif(c,k,t,bodyOverride){const tp=S.tpl.find(x=>x.k===k);if(!tp)return;
  S.notifs.push({id:uid(),t:t||Date.now(),cid:c.id,k,label:tp.label,body:bodyOverride||fill(tp.body,c)})}
function newCustomer(o){const c={id:uid(),code:'C-'+(1000+(++S.seq)),name:o.name,email:o.email||'',bday:o.bday||'',source:o.source||'mostrador',device:o.device||'',created:o.created||Date.now(),stamps:0,points:0,balance:0,visits:0,rewards:0,spend:0,last:0};S.customers.push(c);return c}
function bonus(c){const f=S.cfg,b=Number(f.refBonus)||0;if(f.program==='sellos')c.stamps+=b;else if(f.program==='puntos')c.points+=b;else c.balance=Math.round((c.balance+b)*100)/100}
function visit(c,{ts=Date.now(),tid,amount=0,service='',silent=false,force=false}){
  const f=S.cfg;
  if(!force&&c.last&&f.minWait>0&&ts-c.last<f.minWait*60000){const left=Math.ceil((f.minWait*60000-(ts-c.last))/60000);
    return {ok:false,msg:c.name+' ya sum\u00f3 hace poco. Espera '+left+' min m\u00e1s, o activa \u00abIgnorar la espera\u00bb para la demo.'}}
  const before={ready:rewardReady(c),lvl:(levelOf(c)||{}).name};
  let value=1;
  if(f.program==='sellos')c.stamps+=1;
  else if(f.program==='puntos'){value=Math.round(amount*f.pointsPerEuro);c.points+=value}
  else{value=Math.round(amount*f.cashbackPct)/100;c.balance=Math.round((c.balance+value)*100)/100}
  c.visits++;c.last=ts;c.spend+=amount||0;
  S.events.push({id:uid(),t:ts,cid:c.id,tid,type:'visit',amount,value,service});
  const ready=rewardReady(c);
  if(!silent){
    const on=k=>(S.tpl.find(x=>x.k===k)||{}).auto;
    if(on('sello'))pushNotif(c,'sello',ts);
    if(!before.ready&&ready&&on('premio'))pushNotif(c,'premio',ts+1);
    const lv=levelOf(c);if(lv&&lv.name!==before.lvl&&on('nivel'))pushNotif(c,'nivel',ts+2);
  }
  return {ok:true,value,ready,msg:'Listo, '+c.name+'. '+progressText(c)}
}
function redeem(c,{ts=Date.now(),tid}){const f=S.cfg;let value=1;
  if(f.program==='sellos')c.stamps=Math.max(0,c.stamps-f.stamps);else if(f.program==='puntos'){c.points=Math.max(0,c.points-f.pointsGoal);value=f.pointsGoal}else{value=c.balance;c.balance=0}
  c.rewards++;S.events.push({id:uid(),t:ts,cid:c.id,tid,type:'reward',amount:0,value,service:''});return value}

/* ---------- datos de ejemplo ---------- */
function seedData(keep){
  const cfg=(keep&&keep.cfg)||defCfg();
  S={v:1,epoch:uid(),cfg,seq:0,customers:[],events:[],notifs:[],tpl:(keep&&keep.tpl)||defTpl(),props:[],lastPcid:null,team:(keep&&keep.team)||defTeam(),at:{},del:{}};
  let a=11;const rng=()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296};
  const now=Date.now();
  const names=['Carlos','Jordi','Pablo','Iv\u00e1n','Rub\u00e9n','Sergio','Marcos','Adri\u00e0','V\u00edctor','Hugo','\u00c1lvaro','Ra\u00fal','Nacho','Toni','Marc','Joan','Pol','Biel','Nil','\u00d3scar','Lucas','Diego','Mateo','Eric','Gerard','Pere','Alberto','Dani'];
  const mail=n=>n.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase()+'@ejemplo.com';
  const W=[4,3,1.5,1,1];
  const pick=()=>{const sv=cfg.services;if(!sv.length)return null;const ws=sv.map((_,i)=>W[i]??1);let r=rng()*ws.reduce((x,y)=>x+y,0);for(let i=0;i<sv.length;i++){r-=ws[i];if(r<=0)return sv[i]}return sv[0]};
  const tids=S.team.map(m=>m.id);
  const vis=[];
  names.forEach((n,i)=>{
    const g=i<8?'R':i<16?'N':i<22?'M':i<25?'B':'C';
    let created,times=[];
    const pre=k=>{for(let j=0;j<k;j++)times.push(now-(50+j*21+rng()*5)*DAY)};
    const rec=(k,last,sp)=>{for(let j=0;j<k;j++)times.push(now-(last+j*sp*(.8+.4*rng()))*DAY)};
    if(g==='R'){created=now-(130+rng()*70)*DAY;pre(3+Math.floor(rng()*6));rec(3+Math.floor(rng()*2),rng()*8,10)}
    else if(g==='N'){const age=2+rng()*32;created=now-age*DAY;const k=1+Math.floor(rng()*Math.min(3,1+age/10));for(let j=0;j<k;j++)times.push(created+(now-created)*rng())}
    else if(g==='M'){created=now-(70+rng()*40)*DAY;pre(1+Math.floor(rng()*3));rec(1+Math.floor(rng()*2),2+rng()*12,14)}
    else if(g==='B'){created=now-130*DAY;pre(2+Math.floor(rng()*3));times.push(now-(28+rng()*15)*DAY)}
    else{created=now-130*DAY;pre(2+Math.floor(rng()*2));times.push(now-(30+rng()*8)*DAY);times.push(now-(1+rng()*3)*DAY)}
    const r=rng();const src=g!=='N'?'mostrador':r<.6?'mostrador':r<.85?'amigo':'cupon';
    const c=newCustomer({name:n,email:mail(n),source:src,created,device:rng()<.55?'apple':'google'});
    if(rng()<.6){const m=1+Math.floor(rng()*12),d=1+Math.floor(rng()*27);c.bday=String(m).padStart(2,'0')+'-'+String(d).padStart(2,'0')}
    if(i===1||i===9){const d=new Date();c.bday=String(d.getMonth()+1).padStart(2,'0')+'-'+String(Math.min(27,d.getDate()+3)).padStart(2,'0')}
    times.forEach(t=>{const sv=pick();vis.push({t,c,tid:tids[Math.floor(rng()*tids.length)],service:sv?sv.name:'',amount:sv?sv.price:(cfg.program==='sellos'?0:15)})});
  });
  vis.sort((x,y)=>x.t-y.t).forEach(v=>{
    if(rewardReady(v.c)&&rng()<.7)redeem(v.c,{ts:v.t-1000,tid:v.tid});
    visit(v.c,{ts:v.t,tid:v.tid,amount:v.amount,service:v.service,silent:true,force:true});
  });
  const t3=now-3*DAY,t5=now-5*DAY,t2=now-2*DAY;
  const tp=k=>S.tpl.find(x=>x.k===k);
  S.customers.forEach(c=>{if(c.created<t3&&tp('mes'))pushNotif(c,'mes',t3)});
  S.customers.forEach(c=>{const prev=S.events.filter(e=>e.cid===c.id&&e.type==='visit'&&e.t<t5).sort((x,y)=>y.t-x.t)[0];
    if(prev&&t5-prev.t>21*DAY&&tp('echamos'))pushNotif(c,'echamos',t5)});
  S.customers.filter(c=>c.bday).slice(0,4).forEach(c=>{if(tp('cumple'))pushNotif(c,'cumple',t2)});
  S.customers.filter(rewardReady).forEach(c=>{if(tp('premio'))pushNotif(c,'premio',now-DAY)});
  S.customers.forEach(c=>{const last=S.events.filter(e=>e.cid===c.id&&e.type==='visit').sort((x,y)=>y.t-x.t)[0];if(last&&now-last.t<8*DAY&&tp('sello'))pushNotif(c,'sello',last.t)});
  save();
}

/* ---------- piezas visuales ---------- */
function monoHTML(){const f=S.cfg;return f.logo?'<img alt="" src="'+f.logo+'">':'<span>'+esc((f.name||'?').trim().charAt(0).toUpperCase())+'</span>'}
function qrSvg(text){
  try{const q=qrcode(0,'M');q.addData(String(text||'qr'));q.make();const n=q.getModuleCount();let d='';
    for(let r=0;r<n;r++)for(let c=0;c<n;c++)if(q.isDark(r,c))d+='M'+(c+1)+' '+(r+1)+'h1v1h-1z';
    return '<svg viewBox="0 0 '+(n+2)+' '+(n+2)+'" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges" role="img" aria-label="C\u00f3digo QR"><path d="'+d+'" fill="#111"/></svg>'}
  catch(e){return '<div style="padding:30px 0;font:600 14px sans-serif;text-align:center">QR</div>'}}
const PUBLIC_URL='https://claude.ai/artifact/XeaYE8SB7BYQLtJx7eDKZD';
function counterUrl(){let u=(S.cfg.qrUrl||'').trim();if(u)return u;try{if(/^https?:/.test(location.href)&&/(^localhost|^127\.|github\.io$|vercel\.app$)/.test(location.hostname))return new URL('index.html',location.href).href}catch(e){}return PUBLIC_URL}
function cardHTML(c){
  const f=S.cfg,lv=levelOf(c),ic=ICONS[f.stampIcon]||CHECK;let main='';
  if(f.program==='sellos'){const n=f.stamps;let cells='';for(let i=0;i<n;i++)cells+='<i class="'+(i<c.stamps?'on':'')+'">'+(i<c.stamps?ic:(i+1))+'</i>';
    main='<div class="pass-stamps" style="grid-template-columns:repeat('+Math.ceil(n/2)+',1fr)">'+cells+'</div><div class="pass-note">'+Math.min(c.stamps,n)+' de '+n+' sellos'+(c.stamps>=n?' \u00b7 premio listo':'')+'</div>'}
  else if(f.program==='puntos')main='<div class="pass-big">'+c.points+'<small>puntos</small></div><div class="pass-bar"><i style="width:'+pct(c)*100+'%"></i></div><div class="pass-note">'+(c.points>=f.pointsGoal?'Premio listo':'Te faltan '+(f.pointsGoal-c.points)+' puntos para el premio')+'</div>';
  else main='<div class="pass-big">'+eur(c.balance)+'<small>de saldo</small></div><div class="pass-bar"><i style="width:'+pct(c)*100+'%"></i></div><div class="pass-note">'+f.cashbackPct+' % de cada servicio vuelve a ti \u00b7 m\u00ednimo '+eur(f.cashbackMin)+'</div>';
  return '<div class="pass" style="--p-bg:'+f.c1+';--p-ac:'+f.c2+';--p-fg:'+f.fg+'">'+(f.stripes?'<div class="pass-stripe"></div>':'')+'<div class="pass-head"><span class="pass-logo">'+monoHTML()+'</span><span class="pass-name">'+esc(f.name)+'</span>'+(lv?'<span class="pass-level">'+esc(lv.name)+'</span>':'')+'</div>'
   +main+'<div class="pass-meta"><div><label>Premio</label><b>'+esc(f.reward)+'</b></div><div><label>Cliente</label><b>'+esc(c.name)+'</b></div></div>'
   +'<div class="pass-qr">'+qrSvg('NAVAJA:'+c.code)+'</div><div class="pass-code">'+esc(c.code)+'</div></div>'}
function sampleCust(){const f=S.cfg;return {id:'x',name:'Carlos',code:'C-1001',stamps:Math.min(3,f.stamps-1),points:Math.round(f.pointsGoal*.45),balance:Math.round(f.cashbackMin*.6*100)/100,visits:4,email:''}}
function notifHTML(name,body,time){const f=S.cfg;return '<div class="n-ico" style="background:'+f.c2+';color:'+f.c1+'">'+monoHTML()+'</div><div class="n-body"><div class="n-top"><b>'+esc(name)+'</b><span>'+esc(time)+'</span></div><p>'+esc(body)+'</p></div>'}
function rel(t){const d=Date.now()-t;if(d<6e4)return 'ahora';if(d<36e5)return 'hace '+Math.floor(d/6e4)+' min';if(d<DAY)return 'hace '+Math.floor(d/36e5)+' h';if(d<2*DAY)return 'ayer';return 'hace '+Math.floor(d/DAY)+' d'}
function dshort(t){return t?new Date(t).toLocaleDateString('es-ES',{day:'numeric',month:'short'}):'\u2014'}
function fmtVal(v){const p=S.cfg.program;return p==='sellos'?'+1 sello':p==='puntos'?'+'+v+' puntos':'+'+eur(v)}
function lines(t){return String(t||'').split('\n').map(x=>x.trim()).filter(Boolean)}

/* ---------- navegaci\u00f3n ---------- */
const R={};
function go(tab){if(!TABS.includes(tab))tab=TABS[0];U.tab=tab;
  TABS.forEach(t=>{const e=$('#tab-'+t);if(e)e.hidden=t!==tab});
  $$('#tabs button,#c-nav button').forEach(b=>b.setAttribute('aria-current',b.dataset.tab===tab?'page':'false'));
  try{if(location.hash.slice(1)!==tab)location.hash=tab}catch(e){}
  render();window.scrollTo(0,0)}
function render(){brand();(R[U.tab]||(()=>{}))()}
function brand(){const m=$('#a-mono');if(m){m.innerHTML=monoHTML();$('#a-name').textContent=S.cfg.name}}

/* =====================================================
   P\u00c1GINA DEL CLIENTE
   ===================================================== */
function applyBrand(){const f=S.cfg,r=document.documentElement.style;r.setProperty('--b-c1',f.c1);r.setProperty('--b-c2',f.c2);r.setProperty('--b-fg',f.fg)}
function rCliente(){
  applyBrand();const f=S.cfg;
  $('#c-head').innerHTML='<span class="cp-logo">'+monoHTML()+'</span><h1>'+esc(f.name)+'</h1><p>'+esc(f.tagline)+'</p>';
  const c=cust(U.pcid),main=$('#c-main'),nav=$('#c-nav');let h='';
  if(!c){nav.hidden=true;
    h='<div class="cp-block"><h2>'+esc(f.welcome)+'</h2></div>'+cardHTML({id:'x',name:'Tu nombre',code:'C-0000',stamps:0,points:0,balance:0,visits:0})
     +'<form class="cp-block" id="reg" autocomplete="off"><h3>Guarda tu tarjeta</h3>'
     +'<label class="field"><span>Nombre</span><input type="text" id="r-name" placeholder="Tu nombre"></label>'
     +'<label class="field"><span>Correo</span><input type="email" id="r-email" placeholder="tu@correo.com"></label>'
     +'<label class="field"><span>Cumplea\u00f1os (opcional)</span><input type="date" id="r-bday"></label>'
     +'<label class="field"><span>C\u00f3digo de un amigo o cup\u00f3n (opcional)</span><input type="text" id="r-code" placeholder="'+esc(f.coupon)+'"></label>'
     +'<div id="r-msg"></div><div class="wallet-btns"><button type="button" class="wbtn apple" data-act="wallet-add" data-dev="apple">A\u00f1adir a Apple Wallet</button><button type="button" class="wbtn google" data-act="wallet-add" data-dev="google">Guardar en Google Wallet</button></div>'
     +'<p class="cp-small">'+esc(f.terms)+'</p></form>';
  } else {
    nav.hidden=false;
    if(U.tab==='avisos'){
      const nts=S.notifs.filter(n=>n.cid===c.id).sort((a,b)=>b.t-a.t).slice(0,15);
      h='<h2 class="cp-title">Tus avisos</h2>'+(nts.map(n=>'<div class="cp-notif">'+notifHTML(f.name,n.body,rel(n.t))+'</div>').join('')||'<div class="cp-block"><p>Todav\u00eda no tienes avisos. Te escribiremos cuando sumes un sello o tengas un premio.</p></div>');
    } else if(U.tab==='info'){
      h='<h2 class="cp-title">C\u00f3mo se suma</h2><div class="cp-block"><ul class="cp-list">'+lines(f.rules).map(l=>'<li>'+esc(l)+'</li>').join('')+'</ul><p class="cp-reward">Premio: <b>'+esc(f.reward)+'</b></p></div>'
       +(f.tiersOn?'<h2 class="cp-title">Niveles</h2><div class="cp-block">'+sortedTiers().map(t=>'<div class="cp-row"><span><b>'+esc(t.name)+'</b><small>'+t.visits+' visitas</small></span><span>'+esc(t.perk)+'</span></div>').join('')+'</div>':'')
       +(f.services.length?'<h2 class="cp-title">Servicios y precios</h2><div class="cp-block">'+f.services.map(s=>'<div class="cp-row"><span>'+esc(s.name)+'</span><b>'+eur(s.price)+'</b></div>').join('')+'</div>':'')
       +'<h2 class="cp-title">D\u00f3nde estamos</h2><div class="cp-block"><p><b>'+esc(f.address)+'</b></p><p style="white-space:pre-line">'+esc(f.hours)+'</p><p>Tel\u00e9fono: <b>'+esc(f.phone)+'</b></p></div><p class="cp-small">'+esc(f.terms)+'</p>';
    } else {
      const lv=levelOf(c),nx=nextLevel(c);
      h='<p class="cp-hello">Hola, <b>'+esc(c.name)+'</b></p>'+(rewardReady(c)?'<div class="cp-ready">\u00a1Premio listo! '+esc(f.reward)+'. Ense\u00f1a esta tarjeta en caja.</div>':'')+cardHTML(c)
       +(f.tiersOn?'<div class="cp-block"><p>'+(lv?'Nivel <b>'+esc(lv.name)+'</b> \u00b7 '+esc(lv.perk):'Todav\u00eda no tienes nivel.')+'</p>'+(nx?'<p class="cp-small">Te faltan '+(nx.visits-c.visits)+' visita'+((nx.visits-c.visits)>1?'s':'')+' para ser cliente <b>'+esc(nx.name)+'</b>: '+esc(nx.perk)+'.</p>':'')+'</div>':'')
       +'<div class="cp-block"><h3>Trae a un amigo</h3><p>Comparte tu c\u00f3digo <code>'+esc(c.code)+'</code>. Cuando se apunte con \u00e9l, los dos sum\u00e1is un extra.</p><button class="cb" data-act="copy-code" data-code="'+esc(c.code)+'">Copiar mi c\u00f3digo</button></div>'
       +(c.device?'<p class="cp-small" style="text-align:center">Guardada en '+(c.device==='apple'?'Apple Wallet':'Google Wallet')+'</p>':'<div class="wallet-btns"><button class="wbtn apple" data-act="wallet-save" data-dev="apple">A\u00f1adir a Apple Wallet</button><button class="wbtn google" data-act="wallet-save" data-dev="google">Guardar en Google Wallet</button></div>');
    }
  }
  h+='<div class="cp-demo"><p class="cp-small" style="margin-bottom:12px"><a href="admin.html" style="color:var(--b-c2);font-weight:600">Panel de la barber\u00eda (para el due\u00f1o) \u2192</a></p><label class="field"><span>Modo demo: ver la tarjeta de otro cliente</span><select id="ph-select"><option value="">Cliente nuevo (sin tarjeta)</option>'+S.customers.map(x=>'<option value="'+x.id+'"'+(x.id===U.pcid?' selected':'')+'>'+esc(x.name)+' \u00b7 '+esc(x.code)+'</option>').join('')+'</select></label></div>';
  main.innerHTML=h;
}
function walletAdd(dev){
  const name=($('#r-name').value||'').trim(),email=($('#r-email').value||'').trim(),m=$('#r-msg');
  if(!name||!/.+@.+\..+/.test(email)){m.innerHTML='<div class="msg bad">Escribe tu nombre y un correo v\u00e1lido.</div>';return}
  let c=S.customers.find(x=>x.email.toLowerCase()===email.toLowerCase());
  if(!c){const bd=$('#r-bday').value,code=($('#r-code').value||'').trim();let source='mostrador',ref=null;
    if(code){ref=S.customers.find(x=>x.code.toLowerCase()===code.toLowerCase());if(ref)source='amigo';else if(code.toLowerCase()===S.cfg.coupon.toLowerCase())source='cupon'}
    c=newCustomer({name,email,bday:bd?bd.slice(5):'',source,device:dev});if(ref){bonus(c);bonus(ref)}else if(source==='cupon')bonus(c)}
  U.pcid=c.id;meSet(c.id);S.lastPcid=c.id;save();toast('Tarjeta guardada en '+(dev==='apple'?'Apple Wallet':'Google Wallet'));go('tarjeta')}

/* =====================================================
   PANEL: RESUMEN
   ===================================================== */
function audience(kind){
  const now=Date.now(),mo=new Date().getMonth()+1;
  if(kind==='todos')return S.customers;
  if(kind==='premio')return S.customers.filter(rewardReady);
  if(kind==='cerca')return S.customers.filter(c=>!rewardReady(c)&&pct(c)>=.65);
  if(kind==='inactivos')return S.customers.filter(c=>c.last&&now-c.last>21*DAY);
  if(kind==='cumple')return S.customers.filter(c=>c.bday&&+c.bday.slice(0,2)===mo);
  if(kind==='movil'){const c=cust(S.lastPcid);return c?[c]:[]}
  return []}
function rResumen(){
  const now=Date.now();
  const ready=audience('premio').length,inact=audience('inactivos').length,bday=audience('cumple').length,near=audience('cerca').length;
  const d0=new Date();d0.setHours(0,0,0,0);const A=stats(d0.getTime()-((d0.getDay()+6)%7)*DAY,now+1);
  const card=(n,t,d,btn)=>'<div class="panel"><div class="big" style="font-size:40px">'+n+'</div><b>'+t+'</b><p class="hint">'+d+'</p>'+btn+'</div>';
  const send=(k,aud,label,n)=>'<button class="btn primary sm" style="align-self:flex-start" data-act="res-send" data-k="'+k+'" data-aud="'+aud+'"'+(n?'':' disabled')+'>'+label+'</button>';
  $('#res-cards').innerHTML=
    card(ready,'clientes con el premio listo','Todav\u00eda no lo han canjeado. Un aviso les recuerda que pasen a por \u00e9l.',send('premio','premio','Avisarles del premio',ready))
   +card(inact,'clientes llevan 3 semanas sin venir','Recup\u00e9ralos con un aviso de \u00abte echamos de menos\u00bb.',send('echamos','inactivos','Enviar \u00abte echamos de menos\u00bb',inact))
   +card(bday,'cumplea\u00f1os este mes','Un detalle por su cumplea\u00f1os suele traerlos a la silla.',send('cumple','cumple','Felicitarles',bday))
   +card(near,'clientes cerca del premio','Les falta muy poco. Un empuj\u00f3n y vuelven esta semana.',send('falta','cerca','Avisarles de lo que les falta',near));
  $('#res-kpis').innerHTML='<div class="kpi"><span class="lbl">Clientes</span><b>'+S.customers.length+'</b></div><div class="kpi"><span class="lbl">Nuevos esta semana</span><b>'+A.nuevos.length+'</b></div><div class="kpi"><span class="lbl">Visitas esta semana</span><b>'+A.visits+'</b></div><div class="kpi"><span class="lbl">Premios canjeados</span><b>'+A.premios+'</b></div>';
  const ev=S.events.slice(-8).reverse();
  $('#res-log').innerHTML=ev.map(e=>{const cc=cust(e.cid),mm=team(e.tid);return '<div><span><b>'+esc(cc?cc.name:'?')+'</b> \u00b7 '+(e.type==='reward'?'premio canjeado':esc(e.service||'visita'))+'</span><span>'+esc(mm?mm.name:'\u2014')+' \u00b7 '+rel(e.t)+'</span></div>'}).join('')||'<p class="hint">A\u00fan no hay movimientos.</p>'}

/* =====================================================
   PANEL: TARJETA (todo editable)
   ===================================================== */
function getPath(o,p){return p.split('.').reduce((a,k)=>a==null?a:a[k],o)}
function setPath(o,p,v){const ks=p.split('.');const l=ks.pop();ks.reduce((a,k)=>a[k],o)[l]=v}
function syncForm(){
  $$('[data-cfg]').forEach(el=>{const v=getPath(S.cfg,el.dataset.cfg);
    if(el.type==='radio')el.checked=el.value===v;else if(el.type==='checkbox')el.checked=!!v;else if(document.activeElement!==el)el.value=v??''});
  const cb=$('#f-qr');if(cb&&!S.cfg.qrUrl)cb.placeholder=counterUrl();
  const vs=$('#v-stamps');if(vs)vs.textContent=S.cfg.stamps;
  $$('[data-prog]').forEach(el=>{el.hidden=!el.dataset.prog.split(' ').includes(S.cfg.program)});
  const ru=$('#ref-unit');if(ru)ru.textContent=S.cfg.program==='sellos'?'sellos':S.cfg.program==='puntos'?'puntos':'euros de saldo';
  const tb=$('#tiers-box');if(tb)tb.style.opacity=S.cfg.tiersOn?1:.45;
  const lp=$('#logo-prev');if(lp)lp.innerHTML=S.cfg.logo?'<img alt="" src="'+S.cfg.logo+'">':esc((S.cfg.name||'?').charAt(0).toUpperCase())}
function renderSvc(){const l=$('#svc-list');if(!l)return;
  l.innerHTML=S.cfg.services.map((s,i)=>'<div class="svc-row"><input type="text" data-svc="'+i+'" data-f="name" value="'+esc(s.name)+'" aria-label="Servicio"><input type="number" min="0" step="0.5" data-svc="'+i+'" data-f="price" value="'+esc(s.price)+'" aria-label="Precio en euros"><button class="btn sm danger" data-act="svc-del" data-i="'+i+'">Quitar</button></div>').join('')||'<p class="hint">A\u00f1ade al menos un servicio para poder elegirlo en el esc\u00e1ner.</p>'}
function previewDesign(){const dc=$('#d-card');if(!dc)return;dc.innerHTML=cardHTML(sampleCust());
  $('#d-poster').innerHTML='<span class="eyebrow">Cartel para el mostrador</span><h3>Guarda tu tarjeta de '+esc(S.cfg.name)+'</h3><div class="qr">'+qrSvg(counterUrl())+'</div><small>Escanea, escribe tu nombre y a\u00f1\u00e1dela a Apple Wallet o Google Wallet. '+esc(S.cfg.tagline)+'.</small><small>Este QR abre la p\u00e1gina del cliente. El QR de cada tarjeta lo lee el esc\u00e1ner del barbero.</small>'}
function rTarjeta(){syncForm();renderSvc();previewDesign()}
function renderTeam(){const tl=$('#team-list');if(!tl)return;tl.innerHTML=S.team.map(m=>'<div class="team-row"><input type="text" data-team="'+m.id+'" data-f="name" value="'+esc(m.name)+'" aria-label="Nombre"><input type="text" data-team="'+m.id+'" data-f="pin" value="'+esc(m.pin)+'" maxlength="4" inputmode="numeric" aria-label="PIN de 4 cifras"><button class="btn sm danger" data-act="team-del" data-id="'+m.id+'">Quitar</button></div>').join('')||'<p class="hint">A\u00f1ade a alguien para poder entrar al esc\u00e1ner.</p>'}
function rEquipo(){renderTeam()}

/* =====================================================
   PANEL: ESC\u00c1NER
   ===================================================== */
function rEscaner(){
  const box=$('#scanner'),m=team(U.tid);
  if(!m){box.innerHTML='<div class="panel"><h3>Entrar al esc\u00e1ner</h3><p class="hint">Cada barbero entra con su PIN de 4 cifras. Cada servicio queda apuntado a su nombre.</p><input type="text" id="sc-pin" class="pin" inputmode="numeric" maxlength="4" placeholder="\u00b7\u00b7\u00b7\u00b7" autocomplete="off" aria-label="PIN"><div id="sc-pinmsg"></div><p class="hint">PINs de la demo: '+S.team.map(x=>esc(x.name)+' <code>'+esc(x.pin)+'</code>').join(' \u00b7 ')+'</p></div>';return}
  const c=cust(U.scid),f=S.cfg;let h='';
  h+='<div class="panel"><div class="row" style="justify-content:space-between"><b>Hola, '+esc(m.name)+'</b><button class="btn sm" data-act="sc-logout">Salir</button></div>'
   +'<label class="check"><input type="checkbox" id="sc-off" '+(U.offline?'checked':'')+'>Simular que el m\u00f3vil no tiene conexi\u00f3n</label>'
   +'<label class="check"><input type="checkbox" id="sc-ign" '+(U.ignoreWait?'checked':'')+'>Ignorar la espera entre sellos (solo para la demo)</label>';
  if(U.queue.length)h+='<div class="msg warn">'+U.queue.length+' movimiento(s) pendiente(s) de enviar. '+(U.offline?'Se enviar\u00e1n cuando vuelva la conexi\u00f3n.':'<button class="btn sm" data-act="sc-flush">Enviar ahora</button>')+'</div>';
  h+='</div><div class="panel"><h3>Escanear tarjeta</h3><div class="row"><input type="search" id="sc-search" placeholder="C\u00f3digo o nombre del cliente" style="flex:1" value="'+esc(U.ssearch)+'"><button class="btn" data-act="sc-random">Cliente al azar</button></div><div class="list" id="sc-list"></div><p class="hint">En la barber\u00eda el m\u00f3vil lee el QR de la tarjeta. Aqu\u00ed se simula eligiendo al cliente.</p></div>';
  if(c){const rr=rewardReady(c),lv=levelOf(c);
    const sv=f.services.length?'<div class="field"><span>Servicio</span><div class="chips">'+f.services.map((s,i)=>'<button class="btn sm" data-act="sc-svc" data-i="'+i+'" aria-pressed="'+(i===U.svc)+'">'+esc(s.name)+' \u00b7 '+eur(s.price)+'</button>').join('')+'</div></div>':'';
    h+='<div class="panel"><div class="cust-card"><div class="row" style="justify-content:space-between"><div><div class="big">'+esc(c.name)+'</div><span class="hint">'+esc(c.code)+(lv?' \u00b7 '+esc(lv.name):'')+' \u00b7 '+c.visits+' visitas</span></div><div class="big">'+esc(shortProgress(c))+'</div></div><div class="bar"><i style="width:'+pct(c)*100+'%"></i></div>'
     +(rr?'<div class="msg ok">Premio listo: '+esc(f.reward)+'</div><button class="btn primary" data-act="sc-redeem">Canjear premio</button>':'')+'</div>'+sv;
    if(f.program==='sellos')h+='<button class="btn primary" data-act="sc-visit">Poner sello</button>';
    else h+='<label class="field"><span>Importe del servicio (\u20ac)</span><input type="number" id="sc-amt" min="0" step="0.01" inputmode="decimal" placeholder="0,00" value="'+esc(U.amt)+'"></label><button class="btn primary" data-act="sc-visit">'+(f.program==='puntos'?'Sumar puntos':'Sumar cashback')+'</button>';
    if(U.msg)h+='<div class="msg '+U.msg.type+'">'+esc(U.msg.text)+'</div>';
    h+='</div>'}
  const ev=S.events.slice(-8).reverse();
  h+='<div class="panel"><h3>\u00daltimos movimientos</h3><div class="log">'+(ev.map(e=>{const cc=cust(e.cid),mm=team(e.tid);return '<div><span><b>'+esc(cc?cc.name:'?')+'</b> \u00b7 '+(e.type==='reward'?'premio canjeado':esc(e.service||fmtVal(e.value)))+'</span><span>'+esc(mm?mm.name:'\u2014')+' \u00b7 '+rel(e.t)+'</span></div>'}).join('')||'<p class="hint">A\u00fan no hay movimientos.</p>')+'</div></div>';
  box.innerHTML=h;drawScList()}
function drawScList(){const q=U.ssearch.trim().toLowerCase();const l=$('#sc-list');if(!l)return;
  const arr=S.customers.filter(c=>!q||c.name.toLowerCase().includes(q)||c.code.toLowerCase().includes(q)).slice(0,40);
  l.innerHTML=arr.map(c=>'<button data-act="sc-pick" data-id="'+c.id+'" aria-pressed="'+(c.id===U.scid)+'"><span><b>'+esc(c.name)+'</b> <code>'+esc(c.code)+'</code></span><small>'+esc(shortProgress(c))+(rewardReady(c)?' \u00b7 premio':'')+'</small></button>').join('')||'<p class="hint" style="padding:12px">Ning\u00fan cliente coincide.</p>'}
function scVisit(){
  const c=cust(U.scid),f=S.cfg;if(!c)return;const sv=f.services[U.svc]||null;let amount=0;
  if(f.program==='sellos')amount=sv?sv.price:0;
  else{amount=parseFloat(String($('#sc-amt').value).replace(',','.'));if(!(amount>0)){U.msg={type:'bad',text:'Elige un servicio o escribe el importe.'};return rEscaner()}}
  const job={cid:c.id,tid:U.tid,amount,service:sv?sv.name:'',ts:Date.now()};
  if(U.offline){U.queue.push(job);U.msg={type:'warn',text:'Sin conexi\u00f3n. Guardado en el m\u00f3vil de la barber\u00eda, se enviar\u00e1 al volver la conexi\u00f3n.'};return rEscaner()}
  const r=visit(c,{tid:U.tid,amount,service:job.service,force:U.ignoreWait});U.msg={type:r.ok?'ok':'bad',text:r.msg+(r.ok&&r.ready?' Premio listo.':'')};save();rEscaner()}
function flushQueue(){let n=0;U.queue.forEach(q=>{const c=cust(q.cid);if(c){const r=visit(c,{ts:q.ts,tid:q.tid,amount:q.amount,service:q.service,force:true});if(r.ok)n++}});U.queue=[];save();toast(n+' movimiento(s) enviado(s)');rEscaner()}

/* =====================================================
   PANEL: AVISOS
   ===================================================== */
function rAvisos(){
  const s=sampleCust();
  $('#tpl-list').innerHTML=S.tpl.map(t=>'<div class="panel"><div class="tpl"><div class="tpl-main"><div class="row" style="justify-content:space-between"><h3>'+esc(t.label)+'</h3>'+(t.auto?'<span class="tag ok">Autom\u00e1tico</span>':'<span class="tag">Manual</span>')+'</div><p class="hint">'+esc(t.when)+'</p>'
   +(t.custom?'<label class="field"><span>Nombre del aviso</span><input type="text" data-tpl-label="'+t.k+'" value="'+esc(t.label)+'"></label>':'')
   +'<label class="field"><span>Texto del aviso</span><textarea data-tpl-body="'+t.k+'" maxlength="180">'+esc(t.body)+'</textarea></label>'
   +(['sello','premio','nivel'].includes(t.k)?'<label class="check"><input type="checkbox" data-tpl-auto="'+t.k+'" '+(t.auto?'checked':'')+'>Enviar solo cuando ocurra</label>':'')
   +'<div class="row"><select data-aud="'+t.k+'" style="max-width:270px"><option value="todos">A todos los clientes</option><option value="cerca">A los que est\u00e1n cerca del premio</option><option value="premio">A los que tienen el premio listo</option><option value="inactivos">A los que llevan 3 semanas sin venir</option><option value="cumple">A los que cumplen a\u00f1os este mes</option><option value="movil">Solo al cliente que tiene abierta la tarjeta (demo)</option></select><button class="btn primary" data-act="tpl-send" data-k="'+t.k+'">Enviar</button>'+(t.custom?'<button class="btn danger sm" data-act="tpl-del" data-k="'+t.k+'">Borrar</button>':'')+'</div></div>'
   +'<div><span class="lbl">As\u00ed lo ver\u00e1 el cliente</span><div class="notif" style="margin-top:6px" data-prev="'+t.k+'">'+notifHTML(S.cfg.name,fill(t.body,s),'ahora')+'</div></div></div></div>').join('')}
function tplSend(k){const t=S.tpl.find(x=>x.k===k),sel=$('[data-aud="'+k+'"]').value,list=audience(sel);
  if(!list.length){toast(sel==='movil'?'Primero abre una tarjeta en la p\u00e1gina del cliente.':'Ning\u00fan cliente cumple esa condici\u00f3n ahora mismo.');return}
  list.forEach(c=>pushNotif(c,k));save();toast('\u00ab'+t.label+'\u00bb enviado a '+list.length+' cliente'+(list.length>1?'s':''))}

/* =====================================================
   PANEL: INFORME
   ===================================================== */
function weekRange(){const n=new Date();n.setHours(0,0,0,0);const dow=(n.getDay()+6)%7;const mon=n.getTime()-dow*DAY;
  return U.week==='last'?{s:mon-7*DAY,e:mon,ps:mon-14*DAY,pe:mon-7*DAY}:{s:mon,e:Date.now()+1,ps:mon-7*DAY,pe:mon}}
function stats(s,e){const ev=S.events.filter(x=>x.t>=s&&x.t<e),vs=ev.filter(x=>x.type==='visit');
  return {nuevos:S.customers.filter(c=>c.created>=s&&c.created<e),act:vs.reduce((a,x)=>a+x.value,0),visits:vs.length,premios:ev.filter(x=>x.type==='reward').length,
    vuelven:new Set(vs.filter(x=>{const c=cust(x.cid);return c&&c.created<s}).map(x=>x.cid)).size,ev,vs}}
function dl(cur,prev,money){const d=cur-prev;const txt=money?eur(Math.abs(d)):Math.abs(Math.round(d*100)/100);return '<span class="delta '+(d>=0?'up':'down')+'">'+(d>=0?'\u25b2':'\u25bc')+' '+txt+' vs. semana anterior</span>'}
function rInforme(){
  $$('input[name=week]').forEach(r=>r.checked=r.value===U.week);
  const {s,e,ps,pe}=weekRange(),A=stats(s,e),B=stats(ps,pe),f=S.cfg,money=f.program==='cashback';
  const actLbl=f.program==='sellos'?'Sellos':f.program==='puntos'?'Puntos':'Cashback',fa=v=>money?eur(v):Math.round(v);
  const now=Date.now();
  const byP=S.team.map(m=>{const ev=A.ev.filter(x=>x.tid===m.id);const vs=ev.filter(x=>x.type==='visit');return {n:m.name,v:vs.length,a:vs.reduce((a,x)=>a+x.value,0),i:vs.reduce((a,x)=>a+x.amount,0),p:ev.filter(x=>x.type==='reward').length}}).sort((a,b)=>b.v-a.v);
  const sg={};A.vs.forEach(x=>{const k=x.service||'Sin servicio';sg[k]=sg[k]||{n:0,i:0};sg[k].n++;sg[k].i+=x.amount});
  const svc=Object.entries(sg).sort((a,b)=>b[1].n-a[1].n),tot=A.vs.reduce((a,x)=>a+x.amount,0);
  const nts=S.notifs.filter(n=>n.t>=s&&n.t<e&&n.k!=='sello'),grp={};
  nts.forEach(n=>{(grp[n.label]=grp[n.label]||[]).push(n)});
  const vis=S.events.filter(x=>x.type==='visit');
  const avisos=Object.entries(grp).map(([l,arr])=>{const back=new Set(arr.filter(n=>vis.some(v=>v.cid===n.cid&&v.t>n.t&&v.t<=n.t+7*DAY)).map(n=>n.cid)).size;return {l,n:new Set(arr.map(n=>n.cid)).size,back}});
  const src={mostrador:0,amigo:0,cupon:0};A.nuevos.forEach(c=>src[c.source]=(src[c.source]||0)+1);
  const cerca=audience('cerca').length,inact=audience('inactivos').length;
  const fm=t=>new Date(t).toLocaleDateString('es-ES',{day:'numeric',month:'short'});
  $('#report').innerHTML='<div class="mail"><div class="mail-head"><span><b>De:</b> Tarjeta de fidelidad</span><span><b>Para:</b> propietario de '+esc(f.name)+' \u00b7 lunes, 9:00</span><span><b>Asunto:</b> As\u00ed ha ido tu programa de fidelidad ('+fm(s)+' \u2013 '+fm(e-1)+')</span></div>'
   +'<div class="mail-body"><div class="mail-title"><h3>'+esc(f.name)+'</h3><span class="eyebrow">Informe semanal \u00b7 '+fm(s)+' \u2013 '+fm(Math.min(e-1,now))+'</span></div>'
   +'<div class="kpis"><div class="kpi"><span class="lbl">Clientes nuevos</span><b>'+A.nuevos.length+'</b>'+dl(A.nuevos.length,B.nuevos.length)+'</div><div class="kpi"><span class="lbl">Visitas</span><b>'+A.visits+'</b>'+dl(A.visits,B.visits)+'</div><div class="kpi"><span class="lbl">Premios canjeados</span><b>'+A.premios+'</b>'+dl(A.premios,B.premios)+'</div><div class="kpi"><span class="lbl">Clientes que vuelven</span><b>'+A.vuelven+'</b>'+dl(A.vuelven,B.vuelven)+'</div></div>'
   +'<div><h3 style="font-size:15px;margin-bottom:8px">Servicios de la semana</h3><div class="tbl"><table><thead><tr><th>Servicio</th><th class="n">Veces</th><th class="n">Ingresos</th></tr></thead><tbody>'+(svc.map(([k,v])=>'<tr><td>'+esc(k)+'</td><td class="n">'+v.n+'</td><td class="n">'+eur(v.i)+'</td></tr>').join('')||'<tr><td colspan="3" class="hint">Sin servicios esta semana.</td></tr>')+(svc.length?'<tr><td><b>Total</b></td><td class="n"><b>'+A.visits+'</b></td><td class="n"><b>'+eur(tot)+'</b></td></tr>':'')+'</tbody></table></div></div>'
   +'<div><h3 style="font-size:15px;margin-bottom:8px">Por barbero</h3><div class="tbl"><table><thead><tr><th>Persona</th><th class="n">Visitas</th><th class="n">'+actLbl+'</th><th class="n">Premios</th></tr></thead><tbody>'+(byP.map(r=>'<tr><td>'+esc(r.n)+'</td><td class="n">'+r.v+'</td><td class="n">'+fa(r.a)+'</td><td class="n">'+r.p+'</td></tr>').join('')||'<tr><td colspan="4" class="hint">Sin equipo.</td></tr>')+'</tbody></table></div></div>'
   +'<div><h3 style="font-size:15px;margin-bottom:8px">Avisos en la tarjeta</h3><div class="tbl"><table><thead><tr><th>Aviso</th><th class="n">Clientes</th><th class="n">Han vuelto</th></tr></thead><tbody>'+(avisos.map(r=>'<tr><td>'+esc(r.l)+'</td><td class="n">'+r.n+'</td><td class="n">'+r.back+'</td></tr>').join('')||'<tr><td colspan="3" class="hint">No sali\u00f3 ning\u00fan aviso esta semana.</td></tr>')+'</tbody></table></div></div>'
   +'<div><h3 style="font-size:15px;margin-bottom:8px">De d\u00f3nde vienen los clientes nuevos</h3><p>QR del mostrador: <b>'+src.mostrador+'</b> \u00b7 Tra\u00eddos por un amigo: <b>'+src.amigo+'</b> \u00b7 Con cup\u00f3n: <b>'+src.cupon+'</b></p></div>'
   +'<div><h3 style="font-size:15px;margin-bottom:8px">Oportunidades</h3><div class="opp"><div><b>'+cerca+'</b>clientes est\u00e1n cerca del premio.</div><div><b>'+inact+'</b>clientes llevan m\u00e1s de 3 semanas sin venir.</div></div></div>'
   +'<p class="note">Ejemplo con los datos de esta demo.</p></div></div>';
  if(!S.props.length)genProps();
  $('#props').innerHTML='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px">'+S.props.map((p,i)=>'<div class="prop"><div class="row" style="justify-content:space-between"><span class="tag">'+esc(p.type)+'</span><span class="eyebrow">Propuesta '+(i+1)+'</span></div><h3 style="font-size:16px">'+esc(p.title)+'</h3><p class="hint"><b>A qui\u00e9n:</b> '+esc(p.who)+'<br><b>Cu\u00e1ndo:</b> '+esc(p.when)+'</p><textarea data-prop="'+i+'" maxlength="180">'+esc(p.text)+'</textarea><button class="btn sm" style="align-self:flex-start" data-act="prop-prep" data-i="'+i+'">Preparar aviso</button></div>').join('')+'</div><div class="row" style="margin-top:12px"><button class="btn sm" data-act="prop-regen">Generar de nuevo con los datos de hoy</button></div>'}
function genProps(){
  const f=S.cfg,now=Date.now(),inact=audience('inactivos').length;
  const nm=new Date(now+10*DAY).getMonth();
  const ev=['Reyes y rebajas','San Valent\u00edn','el D\u00eda del Padre','Semana Santa','las comuniones','el verano','las vacaciones','la vuelta al cole','el oto\u00f1o','Halloween','el Black Friday','las fiestas de Navidad'][nm];
  const mes=new Date(now+10*DAY).toLocaleDateString('es-ES',{month:'long'});
  S.props=[
   {type:'Aviso al m\u00f3vil',title:'Recupera a los clientes que no vuelven',who:inact+' clientes que llevan m\u00e1s de 3 semanas sin venir',when:'La primera semana de '+mes,text:'Ya toca repasar ese corte, {nombre} \u2702\ufe0f En '+f.name+' te esperamos: tu tarjeta sigue sumando. {progreso}'},
   {type:'Aviso',title:'Llega bien a '+ev,who:'Todos los clientes con la tarjeta',when:'Una semana antes',text:'Con '+ev+' llegan los planes. Reserva tu corte en '+f.name+' y llega perfecto. {progreso}'},
   {type:'Cup\u00f3n',title:'Reparte el cup\u00f3n '+f.coupon,who:'Gente que a\u00fan no tiene la tarjeta',when:'Todo el mes, en el local y en redes',text:'Escanea el QR de '+f.name+', guarda tu tarjeta y usa el c\u00f3digo '+f.coupon+' para empezar con un extra.'},
   {type:'En el local',title:'Que los clientes traigan amigos',who:'Clientes que ya han canjeado un premio',when:'Fines de semana',text:'Trae a un amigo con tu c\u00f3digo {codigo}: cuando se apunte, los dos sum\u00e1is un extra \ud83c\udf81'}]}
function propPrep(i){const p=S.props[i];S.tpl.push({k:'custom-'+uid(),label:p.title,when:p.who,auto:false,custom:true,body:p.text});save();go('avisos');toast('Aviso preparado al final de la lista')}

/* =====================================================
   PANEL: CLIENTES
   ===================================================== */
function unitStep(){const p=S.cfg.program;return p==='sellos'?1:p==='puntos'?10:1}
function drawDetail(){
  const box=$('#cl-detail');if(!box)return;const c=cust(U.ccid);
  if(!c){box.innerHTML='';return}
  const f=S.cfg,key=f.program==='sellos'?'stamps':f.program==='puntos'?'points':'balance',lab=f.program==='sellos'?'Sellos':f.program==='puntos'?'Puntos':'Saldo (\u20ac)';
  const evs=S.events.filter(e=>e.cid===c.id).sort((a,b)=>b.t-a.t).slice(0,10),nts=S.notifs.filter(n=>n.cid===c.id).sort((a,b)=>b.t-a.t).slice(0,5);
  const lv=levelOf(c);
  box.innerHTML='<div class="panel"><div class="row" style="justify-content:space-between"><h3>'+esc(c.name)+' <code>'+esc(c.code)+'</code></h3><button class="btn sm" data-act="cli-close">Cerrar</button></div>'
   +'<div class="cols" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))"><div><div id="cd-card">'+cardHTML(c)+'</div></div><div class="stack">'
   +'<div class="grid2"><label class="field"><span>Nombre</span><input type="text" data-cf="name" value="'+esc(c.name)+'"></label><label class="field"><span>Correo</span><input type="email" data-cf="email" value="'+esc(c.email)+'"></label>'
   +'<label class="field"><span>Cumplea\u00f1os</span><input type="date" data-cf="bday" value="'+(c.bday?'2000-'+esc(c.bday):'')+'"></label><label class="field"><span>Visitas totales</span><input type="number" min="0" data-cf="visits" value="'+c.visits+'"></label>'
   +'<label class="field"><span>'+lab+'</span><input type="number" min="0" step="'+(key==='balance'?'0.5':'1')+'" data-cf="'+key+'" value="'+c[key]+'"></label><label class="field"><span>Premios canjeados</span><input type="number" min="0" data-cf="rewards" value="'+c.rewards+'"></label></div>'
   +'<p class="hint">Nivel: <b>'+esc(lv?lv.name:'ninguno')+'</b> \u00b7 Origen: '+esc(c.source)+' \u00b7 \u00daltima visita: '+dshort(c.last)+' \u00b7 Gastado: '+eur(c.spend)+'</p>'
   +'<div class="row"><button class="btn" data-act="cli-adj" data-d="-1">\u2212 '+(key==='points'?'10 puntos':key==='balance'?'1 \u20ac':'1 sello')+'</button><button class="btn" data-act="cli-adj" data-d="1">+ '+(key==='points'?'10 puntos':key==='balance'?'1 \u20ac':'1 sello')+'</button>'+(rewardReady(c)?'<button class="btn primary" data-act="cli-redeem">Canjear premio</button>':'')+'</div>'
   +'<div class="row"><select id="cd-tpl" style="max-width:240px">'+S.tpl.map(t=>'<option value="'+t.k+'">'+esc(t.label)+'</option>').join('')+'</select><button class="btn" data-act="cli-send">Enviar este aviso</button><button class="btn danger" data-act="cli-del" data-id="'+c.id+'">Borrar cliente</button></div>'
   +'<p class="note">Los ajustes manuales no cuentan en el informe.</p></div></div>'
   +'<div class="cols" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))"><div><h3 style="font-size:15px;margin-bottom:6px">Historial</h3><div class="log">'+(evs.map(e=>{const mm=team(e.tid);return '<div><span>'+(e.type==='reward'?'Premio canjeado':esc(e.service||'Visita'))+'</span><span>'+esc(mm?mm.name:'\u2014')+' \u00b7 '+dshort(e.t)+'</span></div>'}).join('')||'<p class="hint">Sin movimientos.</p>')+'</div></div>'
   +'<div><h3 style="font-size:15px;margin-bottom:6px">Avisos recibidos</h3><div class="log">'+(nts.map(n=>'<div><span>'+esc(n.label)+'</span><span>'+rel(n.t)+'</span></div>').join('')||'<p class="hint">Ninguno.</p>')+'</div></div></div></div>'}
function rClientes(){drawDetail();drawClientes();$('#b-reset').textContent=U.confirm==='reset'?'\u00bfSeguro? Pulsa de nuevo':'Restablecer datos de ejemplo';$('#b-clear').textContent=U.confirm==='clear'?'\u00bfSeguro? Pulsa de nuevo':'Empezar con todo vac\u00edo'}
function drawClientes(){const q=U.csearch.trim().toLowerCase();
  const arr=S.customers.filter(c=>!q||(c.name+' '+c.email+' '+c.code).toLowerCase().includes(q)).sort((a,b)=>b.created-a.created);
  $('#cl-count').textContent=arr.length+' de '+S.customers.length+' clientes';
  const so={mostrador:'QR del mostrador',amigo:'Amigo',cupon:'Cup\u00f3n'};
  $('#cl-body').innerHTML=arr.slice(0,80).map(c=>'<tr><td><b>'+esc(c.name)+'</b><br><span class="hint">'+esc(c.email||'sin correo')+'</span></td><td><code>'+esc(c.code)+'</code></td><td>'+esc(shortProgress(c))+(rewardReady(c)?' <span class="tag ok">Premio</span>':'')+'</td><td class="n">'+c.visits+'</td><td>'+dshort(c.last)+'</td><td>'+esc(so[c.source]||c.source)+'</td><td><button class="btn sm" data-act="cli-open" data-id="'+c.id+'">Ver y editar</button></td></tr>').join('')||'<tr><td colspan="7" class="hint">Todav\u00eda no hay clientes. A\u00f1ade uno aqu\u00ed abajo o reg\u00edstralo desde la p\u00e1gina del cliente.</td></tr>'}

Object.assign(R,PAGE==='admin'?{resumen:rResumen,tarjeta:rTarjeta,escaner:rEscaner,avisos:rAvisos,informe:rInforme,clientes:rClientes,equipo:rEquipo}:{tarjeta:rCliente,avisos:rCliente,info:rCliente});

/* ---------- eventos ---------- */
document.addEventListener('click',ev=>{
  const b=ev.target.closest('[data-act]');if(!b||b.tagName==='INPUT')return;const a=b.dataset.act;
  if(a==='go'){ev.preventDefault();return go(b.dataset.tab)}
  if(a==='logo-clear'){S.cfg.logo='';save();return rTarjeta()}
  if(a==='team-add'){S.team.push({id:uid(),name:'Nuevo barbero',pin:String(1000+Math.floor(Math.random()*9000))});save();return renderTeam()}
  if(a==='team-del'){S.team=S.team.filter(m=>m.id!==b.dataset.id);if(U.tid===b.dataset.id)U.tid=null;save();return renderTeam()}
  if(a==='svc-add'){S.cfg.services.push({name:'Nuevo servicio',price:10});save();renderSvc();return}
  if(a==='svc-del'){S.cfg.services.splice(+b.dataset.i,1);U.svc=0;save();return renderSvc()}
  if(a==='wallet-add')return walletAdd(b.dataset.dev);
  if(a==='wallet-save'){const c=cust(U.pcid);if(c){c.device=b.dataset.dev;save();toast('Tarjeta guardada en '+(c.device==='apple'?'Apple Wallet':'Google Wallet'));rCliente()}return}
  if(a==='copy-code'){const code=b.dataset.code;try{navigator.clipboard.writeText(code).then(()=>toast('C\u00f3digo copiado: '+code),()=>toast('Tu c\u00f3digo es '+code))}catch(e){toast('Tu c\u00f3digo es '+code)}return}
  if(a==='sc-logout'){U.tid=null;U.scid=null;U.msg=null;return rEscaner()}
  if(a==='sc-pick'){U.scid=b.dataset.id;U.msg=null;const sv=S.cfg.services[U.svc];U.amt=sv?String(sv.price):'';return rEscaner()}
  if(a==='sc-random'){if(!S.customers.length)return;U.scid=S.customers[Math.floor(Math.random()*S.customers.length)].id;U.msg=null;return rEscaner()}
  if(a==='sc-svc'){U.svc=+b.dataset.i;const sv=S.cfg.services[U.svc];U.amt=sv?String(sv.price):'';return rEscaner()}
  if(a==='sc-visit')return scVisit();
  if(a==='sc-redeem'){const c=cust(U.scid);if(c){redeem(c,{tid:U.tid});U.msg={type:'ok',text:'Premio canjeado. '+progressText(c)};save();rEscaner()}return}
  if(a==='sc-flush')return flushQueue();
  if(a==='tpl-send')return tplSend(b.dataset.k);
  if(a==='res-send'){const t=S.tpl.find(x=>x.k===b.dataset.k),list=audience(b.dataset.aud);list.forEach(c=>pushNotif(c,b.dataset.k));save();toast('\u00ab'+t.label+'\u00bb enviado a '+list.length+' cliente'+(list.length>1?'s':''));return rResumen()}
  if(a==='tpl-new'){S.tpl.push({k:'custom-'+uid(),label:'Aviso propio',when:'Cuando t\u00fa quieras',auto:false,custom:true,body:'Hola {nombre}, tenemos novedades en {negocio} \ud83c\udf89'});save();rAvisos();return window.scrollTo(0,document.body.scrollHeight)}
  if(a==='tpl-del'){S.tpl=S.tpl.filter(t=>t.k!==b.dataset.k);save();return rAvisos()}
  if(a==='prop-prep')return propPrep(+b.dataset.i);
  if(a==='prop-regen'){genProps();save();return rInforme()}
  if(a==='cli-add'){const n=$('#cl-name').value.trim();if(!n)return toast('Escribe el nombre del cliente.');newCustomer({name:n,email:$('#cl-email').value.trim()});$('#cl-name').value='';$('#cl-email').value='';save();drawClientes();return toast('Cliente a\u00f1adido')}
  if(a==='cli-open'){U.ccid=b.dataset.id;drawDetail();const d=$('#cl-detail');if(d)d.scrollIntoView({block:'start'});return}
  if(a==='cli-close'){U.ccid=null;return drawDetail()}
  if(a==='cli-adj'){const c=cust(U.ccid);if(!c)return;const f=S.cfg,d=+b.dataset.d;
    if(f.program==='sellos')c.stamps=Math.max(0,c.stamps+d);else if(f.program==='puntos')c.points=Math.max(0,c.points+d*10);else c.balance=Math.max(0,Math.round((c.balance+d)*100)/100);
    save();drawDetail();return drawClientes()}
  if(a==='cli-redeem'){const c=cust(U.ccid);if(c){redeem(c,{tid:null});save();toast('Premio canjeado');drawDetail();drawClientes()}return}
  if(a==='cli-send'){const c=cust(U.ccid);if(c){const k=$('#cd-tpl').value;pushNotif(c,k);save();toast('Aviso enviado a '+c.name);drawDetail()}return}
  if(a==='cli-del'){if(U.ccid===b.dataset.id){U.ccid=null;drawDetail()}S.customers=S.customers.filter(c=>c.id!==b.dataset.id);S.events=S.events.filter(e=>e.cid!==b.dataset.id);S.notifs=S.notifs.filter(n=>n.cid!==b.dataset.id);if(S.lastPcid===b.dataset.id)S.lastPcid=null;if(U.scid===b.dataset.id)U.scid=null;save();return drawClientes()}
  if(a==='reset-demo'||a==='clear-all'){const m=a==='reset-demo'?'reset':'clear';
    if(U.confirm!==m){U.confirm=m;return rClientes()}
    U.confirm=null;const keep={cfg:S.cfg,team:S.team,tpl:S.tpl};
    if(m==='reset')seedData(keep);else{S={v:1,epoch:uid(),cfg:keep.cfg,seq:0,customers:[],events:[],notifs:[],tpl:keep.tpl,props:[],lastPcid:null,team:keep.team,at:{},del:{}}}
    B={c:{},s:{},m:''};save(true);
    U.scid=null;U.queue=[];toast(m==='reset'?'Datos de ejemplo restablecidos':'Todo vac\u00edo. Ya puedes empezar.');return rClientes()}
});
document.addEventListener('input',ev=>{
  const el=ev.target;
  if(el.dataset.cfg){if(el.type==='radio'&&!el.checked)return;
    const v=el.type==='checkbox'?el.checked:(el.type==='number'||el.type==='range')?(el.value===''?0:Number(el.value)):el.value;
    setPath(S.cfg,el.dataset.cfg,v);save();
    if(['program','tiersOn','stamps'].includes(el.dataset.cfg))syncForm();previewDesign();brand();return}
  if(el.dataset.cf){const c=cust(U.ccid);if(!c)return;const k=el.dataset.cf;
    if(['stamps','points','balance','visits','rewards'].includes(k))c[k]=Math.max(0,Number(el.value)||0);
    else if(k==='bday')c.bday=el.value?el.value.slice(5):'';else c[k]=el.value;
    save();const cc=$('#cd-card');if(cc)cc.innerHTML=cardHTML(c);drawClientes();return}
  if(el.dataset.svc!==undefined){const s=S.cfg.services[+el.dataset.svc];if(s){s[el.dataset.f]=el.dataset.f==='price'?(Number(el.value)||0):el.value;save()}return}
  if(el.dataset.team){const m=team(el.dataset.team);if(m){m[el.dataset.f]=el.dataset.f==='pin'?el.value.replace(/\D/g,''):el.value;save()}return}
  if(el.id==='sc-pin'){const v=el.value.replace(/\D/g,'');el.value=v;if(v.length===4){const m=S.team.find(x=>x.pin===v);if(m){U.tid=m.id;rEscaner()}else{$('#sc-pinmsg').innerHTML='<div class="msg bad">PIN incorrecto.</div>';el.value=''}}return}
  if(el.id==='sc-amt'){U.amt=el.value;return}
  if(el.id==='sc-search'){U.ssearch=el.value;return drawScList()}
  if(el.id==='cl-search'){U.csearch=el.value;return drawClientes()}
  if(el.dataset.tplBody){const t=S.tpl.find(x=>x.k===el.dataset.tplBody);t.body=el.value;save();const p=$('[data-prev="'+t.k+'"]');if(p)p.innerHTML=notifHTML(S.cfg.name,fill(t.body,sampleCust()),'ahora');return}
  if(el.dataset.tplLabel){const t=S.tpl.find(x=>x.k===el.dataset.tplLabel);t.label=el.value;save();return}
  if(el.dataset.prop!==undefined){S.props[+el.dataset.prop].text=el.value;save();return}
});
document.addEventListener('change',ev=>{
  const el=ev.target;
  if(el.id==='ph-select'){U.pcid=el.value||null;meSet(U.pcid);S.lastPcid=U.pcid;save();return go('tarjeta')}
  if(el.id==='sc-off'){U.offline=el.checked;if(!U.offline&&U.queue.length)return flushQueue();return rEscaner()}
  if(el.id==='sc-ign'){U.ignoreWait=el.checked;return}
  if(el.dataset.tplAuto){const t=S.tpl.find(x=>x.k===el.dataset.tplAuto);t.auto=el.checked;save();return rAvisos()}
  if(el.name==='week'&&el.checked){U.week=el.value;return rInforme()}
  if(el.id==='f-logo'&&el.files[0]){const fr=new FileReader();fr.onload=()=>{const im=new Image();im.onload=()=>{const m=192,k=Math.min(1,m/Math.max(im.width,im.height)),cv=document.createElement('canvas');cv.width=Math.round(im.width*k);cv.height=Math.round(im.height*k);cv.getContext('2d').drawImage(im,0,0,cv.width,cv.height);S.cfg.logo=cv.toDataURL('image/png');save();rTarjeta();brand()};im.src=fr.result};fr.readAsDataURL(el.files[0])}
});
window.addEventListener('hashchange',()=>{const t=location.hash.slice(1);if(TABS.includes(t)&&t!==U.tab)go(t)});
window.addEventListener('storage',e=>{if(e.key===KEY&&MODE==='local'){const o=load();if(o){S=o;render()}}});

/* ---------- arranque ---------- */
(async()=>{
  S=load();
  try{const ac=new AbortController(),to=setTimeout(()=>ac.abort(),6000);
    const r=await fetch(API+'?t='+Date.now(),{cache:'no-store',signal:ac.signal});clearTimeout(to);
    const j=await r.json();
    if(r.ok&&typeof j.ver==='number'){MODE='cloud';
      if(j.state){S=j.state;VER=j.ver;cache()}
      else{if(!S)seedData();S.epoch=S.epoch||uid();B={c:{},s:{},m:''};save(true)}}
  }catch(e){}
  if(!S)seedData();
  if(!S.epoch)S.epoch=uid();
  if(MODE==='cloud'&&VER)B=snapshot();
  if(PAGE==='cliente'){const m=meGet();if(m&&cust(m))U.pcid=m}
  const chip=$('.demo-chip');if(chip)chip.textContent=MODE==='cloud'?'Datos en la nube \u00b7 compartidos':'Datos solo en este navegador';
  const h=(location.hash||'').slice(1);
  go(TABS.includes(h)?h:TABS[0]);
  setInterval(poll,4000);
})();
})();
