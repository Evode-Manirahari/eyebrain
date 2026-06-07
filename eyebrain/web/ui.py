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
  .ask{display:flex;gap:10px}
  input[type=text]{flex:1;background:var(--panel);border:1px solid var(--line);color:var(--txt);
    padding:14px 16px;border-radius:12px;font-size:16px;outline:none}
  input[type=text]:focus{border-color:var(--accent)}
  button{background:var(--accent);color:#05221f;border:0;padding:0 18px;border-radius:12px;font-weight:600;cursor:pointer;font-size:15px}
  button.ghost{background:var(--panel);color:var(--txt);border:1px solid var(--line)}
  button:active{transform:translateY(1px)}
  .mic{width:52px;font-size:20px}
  .mic.live{background:var(--warn);animation:pulse 1s infinite}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(240,168,95,.6)}100%{box-shadow:0 0 0 14px rgba(240,168,95,0)}}
  .chips{margin:14px 0 6px;display:flex;flex-wrap:wrap;gap:8px}
  .chip{background:var(--panel);border:1px solid var(--line);color:var(--muted);padding:7px 12px;border-radius:20px;cursor:pointer;font-size:13px}
  .chip:hover{border-color:var(--accent2);color:var(--txt)}
  .answer{margin-top:22px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 22px;display:none}
  .answer.show{display:block}
  .answer .label{color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;display:flex;gap:10px;align-items:center}
  .answer .text{font-size:18px;line-height:1.55}
  .badge{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:10px;padding:2px 8px}
  .grid{margin-top:18px;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
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
  <div class="ask">
    <input id="q" type="text" placeholder="Ask: When did the display get knocked over?" autocomplete="off"/>
    <button id="mic" class="mic ghost" title="Speak">🎤</button>
    <button id="go">Ask</button>
  </div>
  <div class="chips" id="chips"></div>

  <div class="answer" id="answer">
    <div class="label">Answer <span class="badge" id="synth"></span> <button class="ghost" id="replay" style="padding:2px 10px;font-size:12px">🔊 replay</button></div>
    <div class="text" id="answerText"></div>
    <div class="grid" id="grid"></div>
  </div>
</main>
<script>
const $=s=>document.querySelector(s);
const EXAMPLES=[
  "When did the display get knocked over?",
  "Where did the contractor leave the equipment?",
  "Did anyone leave a package by the rear exit?",
  "Was there any spill on the floor?"
];
function renderChips(){
  $("#chips").innerHTML="";
  EXAMPLES.forEach(t=>{const c=document.createElement("div");c.className="chip";c.textContent=t;
    c.onclick=()=>{$("#q").value=t;ask();};$("#chips").appendChild(c);});
}
async function loadStatus(){
  try{const r=await fetch("/api/cameras");const d=await r.json();
    $("#status").innerHTML=`${d.cameras.length} cameras &middot; ${d.indexed_moments} moments &middot; ${d.retriever}`;
  }catch(e){$("#status").textContent="offline";}
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
      const img=c.thumb_url?`<img src="${c.thumb_url}" loading="lazy"/>`:`<div style="height:150px;display:flex;align-items:center;justify-content:center" class="muted">no preview</div>`;
      card.innerHTML=`${img}<div class="meta"><span class="score">${c.score}</span>
        <div class="cam">${c.camera_name}</div><div class="tc">${c.time_range}</div>
        <div class="sum">${c.summary}</div></div>`;
      $("#grid").appendChild(card);
    });
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
$("#go").onclick=ask;
$("#q").addEventListener("keydown",e=>{if(e.key==="Enter")ask();});
$("#replay").onclick=()=>lastAnswer&&speak(lastAnswer);
renderChips();loadStatus();setupMic();
</script>
</body>
</html>
"""
