$path = 'C:\Users\Dave\Projects\pricedrop\pricedrop_app.html'
$rest = @'
    <p>v4.0.2 — 27 apr 2026</p>
    <ul>
      <li>🃏 Card view (mobile-first) — tap een kaart om de deal te openen</li>
      <li>🔥 Hot-deal highlights — top deals krijgen een vlam-badge</li>
      <li>🔁 Toggle Card / Tabel weergave (footer-knop)</li>
      <li>✅ SCAN-fix: progress-balk, max 8min timeout, dedup tegen dubbel-klik</li>
      <li>🎨 Modernere look: gradient borders, glow-effects, betere typografie</li>
    </ul>
    <p>v3.4.0 — 4 apr 2026</p>
    <ul>
      <li>Tweakers scraper gefixt: juiste URL (/pricewatch/deals/) + CSS selectors</li>
      <li>PAT via URL parameter: open ?pat=TOKEN op telefoon om SCAN knop te activeren</li>
    </ul>
    <p>v3.3.0 — 4 apr 2026</p>
    <ul>
      <li>SCAN knop: start scan direct vanuit de app (via GitHub Actions)</li>
      <li>Scan-tijd indicator: duidelijk zichtbaar wanneer laatste scan was</li>
      <li>Auto-refresh na scan (pollt GitHub voor resultaat)</li>
      <li>HA/Nabu Casa volledig ontkoppeld</li>
    </ul>
    <p>v3.2.0 — 4 apr 2026</p>
    <ul>
      <li>Tweakers Pricewatch integratie: deals scrapen + prijsverificatie</li>
      <li>Verificatiebron zichtbaar per deal (Tweakers/Idealo/Google)</li>
      <li>14+ shops</li>
    </ul>
    <p>v3.1.0 — 4 apr 2026</p>
    <ul>
      <li>Dark table layout (mobiel-geoptimaliseerd)</li>
      <li>Stats balk met totaal deals, hoogste korting, winst</li>
      <li>iBood scanner: sorteren op korting, early-stop, kleding-filter</li>
    </ul>
    <p>v3.0.0 — 3 apr 2026</p>
    <ul>
      <li>Cache-busting, semver, landvlaggen, Duits→NL, oude deals opruimen</li>
    </ul>
    <p>v2.5.0 — 3 apr 2026</p>
    <ul>
      <li>Rebranding: Deef's PriceDrop, PIN-login, nep-filter</li>
    </ul>
  </div>
</div>

<!-- PAT SETUP MODAL -->
<div class="pat-modal" id="patModal" onclick="if(event.target===this)this.style.display='none'">
  <div class="pat-box">
    <h3>GitHub Token instellen</h3>
    <p>Om scans te starten heb je een GitHub Personal Access Token nodig met <b>actions:write</b> scope.<br>Ga naar GitHub → Settings → Developer settings → Fine-grained tokens.</p>
    <input type="password" id="patInput" placeholder="github_pat_...">
    <div class="btns">
      <button class="pat-cancel" onclick="document.getElementById('patModal').style.display='none'">Annuleer</button>
      <button class="pat-save" onclick="savePat()">Opslaan</button>
    </div>
  </div>
</div>

<script id="dd" type="application/json">__DEAL_DATA__</script>
<script>
// ===================== PIN SYSTEM =====================
const PD_HASH='pd_pin_hash',PD_TRIES='pd_pin_tries',PD_LOCK='pd_pin_lock',PD_UNLOCK='pd_pin_unlock';
const PIN_SESSION=4*60*60*1000,MAX_TRIES=5,LOCKOUT=15*60*1000;
let pinBuf='',pinMode='enter',pinNew='';

async function hashPin(p){
  const d=new TextEncoder().encode('deef-pricedrop-2026-'+p);
  const b=await crypto.subtle.digest('SHA-256',d);
  return Array.from(new Uint8Array(b)).map(x=>x.toString(16).padStart(2,'0')).join('');
}
function getHash(){return localStorage.getItem(PD_HASH)}
function isLocked(){return Date.now()<+(localStorage.getItem(PD_LOCK)||0)}
function lockMins(){return Math.ceil((+(localStorage.getItem(PD_LOCK)||0)-Date.now())/60000)}
function recFail(){
  const t=+(localStorage.getItem(PD_TRIES)||0)+1;
  if(t>=MAX_TRIES){localStorage.setItem(PD_LOCK,''+(Date.now()+LOCKOUT));localStorage.removeItem(PD_TRIES);return true}
  localStorage.setItem(PD_TRIES,''+t);return false;
}
function clrFail(){localStorage.removeItem(PD_TRIES);localStorage.removeItem(PD_LOCK)}

