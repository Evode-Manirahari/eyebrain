"""Self-contained single-page UI (no external CDNs — resilient to venue wifi)."""

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
  header{padding:22px 28px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px}
  .logo{width:30px;height:30px;border-radius:8px;background:radial-gradient(circle at 30% 30%,var(--accent),var(--accent2));box-shadow:0 0 18px rgba(63,208,201,.5)}
  h1{font-size:19px;margin:0;letter-spacing:.5px}
  header .sub{color:var(--muted);font-size:13px}
  .status{margin-left:auto;color:var(--muted);font-size:12px;text-align:right}
  main{max-width:980px;margin:0 auto;padding:26px}
  .ask{display:flex;align-items:center;gap:8px;background:var(--panel);border:1px solid var(--line);
       border-radius:16px;padding:6px 8px 6px 18px}
  .ask:focus-within{border-color:var(--accent)}
  input[type=text]{flex:1;background:transparent;border:0;color:var(--txt);font-size:17px;outline:none;padding:12px 0}
  input[type=text]::placeholder{color:var(--muted)}
  button{border:0;cursor:pointer;font:inherit}
  button.ghost{background:var(--panel);color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:3px 10px;font-size:12px}
  button:active{transform:translateY(1px)}
  .mic{width:46px;height:46px;border-radius:50%;background:var(--accent);color:#05221f;flex:none;
       display:flex;align-items:center;justify-content:center;transition:background .15s,transform .1s}
  .mic:hover{filter:brightness(1.08)}
  .mic:active{transform:scale(.95)}
  .mic.live{background:var(--warn);color:#2a1800;animation:pulse 1.1s infinite}
  .hint{color:var(--muted);font-size:12.5px;margin-top:10px;text-align:center}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(240,168,95,.6)}100%{box-shadow:0 0 0 14px rgba(240,168,95,0)}}
  .answer{margin-top:22px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 22px;display:none}
  .answer.show{display:block}
  .answer .label{color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;display:flex;gap:10px;align-items:center}
  .answer .text{font-size:18px;line-height:1.55}
  .badge{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:10px;padding:2px 8px}
  #clip{display:none;margin-top:16px}
  #player{width:100%;max-height:420px;border-radius:12px;background:#000;display:block}
  .cliplabel{color:var(--accent2);font-size:13px;margin-bottom:6px}
  .gridhint{color:var(--muted);font-size:12px;margin-top:18px}
  .grid{margin-top:8px;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;cursor:pointer;transition:border-color .15s}
  .card:hover{border-color:var(--accent)}
  .card .play{position:absolute;top:8px;left:8px;background:rgba(0,0,0,.6);color:#fff;border-radius:6px;font-size:11px;padding:2px 7px}
  .card .thumb{position:relative}
  .card img{width:100%;height:150px;object-fit:cover;background:#000;display:block}
  .card .meta{padding:10px 12px}
  .card .cam{font-weight:600;font-size:13px}
  .card .tc{color:var(--accent2);font-size:12px}
  .card .sum{color:var(--muted);font-size:12px;margin-top:6px;max-height:54px;overflow:hidden}
  .card .score{float:right;color:var(--muted);font-size:11px}
  .muted{color:var(--muted)}
  .err{color:var(--warn)}
</style>
</head>
<body>
<header>
  <div class="logo"></div>
  <div>
    <h1>eyebrain</h1>
    <div class="sub">talk to your cameras &middot; on-device video search</div>
  </div>
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
  <div class="hint" id="hint">Tap the mic and ask — or type and press Enter.</div>

  <div class="answer" id="answer">
    <div class="label">Answer <span class="badge" id="synth"></span> <button class="ghost" id="replay" style="padding:2px 10px;font-size:12px">🔊 replay</button></div>
    <div class="text" id="answerText"></div>
    <div id="clip">
      <div class="cliplabel" id="clipLabel"></div>
      <video id="player" controls playsinline preload="auto"></video>
    </div>
    <div class="gridhint" id="gridhint"></div>
    <div class="grid" id="grid"></div>
  </div>
</main>
<script>
const $=s=>document.querySelector(s);
async function loadStatus(){
  try{const r=await fetch("/api/cameras");const d=await r.json();
    $("#status").innerHTML=`${d.cameras.length} cameras &middot; ${d.indexed_moments} moments &middot; ${d.powered_by||"on-device"}`;
  }catch(e){$("#status").textContent="offline";}
}
// Clip player: load a camera's video and seek to a cited timecode.
function seekTo(cam, t, label){
  const player=$("#player");
  $("#clip").style.display="block";
  $("#clipLabel").textContent="▶ "+(label||"");
  const url="/api/video/"+encodeURIComponent(cam);
  const go=()=>{ try{player.currentTime=Math.max(0,t);}catch(e){} player.play().catch(()=>{}); };
  if(player.dataset.cam!==cam){
    player.dataset.cam=cam; player.src=url; player.load();
    player.onloadeddata=go;
  } else { go(); }
}
let curAudio=null;
function speakBrowser(text){
  try{window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.rate=1.05;window.speechSynthesis.speak(u);}catch(e){}
}
async function speak(text){
  // Prefer MiniMax TTS (sponsor); fall back to browser speech if unavailable.
  try{
    if(curAudio){curAudio.pause();curAudio=null;}
    const r=await fetch("/api/tts?text="+encodeURIComponent(text));
    if(!r.ok) throw new Error("tts "+r.status);
    const blob=await r.blob();
    curAudio=new Audio(URL.createObjectURL(blob));
    await curAudio.play();
  }catch(e){ speakBrowser(text); }
}
let lastAnswer="";
async function ask(){
  const q=$("#q").value.trim(); if(!q) return;
  $("#answer").classList.add("show");
  $("#answerText").innerHTML='<span class="muted">searching cameras…</span>';
  $("#grid").innerHTML="";$("#synth").textContent="";
  try{
    const r=await fetch("/api/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})});
    const d=await r.json();
    if(!r.ok){$("#answerText").innerHTML=`<span class="err">${d.detail||"error"}</span>`;return;}
    lastAnswer=d.answer;
    $("#answerText").textContent=d.answer;
    $("#synth").textContent=d.synthesis==="llm"?"on-device LLM":(d.synthesis||"");
    d.citations.forEach(c=>{
      const card=document.createElement("div");card.className="card";
      const img=c.thumb_url?`<div class="thumb"><img src="${c.thumb_url}" loading="lazy"/><span class="play">▶ ${c.time_range}</span></div>`:`<div style="height:150px;display:flex;align-items:center;justify-content:center" class="muted">no preview</div>`;
      card.innerHTML=`${img}<div class="meta"><span class="score">${c.score}</span>
        <div class="cam">${c.camera_name}</div><div class="tc">${c.time_range}</div>
        <div class="sum">${c.summary}</div></div>`;
      card.onclick=()=>seekTo(c.camera_id,c.start_sec,`${c.camera_name} @ ${c.time_range}`);
      $("#grid").appendChild(card);
    });
    // Jump the player to the top cited moment ("when did it happen").
    if(d.citations.length){
      const t=d.citations[0];
      seekTo(t.camera_id,t.start_sec,`${t.camera_name} @ ${t.time_range}`);
      $("#gridhint").textContent="Other matching moments (click any clip to jump the video):";
    } else { $("#clip").style.display="none"; $("#gridhint").textContent=""; }
    speak(d.answer);
  }catch(e){$("#answerText").innerHTML=`<span class="err">request failed: ${e}</span>`;}
}
// Web Speech API mic (zero-key voice input)
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
loadStatus();setupMic();
</script>
</body>
</html>
"""
