// TAX quantitative engine adapter for RAPTOR COMMAND
// Reuses the official TAX engine; derives indicators from its daily OHLC history.
const TAX_BASE = 'https://giorgiogoldoni.github.io/TAX-ETP-MANAGER';
const $ = (id) => document.getElementById(id);
const fmt = (v, d=1) => Number.isFinite(v) ? v.toFixed(d) : '—';

function mean(a) { return a.length ? a.reduce((x,y)=>x+y,0)/a.length : null; }
function ema(values, period) {
  if (values.length < period) return null;
  const k=2/(period+1); let e=mean(values.slice(0,period));
  for (let i=period;i<values.length;i++) e=values[i]*k+e*(1-k);
  return e;
}
function sma(values, period) { return values.length>=period ? mean(values.slice(-period)) : null; }
function derive(history, instruments) {
  const all=history.instruments||{}, benchmark=all.CSSPX?.prices||[];
  const bench=benchmark.map(x=>x.close).filter(Number.isFinite);
  const items=[];
  for (const [ticker,seriesObj] of Object.entries(all)) {
    const rows=seriesObj.prices||[], closes=rows.map(x=>x.close).filter(Number.isFinite);
    if (!closes.length) continue;
    const last=closes.at(-1), ma38=sma(closes,38), ma200=sma(closes,200);
    const roc38=closes.length>38 ? (last/closes.at(-39)-1)*100 : null;
    const ema20=ema(closes,20);
    const highs=rows.slice(-34).map(x=>Number.isFinite(x.high)&&Number.isFinite(x.low)?(x.high+x.low)/2:null);
    const ao=highs.length===34&&highs.every(Number.isFinite)
      ? mean(highs.slice(-5))-mean(highs) : null;
    const relative=closes.length>38&&bench.length>38
      ? ((last/closes.at(-39)-1)-(bench.at(-1)/bench.at(-39)-1))*100 : null;
    const peak=Math.max(...closes.slice(-200));
    const drawdown=peak>0?(last/peak-1)*100:null;
    const daily=[];
    for(let i=1;i<closes.length;i++) daily.push(closes[i]/closes[i-1]-1);
    const vol=daily.length>=20?Math.sqrt(mean(daily.slice(-20).map(x=>(x-mean(daily.slice(-20)))**2))*252)*100:null;
    items.push({ticker,price:last,ma38,ma200,roc38,ema20,ao,relative_strength:relative,
      drawdown,volatility_annualized:vol});
  }
  const eligible=items.filter(x=>x.ma200!=null);
  const breadth=eligible.length?eligible.filter(x=>x.price>x.ma200).length/eligible.length*100:null;
  items.forEach(x=>{x.breadth=breadth;});
  return items;
}
function render(items, config, history, instruments) {
  const module=document.createElement('section');
  module.id='tax-quant-module';
  module.style.cssText='background:#fff;border:1px solid #dde2ee;border-radius:8px;padding:14px 16px;box-shadow:0 2px 8px rgba(0,0,0,.035)';
  const updated=history.fetched_at?new Date(history.fetched_at):null;
  const latest=history.latest_date||'—';
  const ageHours=updated?(Date.now()-updated.getTime())/36e5:Infinity;
  const stale=ageHours>48 || history.status==='unavailable';
  const status=stale?'DATI DA AGGIORNARE':history.status==='partial'?'COPERTURA PARZIALE':'DATI DISPONIBILI';
  const statusColor=stale?'#d63040':history.status==='partial'?'#e07b00':'#1a9e63';
  const evaluated=items.map(item=>({...item,signal:window.__taxEvaluate(item,config)}))
    .sort((a,b)=>(b.signal.score??-1)-(a.signal.score??-1));
  const names=Object.fromEntries((instruments.instruments||[]).map(x=>[x.ticker,x.name||x.ticker]));
  const valid=evaluated.filter(x=>x.signal.score!=null);
  const rows=valid.slice(0,12).map(x=>{
    const s=x.signal, color=s.score>=55?'#1a9e63':s.score>=45?'#e07b00':'#d63040';
    return '<tr><td><b>'+x.ticker+'</b><div style="font-size:9px;color:#8a9ab4;max-width:230px">'+(names[x.ticker]||'')+'</div></td>'+
      '<td style="font-weight:700;color:'+color+'">'+fmt(s.score,0)+'</td><td>'+s.label+'</td>'+
      '<td>'+s.coverage+'/5</td><td style="font-size:9px;color:#d63040">'+(s.riskFlags.join(' · ')||'—')+'</td></tr>';
  }).join('');
  module.innerHTML='<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">'+
    '<div><div style="font-size:9px;letter-spacing:1.5px;color:#8a9ab4">MOTORE QUANTITATIVO ESTERNO</div>'+
    '<div style="font-size:18px;font-weight:700;color:#1a2236;margin:3px 0">TAX · ETP MANAGER</div>'+
    '<div style="font-size:10px;color:#5a6e88">Trend MA38/200 · ROC38 · AO/EMA20 · forza relativa · breadth</div></div>'+
    '<div style="text-align:right"><div style="font-size:9px;font-weight:700;color:'+statusColor+'">'+status+'</div>'+
    '<div style="font-size:9px;color:#8a9ab4;margin-top:4px">Ultima seduta: '+latest+'</div>'+
    '<div style="font-size:9px;color:#8a9ab4">Feed: '+(updated?updated.toLocaleString("it-IT"):'non disponibile')+'</div></div></div>'+
    '<div style="display:flex;gap:18px;flex-wrap:wrap;margin:12px 0;padding:9px;background:#f7f8fc;border-radius:5px">'+
    '<span><b>'+valid.length+'</b> strumenti valutabili</span><span><b>'+items.length+'</b> serie storiche</span>'+
    '<span><b>'+fmt(items.find(x=>x.breadth!=null)?.breadth,0)+'%</b> breadth sopra MA200</span>'+
    '<span><b>'+fmt(valid.length?mean(valid.map(x=>x.signal.score)):null,0)+'</b> score medio</span></div>'+
    (rows?'<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:10px"><thead><tr style="text-align:left;color:#8a9ab4"><th style="padding:7px">STRUMENTO</th><th>SCORE</th><th>CLASSE</th><th>DATI</th><th>RISCHI</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<div style="padding:14px;color:#d63040">Nessun segnale calcolabile: storico o indicatori insufficienti.</div>')+
    '<div style="margin-top:10px;font-size:9px;color:#8a9ab4">Motore originale TAX. I campi mancanti non vengono stimati; AO richiede massimi/minimi storici. Score informativo, non ordine automatico. '+
    '<a href="https://giorgiogoldoni.github.io/TAX-ETP-MANAGER/" target="_blank" rel="noopener" style="color:#2678c8">Apri TAX ETP MANAGER ↗</a></div>';
  const page=document.querySelector('.page');
  if(page) page.insertBefore(module,page.firstChild);
}
async function loadTaxQuant() {
  try {
    const [hist,config,instruments,engine]=await Promise.all([
      fetch(TAX_BASE+'/data/history.json').then(r=>{if(!r.ok)throw Error('history '+r.status);return r.json()}),
      fetch(TAX_BASE+'/data/strategy.json').then(r=>{if(!r.ok)throw Error('strategy '+r.status);return r.json()}),
      fetch(TAX_BASE+'/data/instruments.json').then(r=>{if(!r.ok)throw Error('instruments '+r.status);return r.json()}),
      import(TAX_BASE+'/modules/market-engine.js')
    ]);
    window.__taxEvaluate=engine.evaluateInstrument;
    const items=derive(hist,instruments);
    render(items,config,hist,instruments);
  } catch(e) {
    let box=$('tax-quant-module');
    if(!box){box=document.createElement('section');box.id='tax-quant-module';box.style.cssText='background:#fff;border:1px solid #dde2ee;border-radius:8px;padding:14px 16px';const page=document.querySelector('.page');if(page)page.insertBefore(box,page.firstChild);}
    box.innerHTML='<b style="color:#d63040">TAX · Motore quantitativo non disponibile</b><div style="margin-top:5px;font-size:10px;color:#5a6e88">'+String(e.message||e)+'</div>';
  }
}
loadTaxQuant();
setInterval(loadTaxQuant,30*60*1000);