function initPin(){
  if(Date.now()<+(localStorage.getItem(PD_UNLOCK)||0)){showApp();return}
  if(!getHash()){pinMode='set-new';document.getElementById('pin-lbl').textContent='Kies een PIN van 6 cijfers'}
  else{pinMode='enter';document.getElementById('pin-lbl').textContent='Voer je PIN in'}
}

function pinPress(d){
  if(isLocked()){document.getElementById('pin-lbl').textContent='Geblokkeerd — '+lockMins()+' min';return}
  if(pinBuf.length>=6)return;
  pinBuf+=d;renderDots();
  document.getElementById('pin-err').classList.add('h');
  if(pinBuf.length===6)setTimeout(handlePin,120);
}
function pinBack(){if(!pinBuf.length)return;pinBuf=pinBuf.slice(0,-1);renderDots()}
function renderDots(s){document.querySelectorAll('.pin-dot').forEach((d,i)=>{d.classList.remove('ok','err');if(s==='err')d.classList.add('err');else if(i<pinBuf.length)d.classList.add('ok')})}
function pinErr(m){const e=document.getElementById('pin-err');e.textContent=m||'Onjuiste PIN';e.classList.remove('h');renderDots('err');setTimeout(()=>{pinBuf='';renderDots()},700)}

async function handlePin(){
  if(isLocked()){document.getElementById('pin-lbl').textContent='Geblokkeerd — '+lockMins()+' min';pinBuf='';renderDots();return}
  const h=await hashPin(pinBuf);
  if(pinMode==='enter'){
    if(h===getHash()){clrFail();localStorage.setItem(PD_UNLOCK,''+(Date.now()+PIN_SESSION));showApp()}
    else{const l=recFail();if(l){document.getElementById('pin-lbl').textContent='Geblokkeerd — '+lockMins()+' min';document.querySelectorAll('.pin-b').forEach(b=>b.disabled=true);pinBuf='';renderDots()}else{const left=MAX_TRIES-+(localStorage.getItem(PD_TRIES)||0);pinErr('Onjuiste PIN — nog '+left)}}
  }else if(pinMode==='set-new'){
    pinNew=pinBuf;pinMode='confirm';pinBuf='';renderDots();document.getElementById('pin-lbl').textContent='Bevestig je PIN';
  }else if(pinMode==='confirm'){
    if(pinBuf===pinNew){localStorage.setItem(PD_HASH,h);localStorage.setItem(PD_UNLOCK,''+(Date.now()+PIN_SESSION));showApp()}
    else{pinErr('PINs komen niet overeen');setTimeout(()=>{pinMode='set-new';pinNew='';document.getElementById('pin-lbl').textContent='Kies een PIN van 6 cijfers';document.getElementById('pin-err').classList.add('h')},800)}
  }
}

function showApp(){
  document.getElementById('pin-s').classList.add('hidden');
  const app=document.getElementById('app');app.classList.add('show');
  resumeScanIfRunning();
  render();
}

// ===================== DEAL DATA =====================
const ST='__SCAN_TIME__';
let D=[],P=168,S='discount_percent',Q='',MP=0,HIDE_NEP=true,ONLY_VERI=false;
let VIEW='cards';
let tblSort='discount_percent',tblAsc=false;
try{const r=document.getElementById('dd').textContent.trim();if(r&&!r.includes('__'))D=JSON.parse(r)}catch(e){}

// ===================== CONTROLS =====================
const thr=document.getElementById('thr'),thrV=document.getElementById('thrV');
const mpEl=document.getElementById('mp'),mpV=document.getElementById('mpV');
const qEl=document.getElementById('q');
const g=k=>localStorage.getItem('pd6_'+k);
if(g('t'))thr.value=g('t');
if(g('m'))mpEl.value=g('m');
if(g('v'))VIEW=g('v');

function updateThrVisual(){
  const min=+thr.min,max=+thr.max,val=+thr.value;
  const pct=((val-min)/(max-min))*100;
  thr.style.setProperty('--p',pct+'%');
}
function updateMpVisual(){
  const min=+mpEl.min,max=+mpEl.max,val=+mpEl.value;
  const pct=((val-min)/(max-min))*100;
  mpEl.style.setProperty('--p',pct+'%');
}
thrV.textContent=thr.value+'%';MP=+mpEl.value;mpV.textContent='€'+MP;
updateThrVisual();updateMpVisual();

