let session = {
  started:false, userId:"", age:25, previousVisits:0,
  page:"Home", pages:1, clicks:0, startedAt:0
};

function $(id){ return document.getElementById(id); }

function startJourney(){
  session.started = true;
  session.userId = $("userId").value.trim() || "U1001";
  session.age = Number($("age").value || 25);
  session.previousVisits = Number($("previousVisits").value || 0);
  session.page = "Home";
  session.pages = 1;
  session.clicks = 0;
  session.startedAt = Date.now();

  $("journeyArea").classList.remove("hidden");
  updatePredictionAndSave();
}

async function go(page){
  if(!session.started) return;
  session.page = page;
  if(page !== "Home") session.pages += 1;
  session.clicks += 1;
  await updatePredictionAndSave();
}

function resetJourney(){
  session.page="Home";
  session.pages=1;
  session.clicks=0;
  session.startedAt=Date.now();
  updatePredictionAndSave();
}

function duration(){
  return session.startedAt ? Math.floor((Date.now()-session.startedAt)/1000) : 0;
}

async function updatePredictionAndSave(){
  const payload = {
    user_id:session.userId,
    current_page:session.page,
    age:session.age,
    pages_visited:session.pages,
    session_duration:duration(),
    clicks:session.clicks,
    previous_visits:session.previousVisits
  };

  try{
    const r = await fetch("/api/event", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
    });
    const d = await r.json();
    const pct = Number(d.percentage || 0);

    $("currentPage").textContent=session.page;
    $("probability").textContent=pct.toFixed(2)+"%";
    $("risk").textContent=d.user.risk;
    $("pages").textContent=session.pages;
    $("predPage").textContent=session.page;
    $("predProbability").textContent=pct.toFixed(2)+"%";
    $("predRisk").textContent=d.user.risk;
    $("sessionInfo").textContent=duration()+" sec · "+session.clicks+" clicks";
    $("riskBar").style.width=Math.max(2,pct)+"%";

    if(session.page==="Purchase"){
      $("recommendation").textContent="🟢 Purchase completed. Drop-off probability is 0% and the journey is complete.";
    }else if(d.user.risk==="HIGH"){
      $("recommendation").textContent="🚨 High-risk user. Consider immediate assistance, an offer, or a relevant recommendation.";
    }else if(d.user.risk==="MEDIUM"){
      $("recommendation").textContent="⚠️ Medium-risk user. Consider additional product information or personalized guidance.";
    }else{
      $("recommendation").textContent="🟢 Low-risk user. User appears engaged.";
    }

    refreshLiveTable();
  }catch(e){
    console.error(e);
  }
}

async function refreshLiveTable(){
  const table=$("liveTable");
  if(!table) return;
  try{
    const r=await fetch("/api/live?ts="+Date.now(),{cache:"no-store"});
    const d=await r.json();
    const events=d.events||[];
    $("eventCount").textContent=events.length+" events · auto refresh 2s";

    if(!events.length){
      table.innerHTML='<div class="empty">No live events yet.</div>';
      return;
    }

    const cols=["timestamp","user_id","current_page","age","pages_visited","session_duration","clicks","previous_visits","dropout_probability","risk"];
    const labels={"timestamp":"Time","user_id":"User ID","current_page":"Page","age":"Age","pages_visited":"Pages","session_duration":"Duration","clicks":"Clicks","previous_visits":"Prev. Visits","dropout_probability":"Drop-Off","risk":"Risk"};
    let h="<table><thead><tr>"+cols.map(c=>"<th>"+labels[c]+"</th>").join("")+"</tr></thead><tbody>";
    for(const row of events){
      h+="<tr>"+cols.map(c=>{
        let v=row[c]??"";
        if(c==="dropout_probability" && v!=="") v=(Number(v)*100).toFixed(2)+"%";
        if(c==="risk") v='<span class="risk-'+String(v).toLowerCase()+'">'+String(v)+'</span>';
        return "<td>"+String(v).replaceAll("<","&lt;").replaceAll(">","&gt;")+"</td>";
      }).join("")+"</tr>";
    }
    h+="</tbody></table>";
    table.innerHTML=h;
  }catch(e){}
}

if($("liveTable")){
  refreshLiveTable();
  setInterval(refreshLiveTable,2000);
  setInterval(()=>{
    if(session.started){
      $("sessionInfo").textContent=duration()+" sec · "+session.clicks+" clicks";
    }
  },1000);
}
