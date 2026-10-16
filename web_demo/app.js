const $ = id => document.getElementById(id);
let targetModule = 'colors', toastTimer;
function notifyUser(message) { $('toast').textContent=message; $('toast').classList.add('show'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').classList.remove('show'),4000); }
function validatePainting(file) {
  if (!file || !/^image\/(png|jpeg|gif|webp)$/.test(file.type)) { notifyUser('请选择 PNG、JPG、GIF 或 WebP 图片'); return false; }
  if(file.size>30*1024*1024) { notifyUser('图片超过30 MB，请选择较小的图片'); return false; }
  return true;
}
function resetResults() {
  renderTechniqueAnalysis();
  $('colorResults').innerHTML='<p class="empty">正在载入新的古画</p>';
  $('ocrResults').textContent='尚未识别'; $('wordCloud').textContent='识别后生成'; $('wordCloud').style.height='';
  ocrItems=[]; $('ocrOverlay').style.display='none';
  $('analysisState').textContent='等待分析'; $('exportReport').disabled=true;
  $('colorSummary').textContent='尚未分析';
  analyzeBtn.disabled=false; ocrBtn.disabled=false;
  if(window.Plotly) Plotly.purge('plot3d'); $('plot3d').innerHTML='';
}
function showWorkbench() {
  $('uploadDialog').close(); $('home').hidden=true; $('workbench').hidden=false;
  $('homeNav').hidden=true; $('workNav').hidden=false; $('brandHome').textContent='‹ 返回首页';
  $('imageName').textContent=selectedFile?.name||'古画';
  window.scrollTo({top:0,behavior:'instant'});
}
function openUpload() { $('uploadDialog').showModal(); }
document.querySelectorAll('[data-upload]').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();openUpload();}));
document.querySelectorAll('.close-dialog').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));
document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}}));
$('pickFile').onclick=()=>imageInput.click();
async function useSample(asset,name) {
  try { const response=await fetch('assets/'+asset); if(!response.ok)throw Error();const blob=await response.blob();handleImageUpload(new File([blob],name+'.png',{type:'image/png'})); }
  catch { notifyUser('示例读取失败，请通过本地预览服务打开网站，或直接上传图片'); }
}
document.querySelectorAll('[data-sample]').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();targetModule='colors';useSample(b.dataset.sample,b.dataset.name);}));
document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{targetModule=b.dataset.feature;openUpload();});
['homeDrop','modalDrop'].forEach(id=>{const area=$(id);area.addEventListener('click',e=>{if(!e.target.closest('button'))imageInput.click();});area.addEventListener('keydown',e=>{if(e.target===area&&(e.key==='Enter'||e.key===' ')){e.preventDefault();imageInput.click();}});area.addEventListener('dragover',e=>{e.preventDefault();area.classList.add('dragover');});area.addEventListener('dragleave',()=>area.classList.remove('dragover'));area.addEventListener('drop',e=>{e.preventDefault();area.classList.remove('dragover');if(e.dataTransfer.files[0])handleImageUpload(e.dataTransfer.files[0]);});});
imagePreview.addEventListener('load',()=>{analyzeBtn.click();ocrBtn.click();if(targetModule!=='colors')$(targetModule).scrollIntoView({behavior:'smooth'});});
imagePreview.addEventListener('error',()=>{notifyUser('这张图片无法解码，请重新选择');$('analysisState').textContent='图片载入失败';});
$('brandHome').onclick=()=>{$('home').hidden=false;$('workbench').hidden=true;$('homeNav').hidden=false;$('workNav').hidden=true;$('brandHome').textContent='画基因';window.scrollTo({top:0,behavior:'instant'});};
$('runAgain').onclick=()=>analyzeBtn.click(); $('colorCount').onchange=()=>{if(imagePreview.complete&&imagePreview.naturalWidth)analyzeBtn.click();};
$('zoomImage').onclick=()=>{if(!imagePreview.naturalWidth){notifyUser('请先上传图片');return;}$('fullImage').src=imagePreview.src;$('imageDialog').showModal();};
$('exportReport').onclick=()=>{
  const content=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>画基因分析报告</title><style>body{max-width:960px;margin:40px auto;padding:20px;font:16px/1.7 sans-serif}img{max-width:100%;max-height:600px}section{margin:30px 0} .color-match{padding:12px;border-bottom:1px solid #ccc}.color-swatch{width:32px;height:32px;border-radius:50%}button{display:none}</style><h1>画基因 · 古画分析报告</h1><p>${escapeHtml(selectedFile?.name||'古画')}</p><img src="${imagePreview.src}"><section><h2>颜色分析</h2>${$('colorResults').innerHTML}</section><section><h2>题跋文字</h2>${$('ocrResults').innerHTML}<p>${escapeHtml(ocrStatus.textContent)}</p></section><section><h2>印章候选位置</h2><img src="${sealHeatmap.toDataURL()}"><p>${escapeHtml(sealStatus.textContent)}</p></section><section><h2>技法分析</h2><img src="${techniqueRadar.toDataURL()}">${techniqueBars.innerHTML}<p>${escapeHtml(techniqueStatus.textContent)}</p></section><section><h2>国画赏析</h2><p style="white-space:pre-wrap">${escapeHtml(appreciationOutput.textContent)}</p><p>${escapeHtml(appreciationStatus.textContent)}</p></section><p>印章结果为启发式候选评分；技法结果来自本地模型，缺失时不生成分数。</p></html>`;
  const url=URL.createObjectURL(new Blob([content],{type:'text/html;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='画基因分析报告.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notifyUser('报告已导出，可在浏览器打开或打印为PDF');
};
const moduleObserver=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting)document.querySelectorAll('.sidebar-sticky a').forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id));});},{rootMargin:'-100px 0px -55% 0px'});
document.querySelectorAll('.result-panel').forEach(s=>moduleObserver.observe(s));
const revealObserver=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');revealObserver.unobserve(e.target);}}),{threshold:.12});
document.querySelectorAll('.reveal').forEach((el,i)=>{el.style.transitionDelay=(i%2)*120+'ms';revealObserver.observe(el);});
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
let scrollScheduled=false;window.addEventListener('scroll',()=>{if(reducedMotion||scrollScheduled)return;scrollScheduled=true;requestAnimationFrame(()=>{document.querySelector('.hero-background').style.transform=`translateY(${Math.min(window.scrollY,650)*.18}px)`;scrollScheduled=false;});},{passive:true});
async function playEntrance() {
  const entrance=$('entrance'),bg=entrance.querySelector('.entrance-bg'),logo=entrance.querySelector('.entrance-logo');let finished=false;
  const finish=()=>{finished=true;entrance.remove();document.body.style.overflow='';};$('skipIntro').onclick=finish;
  if(reducedMotion){finish();return;}document.body.style.overflow='hidden';
  await Promise.all([document.fonts.ready,logo.decode().catch(()=>{})]);if(finished)return;
  await logo.animate([{opacity:0},{opacity:1}],{duration:850,fill:'forwards',easing:'ease-out'}).finished;
  await new Promise(resolve=>setTimeout(resolve,350));if(finished)return;
  const destination=$('gallery').getBoundingClientRect(),target=$('heroLogo').getBoundingClientRect(),source=logo.getBoundingClientRect();
  const options={duration:1100,easing:'cubic-bezier(.65,0,.2,1)',fill:'forwards'};
  const panel=bg.animate([{transform:'translate(0,0) scale(1,1)'},{transform:`translate(${destination.x}px,${destination.y}px) scale(${destination.width/innerWidth},${destination.height/innerHeight})`}],options);
  logo.style.left=source.x+'px';logo.style.top=source.y+'px';logo.style.transform='none';logo.style.transformOrigin='top left';
  const mark=logo.animate([{transform:'translate(0,0) scale(1)',opacity:1},{transform:`translate(${target.x-source.x}px,${target.y-source.y}px) scale(${target.width/source.width})`,opacity:1}],options);
  await Promise.all([panel.finished,mark.finished]);if(finished)return;await entrance.animate([{opacity:1},{opacity:0}],{duration:200,fill:'forwards'}).finished;finish();
}
playEntrance();
