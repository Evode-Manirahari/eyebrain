"""Self-contained single-page UI (no external CDNs — resilient to venue wifi).

Security-console layout: a tab bar (All cameras + one tab per camera), a camera grid you
click to open and play, each camera's caption "script" (timeline), and a voice agent you
can ask about all cameras or a single one."""

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>eyebrain</title>
<style>
  :root{ --bg:#0b0f14; --panel:#121821; --line:#1f2935; --txt:#e6edf3; --muted:#8b98a5;
         --accent:#3fd0c9; --accent2:#5b9dff; --warn:#f0a85f; }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  header{padding:18px 28px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px}
  .logo{width:30px;height:30px;border-radius:8px;background:radial-gradient(circle at 30% 30%,var(--accent),var(--accent2));box-shadow:0 0 18px rgba(63,208,201,.5)}
  h1{font-size:19px;margin:0;letter-spacing:.5px}
  .status{margin-left:auto;color:var(--muted);font-size:12px;text-align:right}
  main{max-width:1080px;margin:0 auto;padding:22px}
  .ask{display:flex;align-items:center;gap:8px;background:var(--panel);border:1px solid var(--line);
       border-radius:16px;padding:6px 8px 6px 18px}
  .ask:focus-within{border-color:var(--accent)}
  input[type=text]{flex:1;background:transparent;border:0;color:var(--txt);font-size:17px;outline:none;padding:12px 0}
  input[type=text]::placeholder{color:var(--muted)}
  .mic{width:46px;height:46px;border-radius:50%;background:var(--accent);color:#05221f;flex:none;border:0;
       display:flex;align-items:center;justify-content:center;cursor:pointer;transition:background .15s,transform .1s}
  .mic:hover{filter:brightness(1.08)} .mic:active{transform:scale(.95)}
  .mic.live{background:var(--warn);color:#2a1800;animation:pulse 1.1s infinite}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(240,168,95,.6)}100%{box-shadow:0 0 0 14px rgba(240,168,95,0)}}
  button{border:0;cursor:pointer;font:inherit}
  button.ghost{background:var(--panel);color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:3px 10px;font-size:12px}
  .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 14px}
  .tab{background:var(--panel);border:1px solid var(--line);color:var(--muted);padding:8px 14px;border-radius:20px;cursor:pointer;font-size:13px}
  .tab:hover{color:var(--txt)} .tab.on{background:var(--accent);color:#05221f;border-color:var(--accent);font-weight:600}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
  .cam{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;cursor:pointer;transition:border-color .15s}
  .cam:hover{border-color:var(--accent)}
  .cam .ph{position:relative}
  .cam img{width:100%;height:150px;object-fit:cover;background:#000;display:block}
  .cam .liveband{position:absolute;top:8px;left:8px;background:rgba(0,0,0,.6);color:#fff;font-size:11px;border-radius:6px;padding:2px 8px;display:flex;align-items:center;gap:6px}
  .dot{width:7px;height:7px;border-radius:50%;background:#ff5d5d;box-shadow:0 0 8px #ff5d5d}
  .cam .nm{padding:11px 13px;font-weight:600;font-size:14px}
  .cam .nm small{display:block;color:var(--muted);font-weight:400;font-size:12px;margin-top:2px}
  .single{display:grid;grid-template-columns:1.4fr 1fr;gap:16px}
  @media(max-width:820px){.single{grid-template-columns:1fr}}
  #player{width:100%;max-height:460px;border-radius:12px;background:#000;display:block}
  .panelttl{color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:1px;margin:2px 0 8px}
  .script{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;max-height:460px;overflow:auto}
  .ev{display:flex;gap:10px;padding:8px 10px;border-radius:8px;cursor:pointer}
  .ev:hover{background:#182230} .ev .t{color:var(--accent2);font-size:12px;flex:none;width:96px}
  .ev .s{font-size:13px;color:var(--txt)}
  .answer{margin-top:16px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px;display:none}
  .answer.show{display:block}
  .answer .label{color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;display:flex;gap:10px;align-items:center}
  .answer .text{font-size:18px;line-height:1.55}
  .badge{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:10px;padding:2px 8px}
  .cites{margin-top:14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
  .cite{background:#0e141b;border:1px solid var(--line);border-radius:10px;overflow:hidden;cursor:pointer}
  .cite:hover{border-color:var(--accent)} .cite img{width:100%;height:120px;object-fit:cover;background:#000;display:block}
  .cite .m{padding:8px 10px} .cite .c{font-weight:600;font-size:13px} .cite .tc{color:var(--accent2);font-size:12px}
  .cite .su{color:var(--muted);font-size:12px;margin-top:4px;max-height:48px;overflow:hidden}
  .muted{color:var(--muted)} .err{color:var(--warn)}
</style>
</head>
<body>
<header>
  <div class="logo"></div>
  <h1>eyebrain</h1>
  <div class="status" id="status">loading…</div>
</header>
<main>
  <form class="ask" id="askForm">
    <input id="q" type="text" placeholder="Ask your cameras anything…" autocomplete="off"/>
    <button type="button" id="mic" class="mic" title="Tap to speak" aria-label="Speak">
      <svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="2.5" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><line x1="12" y1="18" x2="12" y2="21.5"/>
      </svg>
    </button>
  </form>

  <div class="tabs" id="tabs"></div>

  <div class="answer" id="answer">
    <div class="label">Answer <span class="badge" id="synth"></span> <button class="ghost" id="replay">🔊 replay</button></div>
    <div class="text" id="answerText"></div>
    <div class="cites" id="cites"></div>
  </div>

  <div id="view"></div>
</main>
<script>
const $=s=>document.querySelector(s);
const state={cameras:[],active:"all"};
let lastAnswer="";

async function init(){
  try{
    const d=await (await fetch("/api/cameras")).json();
    state.cameras=d.cameras||[];
    $("#status").innerHTML=`${state.cameras.length} cameras &middot; ${d.indexed_moments} moments &middot; ${d.powered_by||"on-device"}`;
  }catch(e){ $("#status").textContent="offline"; }
  renderTabs(); show("all"); setupMic();
}
function renderTabs(){
  const t=$("#tabs"); t.innerHTML="";
  const mk=(id,label)=>{const b=document.createElement("div");b.className="tab"+(state.active===id?" on":"");b.textContent=label;b.onclick=()=>show(id);return b;};
  t.appendChild(mk("all","◢ All cameras"));
  state.cameras.forEach(c=>t.appendChild(mk(c.camera_id,c.camera_name)));
}
function show(id){
  state.active=id; renderTabs();
  $("#q").placeholder = id==="all" ? "Ask across all cameras…" : `Ask the ${camName(id)} camera…`;
  if(id==="all") renderAll(); else renderSingle(id);
}
function camName(id){const c=state.cameras.find(x=>x.camera_id===id);return c?c.camera_name:id;}

function renderAll(){
  const v=$("#view");
  v.innerHTML='<div class="grid" id="grid"></div>';
  state.cameras.forEach(c=>{
    const el=document.createElement("div");el.className="cam";
    el.innerHTML=`<div class="ph"><img src="/api/frame?camera=${encodeURIComponent(c.camera_id)}&t=0" loading="lazy"/>
      <span class="liveband"><span class="dot"></span>${c.camera_name}</span></div>
      <div class="nm">${c.camera_name}<small>click to view &amp; ask</small></div>`;
    el.onclick=()=>show(c.camera_id);
    $("#grid").appendChild(el);
  });
}

async function renderSingle(cam){
  const v=$("#view");
  v.innerHTML=`<div class="single">
      <div><video id="player" controls playsinline preload="auto" src="/api/video/${encodeURIComponent(cam)}"></video></div>
      <div><div class="panelttl">${camName(cam)} — script</div><div class="script" id="script">loading…</div></div>
    </div>`;
  try{
    const d=await (await fetch("/api/moments?camera="+encodeURIComponent(cam))).json();
    const s=$("#script"); s.innerHTML="";
    if(!d.moments.length){s.innerHTML='<div class="muted" style="padding:10px">no moments</div>';return;}
    d.moments.forEach(m=>{
      const row=document.createElement("div");row.className="ev";
      row.innerHTML=`<span class="t">${m.time_range}</span><span class="s">${m.summary}</span>`;
      row.onclick=()=>seek(m.start_sec);
      s.appendChild(row);
    });
  }catch(e){ $("#script").innerHTML='<div class="err" style="padding:10px">failed to load script</div>'; }
}
function seek(t){const p=$("#player");if(!p)return;try{p.currentTime=Math.max(0,t);}catch(e){}p.play().catch(()=>{});}

let curAudio=null;
function speakBrowser(t){try{speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(t);u.rate=1.05;speechSynthesis.speak(u);}catch(e){}}
async function speak(t){
  try{if(curAudio){curAudio.pause();curAudio=null;}
    const r=await fetch("/api/tts?text="+encodeURIComponent(t));if(!r.ok)throw 0;
    curAudio=new Audio(URL.createObjectURL(await r.blob()));await curAudio.play();
  }catch(e){speakBrowser(t);}
}

async function ask(){
  const q=$("#q").value.trim(); if(!q) return;
  $("#answer").classList.add("show");
  $("#answerText").innerHTML='<span class="muted">searching…</span>';
  $("#cites").innerHTML="";$("#synth").textContent="";
  const body={question:q}; if(state.active!=="all") body.camera=state.active;
  try{
    const d=await (await fetch("/api/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})).json();
    lastAnswer=d.answer; $("#answerText").textContent=d.answer;
    $("#synth").textContent=d.synthesis||"";
    (d.citations||[]).forEach(c=>{
      const el=document.createElement("div");el.className="cite";
      const img=c.thumb_url?`<img src="${c.thumb_url}" loading="lazy"/>`:"";
      el.innerHTML=`${img}<div class="m"><div class="c">${c.camera_name}</div><div class="tc">${c.time_range}</div><div class="su">${c.summary}</div></div>`;
      el.onclick=()=>openAt(c.camera_id,c.start_sec);
      $("#cites").appendChild(el);
    });
    if(d.citations&&d.citations.length){const t=d.citations[0];openAt(t.camera_id,t.start_sec);}
    speak(d.answer);
  }catch(e){ $("#answerText").innerHTML='<span class="err">request failed</span>'; }
}
function openAt(cam,t){
  if(state.active!==cam){ show(cam); setTimeout(()=>seek(t),350); }
  else seek(t);
}

let rec=null;
function setupMic(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){$("#mic").style.display="none";return;}
  rec=new SR();rec.lang="en-US";rec.interimResults=false;rec.maxAlternatives=1;
  rec.onresult=e=>{$("#q").value=e.results[0][0].transcript;ask();};
  rec.onend=()=>$("#mic").classList.remove("live");
  $("#mic").onclick=()=>{try{$("#mic").classList.add("live");rec.start();}catch(e){}};
}
$("#askForm").addEventListener("submit",e=>{e.preventDefault();ask();});
$("#replay").onclick=()=>lastAnswer&&speak(lastAnswer);
init();
</script>
</body>
</html>
"""