thr.addEventListener('input',()=>{thrV.textContent=thr.value+'%';updateThrVisual();localStorage.setItem('pd6_t',thr.value);render()});
mpEl.addEventListener('input',()=>{MP=+mpEl.value;mpV.textContent='€'+MP;updateMpVisual();localStorage.setItem('pd6_m',mpEl.value);render()});
qEl.addEventListener('input',()=>{Q=qEl.value.toLowerCase();render()});

document.getElementById('fb').addEventListener('click',e=>{
  const b=e.target.closest('.fb');if(!b)return;
  if(b.dataset.h){document.querySelectorAll('[data-h]').forEach(x=>x.classList.remove('on'));b.classList.add('on');P=+b.dataset.h;render()}
  if(b.dataset.s){document.querySelectorAll('[data-s]').forEach(x=>x.classList.remove('on'));b.classList.add('on');S=b.dataset.s;render()}
  if(b.dataset.tog==='nep'){HIDE_NEP=!HIDE_NEP;b.classList.toggle('on',HIDE_NEP);render()}
  if(b.dataset.tog==='veri'){ONLY_VERI=!ONLY_VERI;b.classList.toggle('on',ONLY_VERI);render()}
});

function toggleView(){
  VIEW=(VIEW==='cards')?'table':'cards';
  localStorage.setItem('pd6_v',VIEW);
  document.getElementById('vToggle').textContent=(VIEW==='cards')?'🃏 Cards':'📋 Tabel';
  render();
}
document.getElementById('vToggle').textContent=(VIEW==='cards')?'🃏 Cards':'📋 Tabel';

// ===================== FILTER + SORT =====================
function flt(){
  const md=+thr.value,co=Date.now()-P*36e5;
  return D.filter(d=>{
    if(d.discount_percent<md)return false;
    if(d.current_price<MP)return false;
    if(d.found_at&&new Date(d.found_at).getTime()<co)return false;
    if(Q&&!d.product_name.toLowerCase().includes(Q))return false;
    if(HIDE_NEP&&d.is_fake_discount)return false;
    if(ONLY_VERI&&!d.is_verified)return false;
    return true;
  }).sort((a,b)=>{
    if(S==='mp_profit')return(b.mp_profit||0)-(a.mp_profit||0);
    if(S==='found_at')return new Date(b.found_at||0)-new Date(a.found_at||0);
    if(S==='current_price')return a.current_price-b.current_price;
    return(b.real_discount_percent||b.discount_percent)-(a.real_discount_percent||a.discount_percent);
  });
}

function sortTable(col){
  if(tblSort===col)tblAsc=!tblAsc;
  else{tblSort=col;tblAsc=false}
  S=col;render();
}

function renderStats(ds){
  const total=ds.length;
  const best=ds.length>0?Math.max(...ds.map(d=>d.real_discount_percent||d.discount_percent)):0;
  const totalProfit=ds.reduce((s,d)=>{const p=(d.mp_profit||0)-(d.shipping_cost||0);return s+(p>0?p:0)},0);
  const shops=new Set(ds.map(d=>d.shop.split('(')[0].trim())).size;
  document.getElementById('statsBar').innerHTML=
    '<div class="stat"><div class="val">'+total+'</div><div class="lbl">Deals</div></div>'+
    '<div class="stat"><div class="val hot">-'+best.toFixed(0)+'%</div><div class="lbl">Hoogste</div></div>'+
    '<div class="stat"><div class="val profit">€'+totalProfit.toFixed(0)+'</div><div class="lbl">MP winst</div></div>'+
    '<div class="stat"><div class="val">'+shops+'</div><div class="lbl">Shops</div></div>';
}

