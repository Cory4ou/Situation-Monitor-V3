'use strict';
const $=id=>document.getElementById(id);
let config={range_nm:50}, planes=[], newsItems=[], newsPage=0;
const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');
const n=(v,d=0)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(d):'—';
const trails=new Map();
function updateTrails(current,now=Date.now()){
 for(const [id,t] of trails){t.points=t.points.filter(q=>now-q.t<=90000);if(now-t.seen>90000||!t.points.length)trails.delete(id);}
 for(const p of current){const id=p.id||p.flight;let t=trails.get(id)||{points:[],seen:now};const last=t.points[t.points.length-1];
 if(!last||Math.abs(last.d-p.distance)>.002||Math.abs(last.b-p.bearing)>.1)t.points.push({d:p.distance,b:p.bearing,t:now});
 t.points=t.points.slice(-32);t.seen=now;trails.set(id,t);}
 while(trails.size>250)trails.delete(trails.keys().next().value);
}
function drawTrails(x,y,r){
 const now=Date.now();ctx.save();ctx.lineWidth=1.5;
 for(const t of trails.values())for(let i=1;i<t.points.length;i++){
 const a=t.points[i-1],b=t.points[i];if(now-a.t>90000||a.d>config.range_nm||b.d>config.range_nm)continue;
 const pa=a.b*Math.PI/180,pb=b.b*Math.PI/180,ra=r*Math.sqrt(a.d/config.range_nm),rb=r*Math.sqrt(b.d/config.range_nm);
 ctx.strokeStyle='rgba(0,232,242,'+Math.max(0,.55*(1-(now-a.t)/90000))+')';ctx.beginPath();ctx.moveTo(x+Math.sin(pa)*ra,y-Math.cos(pa)*ra);ctx.lineTo(x+Math.sin(pb)*rb,y-Math.cos(pb)*rb);ctx.stroke();
 }ctx.restore();
}
function radar(){
 const w=340,h=326,x=170,y=162,r=142;ctx.clearRect(0,0,w,h);ctx.fillStyle='#02090c';ctx.fillRect(0,0,w,h);
 ctx.strokeStyle='#234e20';ctx.lineWidth=1;
 for(let i=1;i<=4;i++){ctx.beginPath();ctx.arc(x,y,r*i/4,0,Math.PI*2);ctx.stroke();}
 ctx.beginPath();ctx.moveTo(x-r,y);ctx.lineTo(x+r,y);ctx.moveTo(x,y-r);ctx.lineTo(x,y+r);ctx.stroke();
 ctx.font='11px monospace';ctx.fillStyle='#75ff00';ctx.fillText('N',x-3,14);ctx.fillText('S',x-3,319);ctx.fillText('W',9,y+4);ctx.fillText('E',322,y+4);
 ctx.font='8px monospace';ctx.fillStyle='#7d999e';ctx.fillText(`${config.range_nm} NM (${n(config.range_nm*1.852)} km) · EXPANDED CENTER`,8,309);
 if(!planes.length){ctx.fillStyle='#7d999e';ctx.textAlign='center';ctx.fillText('NO LIVE CONTACTS',x,y+22);ctx.textAlign='left';}
 drawTrails(x,y,r);
 const dots=planes.map(p=>{const b=p.bearing*Math.PI/180,d=r*Math.sqrt(p.distance/config.range_nm);return {p,px:x+Math.sin(b)*d,py:y-Math.cos(b)*d};});
 const boxes=[];
 for(const {p,px,py} of dots){
 ctx.save();ctx.translate(px,py);ctx.rotate((p.track||0)*Math.PI/180);ctx.shadowColor='#00e8f2';ctx.shadowBlur=4;ctx.strokeStyle='#8fffff';ctx.lineWidth=1.7;ctx.beginPath();ctx.moveTo(0,-6);ctx.lineTo(0,6);ctx.moveTo(-5,2);ctx.lineTo(0,-1);ctx.lineTo(5,2);ctx.stroke();ctx.restore();
 }
 ctx.font='10px monospace';
 for(const {p,px,py} of dots.slice(0,8)){
 const width=ctx.measureText(p.flight).width+8,height=15;
 let best=null,bestScore=Infinity;
 for(const distance of [18,32,48,66,86,110]){
 for(const angle of [-Math.PI/4,Math.PI/4,-3*Math.PI/4,3*Math.PI/4,0,Math.PI,-Math.PI/2,Math.PI/2]){
 const cx=px+Math.cos(angle)*distance,cy=py+Math.sin(angle)*distance;
 const left=Math.max(18,Math.min(322-width,cx-width/2)),top=Math.max(22,Math.min(286,cy-height/2));
 const box={left,top,right:left+width,bottom:top+height};
 const overlaps=boxes.filter(q=>box.left<q.right+4&&box.right>q.left-4&&box.top<q.bottom+4&&box.bottom>q.top-4).length;
 const covers=dots.filter(q=>q.px>box.left-9&&q.px<box.right+9&&q.py>box.top-9&&q.py<box.bottom+9).length;
 const score=overlaps*10000+covers*1000+distance;
 if(score<bestScore){best=box;bestScore=score;}
 }
 if(bestScore<1000)break;
 }
 boxes.push(best);
 const tx=(best.left+best.right)/2,ty=(best.top+best.bottom)/2;
 ctx.strokeStyle='#3d827b';ctx.lineWidth=.7;ctx.beginPath();ctx.moveTo(px,py);ctx.lineTo(tx,ty);ctx.stroke();
 ctx.fillStyle='#020d11';ctx.fillRect(best.left,best.top,width,height);
 ctx.fillStyle='#7cfcff';ctx.fillText(p.flight,best.left+4,best.top+11);
 }

}
async function api(route){const r=await fetch('/api/'+route,{signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('HTTP '+r.status);return r.json();}
function state(id,ok){$(id).className=ok?'good':'bad';}
async function updateAircraft(){try{const a=await api('aircraft');state('adsbLight',a.ok);planes=a.ok?a.data.planes:[];if(a.ok)updateTrails(planes);else trails.clear();$('contacts').textContent=a.ok?`${planes.length} CONTACTS`:'OFFLINE';$('radarInfo').textContent=a.ok?'LIVE READSB · WIDE VIEW '+config.range_nm+' NM ('+n(config.range_nm*1.852)+' km)':'READSB UNAVAILABLE · CHECK CONFIG';$('airMessage').textContent=a.ok?(planes.length?'':'No positioned aircraft in range'):'Receiver unavailable or location unset';$('planes').replaceChildren();for(const p of planes.slice(0,7)){const tr=document.createElement('tr');const alt=typeof p.alt==='number'?`${n(p.alt)} (${n(p.alt*.3048)})`:p.alt||'—';for(const value of [p.flight,alt,`${n(p.speed)} (${n(p.speed*1.852)})`,`${n(p.distance,1)} (${n(p.distance*1.852,1)})`]){const td=document.createElement('td');td.textContent=value;tr.append(td);}$('planes').append(tr);}radar();}catch{planes=[];trails.clear();radar();state('adsbLight',false);$('contacts').textContent='DISCONNECTED';$('planes').replaceChildren();$('airMessage').textContent='Dashboard connection lost';$('radarInfo').textContent='NO LIVE DATA';}}
function condition(code){if(code===0)return ['☀','Clear'];if(code<=3)return ['☁','Partly cloudy'];if(code<=48)return ['≋','Fog'];if(code<=67)return ['☂','Rain / drizzle'];if(code<=77)return ['❄','Snow'];if(code<=82)return ['☂','Rain showers'];if(code<=86)return ['❄','Snow showers'];return ['ϟ','Thunderstorms'];}
async function updateWeather(){try{const a=await api('weather');state('wxLight',a.ok);$('weatherState').textContent=a.ok?'OK':a.data?'STALE':'OFFLINE';const box=$('weatherBody');box.replaceChildren();if(!a.data){box.textContent='Weather unavailable. Set coordinates in config.json.';return;}const w=a.data,[icon,label]=condition(w.weather_code);for(const [tag,text,cls] of [['div',icon+' '+n(w.temperature_2m*9/5+32)+'°F','temperature'],['div',n(w.temperature_2m,1)+'°C · '+label,''],['div','HUMIDITY '+n(w.relative_humidity_2m)+'%',''],['div','WIND '+n(w.wind_speed_10m)+' km/h',''],['div','('+n(w.wind_speed_10m/1.609,1)+' mph)',''],['div','FEELS '+n(w.apparent_temperature*9/5+32)+'°F ('+n(w.apparent_temperature)+'°C)','']]){const el=document.createElement(tag);el.textContent=text;el.className=cls;box.append(el);}}catch{state('wxLight',false);$('weatherState').textContent='DISCONNECTED';}}
function showNews(){const box=$('headlines');box.replaceChildren();if(!newsItems.length){box.textContent='No RSS headlines available';return;}for(const item of newsItems.slice(newsPage*5,newsPage*5+5)){const a=document.createElement('a');a.className='headline';a.href=item.url;a.target='_blank';a.rel='noopener noreferrer';a.title=item.title;const small=document.createElement('small');small.textContent=item.source;a.append(small,document.createTextNode(item.title));box.append(a);}}
async function updateNews(){try{const a=await api('news');state('rssLight',a.ok);newsItems=a.data?.items||[];newsPage=0;$('newsState').textContent=a.ok?(a.data.failed.length?'RSS · PARTIAL':'RSS · LIVE'):'RSS · STALE / OFFLINE';showNews();}catch{state('rssLight',false);$('newsState').textContent='RSS · DISCONNECTED';}}
async function updateStatus(){try{const s=await api('status');$('connection').textContent='● ONLINE';state('connection',true);$('cpu').textContent=s.temperature===null?'PI OK':n(s.temperature)+'°C ('+n(s.temperature*9/5+32)+'°F)';}catch{$('connection').textContent='● OFFLINE';state('connection',false);}}
async function updateMarkets(){try{const a=await api('football');const box=$('marketBody');box.replaceChildren();$('footballState').textContent=a.ok?'TOP 25 · ESPN':'TOP 25 · STALE / OFFLINE';if(!a.data){box.textContent='SCORES UNAVAILABLE';return;}if(!a.data.weekend){box.textContent='TOP 25 COLLEGE FOOTBALL · SCORES RETURN THIS WEEKEND';return;}if(!a.ok){box.textContent='SCORES UNAVAILABLE · LAST DATA NOT LIVE';return;}if(!a.data.games.length){box.textContent='NO TOP 25 GAMES THIS WEEKEND';return;}const text=a.data.games.map(g=>g.text).join(' | ');const track=document.createElement('div');track.id='scoreTrack';track.style.setProperty('--scroll-seconds',Math.max(35,text.length/9)+'s');
for(let i=0;i<2;i++){const group=document.createElement('span');group.className='scoreGroup';if(i)group.setAttribute('aria-hidden','true');for(const g of a.data.games){const el=document.createElement('span');el.className='scoreGame'+(g.ou?' ou':'');el.textContent=(g.ou?'OU SPOTLIGHT · ':'')+g.text;group.append(el);}track.append(group);}box.append(track);}catch{$('footballState').textContent='TOP 25 · OFFLINE';$('marketBody').textContent='SCORES UNAVAILABLE';}}


let alertData=null,alertOK=false,alertIndex=0;
function showAlerts(){
 const banner=$('alertBanner'),status=$('alertStatus');
 const items=(alertData?.items||[]).filter(a=>a.expires*1000>Date.now());
 status.textContent=alertOK?(items.length?'NWS · '+items.length+' ACTIVE':'NWS · NO ACTIVE ALERTS'):'NWS · UNAVAILABLE / STALE';
 status.className=alertOK&&!items.length?'good':'bad';
 banner.hidden=!items.length;$('news').classList.toggle('hasAlerts',!!items.length);
 if(items.length){const a=items[alertIndex%items.length];banner.textContent=(alertOK?'NWS · ':'STALE NWS · ')+a.event+' · '+a.headline;banner.className=['Extreme','Severe'].includes(a.severity)?'severe':'';banner.title=a.headline+'\n'+a.description+'\n'+a.instruction;}
}
async function updateAlerts(){try{const a=await api('alerts');alertData=a.data;alertOK=a.ok;showAlerts();}catch{alertOK=false;showAlerts();}}

function clock(){$('clock').textContent=new Date().toLocaleString('en-US',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});}
async function start(){try{config=await api('config');$('location').textContent=config.location;}catch{}radar();updateAircraft();updateWeather();updateNews();updateStatus();updateMarkets();updateAlerts();setInterval(updateAlerts,60000);setInterval(()=>{alertIndex++;showAlerts();},12000);setInterval(updateAircraft,3000);setInterval(updateWeather,60000);setInterval(updateNews,60000);setInterval(updateStatus,15000);setInterval(updateMarkets,60000);setInterval(()=>{if(newsItems.length){newsPage=(newsPage+1)%Math.ceil(newsItems.length/5);showNews();}},15000);clock();setInterval(clock,1000);}
start();
