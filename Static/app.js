const $=id=>document.getElementById(id);
let mode='mix';
document.querySelectorAll('.mode').forEach(btn=>btn.addEventListener('click',()=>{mode=btn.dataset.mode;document.querySelectorAll('.mode').forEach(b=>b.classList.toggle('active',b===btn));$('mixFields').classList.toggle('hidden',mode!=='mix');$('masterFields').classList.toggle('hidden',mode!=='master');$('error').classList.add('hidden');$('result').classList.add('hidden')}));
[['instrumental','instName'],['vocals','voxName'],['track','trackName']].forEach(([input,label])=>$(input).addEventListener('change',()=>{$(label).textContent=$(input).files[0]?.name||'Escolher ficheiro'}));
$('vocalGain').addEventListener('input',e=>$('gainValue').textContent=`${e.target.value} dB`);
$('lufs').addEventListener('input',e=>$('lufsValue').textContent=`${e.target.value.replace('-','−')} LUFS`);
$('form').addEventListener('submit',async e=>{
 e.preventDefault();$('error').classList.add('hidden');$('result').classList.add('hidden');
 if(mode==='mix'&&(!$('instrumental').files[0]||!$('vocals').files[0])){showError('Carrega tanto a instrumental como os vocais.');return}
 if(mode==='master'&&!$('track').files[0]){showError('Carrega primeiro a música que queres masterizar.');return}
 const data=new FormData();data.append('mode',mode);data.append('output_format',document.querySelector('input[name=format]:checked').value);data.append('target_lufs',$('lufs').value);data.append('vocal_gain',$('vocalGain').value);
 if(mode==='mix'){data.append('instrumental',$('instrumental').files[0]);data.append('vocals',$('vocals').files[0])}else data.append('track',$('track').files[0]);
 $('submit').disabled=true;$('progressWrap').classList.remove('hidden');$('progressText').textContent='A analisar e processar o áudio…';$('progressPct').textContent='A trabalhar';$('submit').firstChild.textContent=' A PROCESSAR…';
 try{const response=await fetch('/api/process',{method:'POST',body:data});if(!response.ok){let msg='Falha ao processar o áudio.';try{const t=await response.json();msg=t.detail||msg}catch{}throw new Error(msg)}
 const blob=await response.blob();const url=URL.createObjectURL(blob);const ext=data.get('output_format');const a=document.createElement('a');a.href=url;a.download=`Levi_Master_AI.${ext}`;a.textContent='Descarregar ficheiro';$('result').replaceChildren();const title=document.createElement('b');title.textContent='✓ Master concluído! ';$('result').append(title,document.createTextNode('O teu ficheiro está pronto. '),a);$('result').classList.remove('hidden');$('progressText').textContent='Processamento concluído';$('progressPct').textContent='100%';$('progressWrap').querySelector('.progress span').style.animation='none';$('progressWrap').querySelector('.progress span').style.width='100%';a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
 }catch(err){showError(err.message||'Não foi possível processar o ficheiro.');}finally{$('submit').disabled=false;$('submit').firstChild.textContent='✦ PROCESSAR A MINHA MÚSICA';setTimeout(()=>$('progressWrap').classList.add('hidden'),1800)}
});
function showError(msg){$('error').textContent=msg;$('error').classList.remove('hidden')}
if('serviceWorker' in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('/static/sw.js').catch(()=>{}));