// ===================== RENDER =====================
function escAttr(s){return (s||'').replace(/[&<>"']/g,c=>({"&":"&","<":"<",">":">",'"':""","'":"&#39;"}[c]))}
function escHtml(s){return (s||'').replace(/[&<>]/g,c=>({"&":"&","<":"<",">":">"}[c]))}

function buildTags(d,ship){
  let tags='';
  if(d.mp_median_price){
    const pr=(d.mp_profit||0)-ship;
    tags+='<span class="tag tag-b">MP €'+d.mp_median_price.toFixed(0)+'</span>';
    tags+='<span class="tag '+(pr>=0?'tag-g':'tag-r')+'">'+(pr>=0?'+':'')+'€'+pr.toFixed(0)+'</span>';
  }
  if(d.tweakers_price)tags+='<span class="tag tag-b" title="Tweakers Pricewatch">TW €'+d.tweakers_price.toFixed(0)+'</span>';
  if(d.is_verified&&!d.is_fake_discount){
    const src=d.verification_source||'';
    tags+='<span class="tag tag-g">✅ ECHT'+(src?' ('+escHtml(src)+')':'')+'</span>';
  }
  if(d.is_fake_discount)tags+='<span class="tag tag-r">⚠️ NEP</span>';
  if(d.coupon_code)tags+='<span class="tag tag-c">🎟 '+escHtml(d.coupon_code)+'</span>';
  return tags;
}

function fmtTime(found_at){
  if(!found_at)return '';
  const d=new Date(found_at);
  return d.toLocaleString('nl-NL',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
}

function renderCards(ds){
  const el=document.getElementById('dl');
  const sortedByDisc=[...ds].sort((a,b)=>(b.real_discount_percent||b.discount_percent)-(a.real_discount_percent||a.discount_percent));
  const hotIds=new Set(sortedByDisc.slice(0,3).filter(d=>(d.real_discount_percent||d.discount_percent)>=60).map(d=>d.url));
  let h='';
  for(const d of ds){
    const disc=d.real_discount_percent||d.discount_percent;
    const dCls=disc>=60?'disc-hot':disc>=40?'disc-warm':'disc-cool';
    const cls=['card'];
    if(d.is_fake_discount)cls.push('fake');
    if(d.is_verified&&!d.is_fake_discount)cls.push('veri');
    if(hotIds.has(d.url))cls.push('hot');
    const shop=d.shop.split('(')[0].trim();
    const flag=d.country_flag||'';
    const ship=d.shipping_cost||0;
    const tags=buildTags(d,ship);
    h+='<a class="'+cls.join(' ')+'" href="'+escAttr(d.url)+'" target="_blank" rel="noopener" title="'+escAttr(d.product_name)+'">'+
      '<div class="c-row1">'+
        '<span class="shop-pill"><span class="flag">'+flag+'</span>'+escHtml(shop)+'</span>'+
        '<span class="disc '+dCls+'">−'+disc.toFixed(0)+'%</span>'+
      '</div>'+
      '<div class="c-name">'+escHtml(d.product_name)+'</div>'+
      '<div class="c-prices">'+
        '<span class="c-now">€'+d.current_price.toFixed(2)+'</span>'+
        '<span class="c-was">€'+d.original_price.toFixed(0)+'</span>'+
      '</div>'+
      (tags?'<div class="c-tags">'+tags+'</div>':'')+
      '<div class="c-foot">'+
        '<span class="c-time">📅 '+fmtTime(d.found_at)+'</span>'+
        '<span class="c-arrow">Bekijk →</span>'+
      '</div>'+
      '</a>';
  }
  el.innerHTML=h;
}

function renderTable(ds){
  const thCls=c=>tblSort===c?(tblAsc?'sorted-asc':'sorted'):'';
  let h='<div class="tbl-wrap"><table><thead><tr>'+
    '<th class="'+thCls('product_name')+'" onclick="sortTable(\'product_name\')">Product</th>'+
    '<th class="'+thCls('shop')+'" onclick="sortTable(\'shop\')">Shop</th>'+
    '<th class="'+thCls('current_price')+'" onclick="sortTable(\'current_price\')">Prijs</th>'+
    '<th class="'+thCls('original_price')+'" onclick="sortTable(\'original_price\')">Was</th>'+
    '<th class="'+thCls('discount_percent')+'" onclick="sortTable(\'discount_percent\')">Korting</th>'+
    '<th>Info</th>'+
    '<th class="'+thCls('found_at')+'" onclick="sortTable(\'found_at\')">Tijd</th>'+
    '<th></th>'+
    '</tr></thead><tbody>';
  for(const d of ds){
    const disc=d.real_discount_percent||d.discount_percent;
    const dCls=disc>=60?'disc-hot':disc>=40?'disc-warm':'disc-cool';
    const nep=d.is_fake_discount?' nep-row':'';
    const veri=(d.is_verified&&!d.is_fake_discount)?' veri-row':'';
    const t=fmtTime(d.found_at);
    const shop=d.shop.split('(')[0].trim();
    const flag=d.country_flag||'';
    const ship=d.shipping_cost||0;
    const tags=buildTags(d,ship);
    const name=d.product_name.length>55?d.product_name.substring(0,55)+'...':d.product_name;
    h+='<tr class="'+nep+veri+'">'+
      '<td class="name-col">'+escHtml(name)+'</td>'+
      '<td><span class="shop-pill">'+flag+' '+escHtml(shop)+'</span></td>'+
      '<td style="font-weight:700">€'+d.current_price.toFixed(2)+'</td>'+
      '<td style="text-decoration:line-through;color:#555">€'+d.original_price.toFixed(0)+'</td>'+
      '<td><span class="disc '+dCls+'" style="font-size:13px;padding:2px 8px">−'+disc.toFixed(0)+'%</span></td>'+
      '<td>'+tags+'</td>'+
      '<td style="color:#555;font-size:11px">'+t+'</td>'+
      '<td><a href="'+escAttr(d.url)+'" target="_blank" rel="noopener" class="link-btn">Bekijk</a></td>'+
      '</tr>';
  }
  h+='</tbody></table></div>';
  document.getElementById('dl').innerHTML=h;
}

function render(){
  const ds=flt();
  document.getElementById('cnt').textContent=ds.length+' deals';
  renderStats(ds);
  if(!ds.length){
    document.getElementById('dl').innerHTML='<div class="empty"><div class="ic">🔍</div><div class="t1">Geen deals gevonden</div><div class="t2">Pas je filters aan of doe een nieuwe scan</div></div>';
    return;
  }
  if(VIEW==='cards')renderCards(ds);
  else renderTable(ds);
}

// ===================== SCAN TRIGGER =====================
const GH_REPO='thegaveryahoo/pricedrop';
const GH_WORKFLOW='scan.yml';
const PAT_KEY='pd_github_pat';
const SCAN_STATE_KEY='pd_scan_state';
const MAX_SCAN_DURATION=8*60*1000;
const POLL_INTERVAL=15*1000;
const PAT_FAIL_KEY='pd_pat_fails';
const PAT_FAIL_MAX=3;

(function(){const u=new URLSearchParams(location.search);const p=u.get('pat');if(p){localStorage.setItem(PAT_KEY,p);history.replaceState(null,'',location.pathname)}})();

function getPat(){return localStorage.getItem(PAT_KEY)}
function getScanState(){try{return JSON.parse(localStorage.getItem(SCAN_STATE_KEY)||'null')}catch(e){return null}}
function setScanState(s){if(s)localStorage.setItem(SCAN_STATE_KEY,JSON.stringify(s));else localStorage.removeItem(SCAN_STATE_KEY)}

function showProgress(msg,pct){
  const p=document.getElementById('scanProgress');
  const t=document.getElementById('scanProgressText');
  const f=document.getElementById('scanProgressFill');
  p.classList.add('show');
  t.innerHTML='<span class="spinner"></span>'+msg;
  if(typeof pct==='number')f.style.width=Math.min(100,Math.max(0,pct))+'%';
}
function hideProgress(){document.getElementById('scanProgress').classList.remove('show')}

function setScanBtn(state,text){
  const btn=document.getElementById('scanBtn');
  btn.classList.remove('running','err','ok');
  if(state)btn.classList.add(state);
  btn.textContent=text;
}

function savePat(){
  const v=document.getElementById('patInput').value.trim();
  if(v){
    localStorage.setItem(PAT_KEY,v);
    localStorage.removeItem(PAT_FAIL_KEY);
    document.getElementById('patModal').style.display='none';
    triggerScan();
  }
}

let _scanTimer=null;

async function triggerScan(){
  const pat=getPat();
  if(!pat){document.getElementById('patModal').style.display='flex';return}
  const existing=getScanState();
  if(existing && (Date.now()-existing.start_at)<MAX_SCAN_DURATION){
    showProgress('Scan loopt al — bezig...');
    setScanBtn('running','Loopt...');
    schedulePoll(pat);
    return;
  }
  const start_at=Date.now();
  setScanBtn('running','Starten...');
  showProgress('Scan starten...',5);
  try{
    const r=await fetch('https://api.github.com/repos/'+GH_REPO+'/actions/workflows/'+GH_WORKFLOW+'/dispatches',{
      method:'POST',
      headers:{'Authorization':'Bearer '+pat,'Accept':'application/vnd.github+json','Content-Type':'application/json'},
      body:JSON.stringify({ref:'master'})
    });
    if(r.status===204){
      setScanState({start_at,run_id:null,status:'queued',attempts:0});
      localStorage.removeItem(PAT_FAIL_KEY);
      setScanBtn('running','Loopt...');
      showProgress('Gestart! Even wachten op GitHub...',10);
      _scanTimer=setTimeout(()=>pollScanResult(pat),8000);
    }else if(r.status===401||r.status===403){
      handlePatFail();
    }else{
      const txt=await r.text().catch(()=>'');
      setScanBtn('err','Fout '+r.status);
      hideProgress();
      console.error('Scan trigger failed:',r.status,txt);
      setTimeout(()=>setScanBtn(null,'SCAN'),4000);
    }
  }catch(e){
    setScanBtn('err','Netwerk fout');
    hideProgress();
    console.error('Scan trigger error:',e);
    setTimeout(()=>setScanBtn(null,'SCAN'),4000);
  }
}

function handlePatFail(){
  const fails=+(localStorage.getItem(PAT_FAIL_KEY)||0)+1;
  localStorage.setItem(PAT_FAIL_KEY,''+fails);
  if(fails>=PAT_FAIL_MAX){
    localStorage.removeItem(PAT_KEY);
    localStorage.removeItem(PAT_FAIL_KEY);
    setScanBtn('err','Token ongeldig');
    hideProgress();
    setTimeout(()=>{setScanBtn(null,'SCAN');document.getElementById('patModal').style.display='flex'},2000);
  }else{
    setScanBtn('err','Auth fout ('+fails+'/'+PAT_FAIL_MAX+')');
    hideProgress();
    setTimeout(()=>setScanBtn(null,'SCAN'),3000);
  }
}

function schedulePoll(pat){
  if(_scanTimer)clearTimeout(_scanTimer);
  _scanTimer=setTimeout(()=>pollScanResult(pat),POLL_INTERVAL);
}

async function pollScanResult(pat){
  const state=getScanState();
  if(!state){hideProgress();setScanBtn(null,'SCAN');return}
  const elapsed=Date.now()-state.start_at;
  if(elapsed>MAX_SCAN_DURATION){
    setScanState(null);
    hideProgress();
    setScanBtn('err','Time-out (8 min)');
    setTimeout(()=>setScanBtn(null,'SCAN'),5000);
    return;
  }
  const elapsedSec=Math.floor(elapsed/1000);
  const elapsedTxt=elapsedSec<60?elapsedSec+'s':Math.floor(elapsedSec/60)+'m '+(elapsedSec%60)+'s';
  const pctEstimate=Math.min(85,10+elapsed/MAX_SCAN_DURATION*75);
  try{
    const r=await fetch('https://api.github.com/repos/'+GH_REPO+'/actions/workflows/'+GH_WORKFLOW+'/runs?per_page=5',{
      headers:{'Authorization':'Bearer '+pat,'Accept':'application/vnd.github+json'}
    });
    if(r.status===401||r.status===403){handlePatFail();setScanState(null);return}
    if(!r.ok)throw new Error('runs API '+r.status);
    const data=await r.json();
    const runs=data.workflow_runs||[];
    const ourRun=runs.find(run=>{const createdAt=new Date(run.created_at).getTime();return createdAt>=(state.start_at-30000);});
    if(!ourRun){showProgress('Wachten op start... ('+elapsedTxt+')',pctEstimate);schedulePoll(pat);return}
    if(state.run_id!==ourRun.id){state.run_id=ourRun.id;setScanState(state)}
    if(ourRun.status==='completed'){
      setScanState(null);
      hideProgress();
      if(ourRun.conclusion==='success'){
        setScanBtn('ok','Klaar!');
        showProgress('Pagina ververst...',100);
        setTimeout(()=>location.reload(),1200);
      }else{
        setScanBtn('err','Scan faalde');
        setTimeout(()=>setScanBtn(null,'SCAN'),5000);
      }
      return;
    }
    const statusTxt=ourRun.status==='queued'?'In wachtrij':'Loopt';
    showProgress(statusTxt+'... ('+elapsedTxt+')',pctEstimate);
    schedulePoll(pat);
  }catch(e){
    console.error('Poll error:',e);
    showProgress('Verbinding wankel... ('+elapsedTxt+')',pctEstimate);
    schedulePoll(pat);
  }
}

function resumeScanIfRunning(){
  const state=getScanState();
  if(!state)return;
  const elapsed=Date.now()-state.start_at;
  if(elapsed>MAX_SCAN_DURATION){setScanState(null);return}
  const pat=getPat();
  if(!pat){setScanState(null);return}
  setScanBtn('running','Loopt...');
  showProgress('Scan loopt nog...');
  schedulePoll(pat);
}

// ===================== PULL-TO-REFRESH =====================
(function(){
  const dl=document.getElementById('dl');
  let startY=0, pulling=false, pulled=false;
  const ptr=document.createElement('div');
  ptr.className='ptr';
  ptr.innerHTML='<span class="ptr-icon">↓</span> Trek omlaag om te verversen';
  dl.parentElement.style.position='relative';
  dl.parentElement.insertBefore(ptr,dl);
  dl.addEventListener('touchstart',e=>{if(dl.scrollTop<=0){startY=e.touches[0].clientY;pulling=true}},{passive:true});
  dl.addEventListener('touchmove',e=>{
    if(!pulling)return;
    const dy=e.touches[0].clientY-startY;
    if(dy>0&&dl.scrollTop<=0){
      const pct=Math.min(1,dy/120);
      ptr.style.top=(-50+pct*60)+'px';
      ptr.style.opacity=pct;
      ptr.querySelector('.ptr-icon').style.transform='rotate('+(pct*180)+'deg)';
      if(pct>=1&&!pulled){pulled=true;ptr.querySelector('.ptr-icon').textContent='↻';ptr.querySelector('.ptr-icon').classList.add('spin');ptr.innerHTML='<span class="ptr-icon spin">↻</span> Verversen...';setTimeout(()=>location.reload(),400)}
    }
  },{passive:true});
  dl.addEventListener('touchend',()=>{
    if(pulling){ptr.style.top='-50px';ptr.style.opacity='0';ptr.querySelector('.ptr-icon').style.transform='';ptr.querySelector('.ptr-icon').classList.remove('spin');ptr.innerHTML='<span class="ptr-icon">↓</span> Trek omlaag om te verversen';pulling=false;pulled=false}
  },{passive:true});
})();

// ===================== SCAN TIME =====================
function updateScanTime(){
  const el=document.getElementById('scanTime');
  const sp=document.getElementById('sp'),st=document.getElementById('st');
  if(!ST||ST.includes('__')){
    el.textContent='Nog geen scan uitgevoerd';
    sp.className='sp sp-x';st.textContent='?';
    return;
  }
  const p=ST.match(/(\d{2})-(\d{2})-(\d{4})\s(\d{2}):(\d{2})/);
  if(!p)return;
  const sd=new Date(+p[3],+p[2]-1,+p[1],+p[4],+p[5]);
  const m=Math.floor((Date.now()-sd.getTime())/60000);
  let timeStr;
  if(m<1)timeStr='Zojuist gescand';
  else if(m<60)timeStr='Laatste scan: '+m+' min geleden';
  else if(m<1440)timeStr='Laatste scan: '+Math.floor(m/60)+'u '+m%60+'m geleden';
  else timeStr='Laatste scan: '+Math.floor(m/1440)+'d geleden';
  const shops='__SCAN_SHOPS__';
  if(shops&&!shops.includes('__'))timeStr+=' ('+shops+' shops)';
  el.textContent=timeStr;
  if(m<60){sp.className='sp sp-ok';st.textContent=m+'m'}
  else if(m<240){sp.className='sp sp-w';st.textContent=Math.floor(m/60)+'u'}
  else{sp.className='sp sp-x';st.textContent=Math.floor(m/60)+'u'}
}
updateScanTime();
setInterval(updateScanTime,60000);

initPin();
if('serviceWorker' in navigator){
  const swPath='/pricedrop/pricedrop_sw.js';
  navigator.serviceWorker.register(swPath).then(reg=>{reg.update()}).catch(()=>{});
}
</script>
</body>
</html>
'@
Add-Content -Path $path -Value $rest -Encoding UTF8
Write-Host "Done! File size: $((Get-Item $path).Length) bytes"
</｜DSML｜parameter>
</｜DSML｜invoke>
</｜DSML｜tool_calls>