let series=null, generation=0;
const el=id=>document.getElementById(id);
const number=(value,digits=1)=>Number(value).toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
const date=ts=>new Date(ts*1000).toLocaleString('pt-BR');
async function request(url){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(10000)});if(!r.ok)throw new Error('Falha HTTP '+r.status);return r.json()}
function card(name,value){const box=document.createElement('article'),label=document.createElement('small'),v=document.createElement('strong');label.textContent=name;v.textContent=value;box.append(label,v);return box}
async function live(){
  try{
    const d=await request('/api'),hours=Math.floor(d.uptime/3600);
    el('cards').replaceChildren(
      card('Temperatura',d.temp==null?'Indisponível':number(d.temp)+' °C'),
      card('CPU',number(d.cpu)+' %'),
      card('RAM',number(d.ram)+' %'),
      card('Disco ocupado (/)',number(100*d.disk_used/d.disk_total)+' %'),
      card('Tempo ligada',Math.floor(hours/24)+'d '+hours%24+'h '+Math.floor(d.uptime%3600/60)+'min'));
    el('cards').children[2].title=number(d.ram_used,2)+' / '+number(d.ram_total,2)+' GiB';
    el('cards').children[3].title=number(d.disk_used)+' / '+number(d.disk_total)+' GiB';
    const stale=Date.now()/1000-d.ts>20;
    el('status').textContent=(stale?'Coleta atrasada. Última leitura: ':'Última leitura: ')+date(d.ts);
    el('status').className=stale?'error':'';
  }catch{el('status').textContent='Sem leitura atual. Tentando novamente...';el('status').className='error'}
  setTimeout(live,5000);
}
function draw(key,color){
  const canvas=el(key),w=canvas.clientWidth,h=canvas.clientHeight,dpr=window.devicePixelRatio||1;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const left=38,right=w-14,top=15,bottom=h-38;
  if(!series||right<=left)return;
  const points=series.points,valid=points.filter(p=>p[key]!=null);
  const ceiling=key==='temp'?Math.max(80,...valid.map(p=>Math.ceil(p[key]/10)*10)):100;
  const x=t=>left+(t-series.start)/(series.end-series.start)*(right-left);
  const y=v=>bottom-v/ceiling*(bottom-top);
  ctx.font='11px system-ui';ctx.textBaseline='middle';
  for(let i=0;i<=4;i++){
    const v=ceiling*i/4,yy=y(v);ctx.strokeStyle='#2b394d';ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(right,yy);ctx.stroke();
    ctx.fillStyle='#a6b3c5';ctx.textAlign='right';ctx.fillText(String(Math.round(v)),left-8,yy);
  }
  for(let i=0;i<=2;i++){
    const t=series.start+(series.end-series.start)*i/2;
    const options=series.end-series.start>86400?{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}:{hour:'2-digit',minute:'2-digit'};
    ctx.textAlign=i===0?'left':i===2?'right':'center';
    ctx.fillText(new Date(t*1000).toLocaleString('pt-BR',options),x(t),h-12);
  }
  ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;ctx.beginPath();
  let previous=null;
  for(const p of points){
    if(p[key]==null){previous=null;continue}
    if(previous&&p.ts-previous.ts<=Math.max(90,series.bucket*2))ctx.lineTo(x(p.ts),y(p[key]));
    else ctx.moveTo(x(p.ts),y(p[key]));
    previous=p;
  }
  ctx.stroke();
  for(const p of valid){ctx.beginPath();ctx.arc(x(p.ts),y(p[key]),2,0,Math.PI*2);ctx.fill()}
  if(!valid.length){ctx.textAlign='center';ctx.fillStyle='#a6b3c5';ctx.fillText('Ainda sem dados neste período',(left+right)/2,(top+bottom)/2)}
  canvas.setAttribute('aria-label',valid.length?`${key}: ${valid.length} pontos, último valor ${number(valid[valid.length-1][key])}`:`${key}: sem dados`);
}
function redraw(){draw('temp','#6ee7b7');draw('cpu','#70b8ff');draw('ram','#c4a1ff')}
async function loadHistory(){
  const token=++generation;
  try{
    const data=await request('/api/history?period='+encodeURIComponent(el('period').value));
    if(token!==generation)return;
    series=data;redraw();
    el('history-status').textContent=data.total_samples?`Histórico desde ${date(data.first)} · ${data.points.length} pontos neste período · médias a cada ${number(data.bucket/60,1)} min.`:'O histórico começa agora. Aguarde as primeiras coletas.';
    el('history-status').className='';
  }catch{if(token===generation){el('history-status').textContent='Não foi possível atualizar o histórico. Tentando novamente...';el('history-status').className='error'}}
}
el('period').addEventListener('change',()=>{series=null;redraw();el('history-status').textContent='Carregando período...';loadHistory()});
new ResizeObserver(redraw).observe(el('temp').parentElement);
live();loadHistory();setInterval(loadHistory,30000);
