/* Detailed, on-demand inspectors for recorded data. No external UI dependencies. */
window.HistoryInspector = (() => {
  "use strict";
  const el=id=>document.getElementById(id);
  const esc=value=>String(value ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt=value=>value == null ? "—" : typeof value === "number" ? value.toLocaleString("en-GB",{maximumFractionDigits:2}) : typeof value === "object" ? JSON.stringify(value) : String(value);
  const clock=value=>{const s=Math.max(0,Math.round(value || 0));return `${s>=3600?Math.floor(s/3600)+":":""}${String(Math.floor(s/60)%60).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;};
  const dist=value=>value>=1000?`${fmt(value/1000)} km`:`${fmt(value)} m`;
  const rawId=value=>(value || "").split("/").pop();
  const image=value=>`/api/vehicle-images/${encodeURIComponent(rawId(value))}`;
  const wiki=value=>`https://wiki.warthunder.com/unit/${encodeURIComponent(rawId(value))}`;
  const names={speed:"Speed",rpm:"Engine RPM",gear:"Gear",gear_neutral:"Neutral gear",crew_current:"Remaining crew",crew_total:"Crew capacity",crew_distance:"Crew distance",stabilizer:"Stabilizer",first_stage_ammo:"Ready-rack ammunition",gunner_state:"Gunner state",driver_state:"Driver state",repair_time:"Repair time",burns:"Fire",engine_broken:"Engine damaged",engine_dead:"Engine disabled",track_broken:"Track damaged",transmission_broken:"Transmission damaged",barrel_dead:"Gun barrel disabled",breech_damaged:"Breech damaged",breach_dead:"Breech disabled",is_repairing:"Repairing",is_repairing_auto:"Automatic repair",lws:"Laser warning",ircm:"IR countermeasures",cruise_control:"Cruise control",h_drive_dead:"Horizontal gun drive disabled",h_drive_broken:"Horizontal gun drive damaged",v_drive_broken:"Vertical gun drive damaged",h_drive_damaged:"Horizontal gun drive damaged",gunner_time_to_take_place:"Gunner replacement time",driver_time_to_take_place:"Driver replacement time",gunner_time_to_available:"Gunner recovery time",has_speed_warning:"Speed warning",driving_direction_mode:"Driving direction mode","H, m":"Altitude (m)","TAS, km/h":"True airspeed (km/h)","IAS, km/h":"Indicated airspeed (km/h)","Vy, m/s":"Vertical speed (m/s)","Mfuel, kg":"Fuel (kg)","Mfuel0, kg":"Initial fuel (kg)","M":"Mach",roll_indicators_is_available:"Roll indicator available"};
  const label=key=>names[key.split(".").slice(1).join(".")] || names[key] || key.replace(/^(state|indicators)\./,"");
  let data=null, controls=null, snapshot=null, sampleData=null, eventLimit=100;

  function setupImages(root) {
    root.querySelectorAll("img[data-unit-image]").forEach(img=>img.addEventListener("error",()=>{
      img.src="/static/vehicle-placeholder.svg";img.dataset.fallback="true";
      const credit=img.closest(".vehicle-card")?.querySelector(".vehicle-image-kind");
      if(credit)credit.textContent="Generic illustration";
    },{once:true}));
  }
  function tree(value,key="Record") {
    if(value !== null && typeof value === "object") {
      const details=document.createElement("details"), summary=document.createElement("summary");
      summary.textContent=`${key} · ${Array.isArray(value)?"array":"object"} · ${Object.keys(value).length} entries`;
      details.append(summary);details.className="json-node";
      details.addEventListener("toggle",()=>{
        if(!details.open || details.dataset.loaded)return;
        details.dataset.loaded="true";
        const children=document.createElement("div");children.className="json-children";
        for(const [name,item] of Object.entries(value))children.append(tree(item,name));
        details.append(children);
      });
      return details;
    }
    const row=document.createElement("div");row.className="json-leaf";
    const name=document.createElement("span"), text=document.createElement("code");
    name.textContent=key;text.textContent=value===null?"null":String(value);row.append(name,text);return row;
  }
  function fillTree(id,value,key) {el(id).replaceChildren(tree(value,key));}
  function tablePairs(pairs) {return pairs.map(([key,value])=>`<span>${esc(key)}</span><span>${esc(value)}</span>`).join("");}
  function renderPeriod(result) {
    const t=result.totals,h=t.duration_s/3600,decided=t.wins+t.losses;
    el("period-rates").textContent=`Battle-hour rates: ${t.xp == null || !h?"—":fmt(t.xp/h)} XP/h · ${t.silver == null || !h?"—":fmt(t.silver/h)} SL/h · Win rate: ${decided?fmt(t.wins/decided*100)+"%":"—"} (${decided} known results)`;
    el("period-vehicles").innerHTML=(result.vehicle_totals || []).map(v=>`<tr><td><a href="${wiki(v.type)}" target="_blank" rel="noopener">${esc(v.name)}</a></td><td>${v.battles}</td><td>${clock(v.duration_s)}</td><td>${dist(v.distance_m)}</td><td>${fmt(v.kills)} / ${fmt(v.deaths)}</td><td>${fmt(v.xp)}</td><td>${fmt(v.silver)}</td></tr>`).join("") || '<tr><td colspan="7">No vehicle records in this period.</td></tr>';
  }
  function renderBattle(record,bridge) {
    data=record;controls=bridge;snapshot=null;eventLimit=100;
    el("event-search").value="";el("event-scope").value="all";el("roster-search").value="";el("parameter-search").value="";
    el("vehicle-gallery").innerHTML=data.summary.vehicles.map(v=>`<details class="vehicle-card detail-section"><summary><img data-unit-image src="${image(v.type)}" alt="${esc(v.name)} in War Thunder" loading="lazy" width="220" height="120"><span class="vehicle-card-title"><i class="route-dot" style="background:${controls.color(v.type)}"></i>${esc(v.name)}</span><span class="vehicle-image-kind">War Thunder Wiki illustration</span><span class="vehicle-card-metrics">${clock(v.duration_s)} · ${dist(v.distance_m)} · ${fmt(v.kills)} / ${fmt(v.deaths)} K/L</span></summary><div class="vehicle-card-body"><div class="snapshot-table">${tablePairs([["Observed runs",v.runs],["Moving / stationary",`${clock(v.moving_s)} / ${clock(v.stationary_s)}`],["Sample mean / max speed",`${fmt(v.average_speed_kmh)} / ${fmt(v.max_speed_kmh)} km/h`],["Position samples",`${fmt(v.position_samples)} / ${fmt(v.samples)}`],["Minimum crew",fmt(v.minimum_crew)],["Vehicle XP / SL",`${fmt(v.xp)} / ${fmt(v.silver)}`]])}</div><div class="detail-actions"><button class="history-button" data-follow="${esc(v.type)}" type="button">Follow route</button><a class="history-button" href="${wiki(v.type)}" target="_blank" rel="noopener">Wiki specifications ↗</a></div></div></details>`).join("");
    setupImages(el("vehicle-gallery"));
    el("battle-vehicles").innerHTML=data.summary.vehicles.map(v=>`<tr><td>${esc(v.name)}</td><td>${v.runs}</td><td>${clock(v.duration_s)}</td><td>${clock(v.moving_s)} / ${clock(v.stationary_s)}</td><td>${dist(v.distance_m)}</td><td>${fmt(v.average_speed_kmh)} / ${fmt(v.max_speed_kmh)} km/h</td><td>${fmt(v.minimum_crew)}</td><td>${fmt(v.kills)} / ${fmt(v.deaths)}</td><td>${fmt(v.xp)}</td><td>${fmt(v.silver)}</td></tr>`).join("");
    el("battle-conditions").innerHTML=data.summary.vehicles.map(v=>`<h3>${esc(v.name)}</h3><table class="history-table"><thead><tr><th>Observed condition</th><th>Duration</th><th>Observed episodes</th></tr></thead><tbody>${Object.entries(v.condition_seconds).map(([key,seconds])=>`<tr><td>${esc(label(key))}</td><td>${clock(seconds)}</td><td>${fmt(v.condition_episodes?.[key])}</td></tr>`).join("") || '<tr><td colspan="3">No such conditions were recorded.</td></tr>'}</tbody></table>`).join("")+'<p class="history-note">Durations and episodes are estimated from telemetry. Conditions can overlap; an episode may already be active at the first sample.</p>';
    const metrics=new Map();
    for(const v of data.summary.vehicles)for(const [key,value] of Object.entries(v.parameters || {}))if(value.numeric_count)metrics.set(key,label(key));
    el("chart-metric").innerHTML=[...metrics].map(([key,name])=>`<option value="${esc(key)}">${esc(name)} (${esc(key.split(".")[0])})</option>`).join("");
    if(metrics.has("indicators.speed"))el("chart-metric").value="indicators.speed";
    const types=[...new Set(data.events.map(e=>e.verb).filter(Boolean))];
    el("event-type").innerHTML='<option value="all">All event types</option>'+types.map(type=>`<option value="${esc(type)}">${esc(type)}</option>`).join("");
    const s=data.session,m=data.summary;
    el("battle-context").innerHTML=`<div class="snapshot-table">${tablePairs([
      ["Battle ID",s.id],["Started (local)",new Date(s.start_ts*1000).toLocaleString("en-GB")],
      ["Ended (local)",s.end_ts?new Date(s.end_ts*1000).toLocaleString("en-GB"):"Still recording"],
      ["Stored telemetry samples",fmt(m.sample_count)],["Samples with own position",`${fmt(m.position_samples)} (${m.sample_count?fmt(m.position_samples/m.sample_count*100):0}%)`],
      ["Recorded combat events",fmt(m.event_count)],["Reward source",s.rewards_source || "Not recorded"],
      ["Rewards observed",s.rewards_ts?new Date(s.rewards_ts*1000).toLocaleString("en-GB"):"Unknown"],
      ["Map background",!s.has_map_image?"Not recorded":s.map_image_verified?"Fresh in-match capture":"Legacy recorded image; not verified"],
      ["Map bounds (metres)",data.map_info?.map_min?`${data.map_info.map_min.join(", ")} → ${data.map_info.map_max.join(", ")}`:"Not recorded"],
    ])}</div>`;
    el("mission-details").innerHTML='<h3>Recorded mission</h3>';
    el("mission-details").append(tree(data.mission,"Mission"),tree(data.map_info,"Map metadata"));
    fillTree("battle-raw",{session:data.session,summary:data.summary,rewards:data.rewards},"Recorded metadata");
    renderRuns();renderRoster();renderEvents();
  }
  function renderRuns() {
    if(!data)return;
    el("run-list").innerHTML=controls.runs().map(run=>`<button type="button" class="run-record" data-seek="${run.start_s}"><i class="route-dot" style="background:${controls.color(run.vehicle)}"></i>${esc(run.name)} · run ${run.spawn}<span>${clock(run.start_s)} → ${clock(run.end_s)} · ${dist(run.distance_m)} · ${run.samples} samples</span></button>`).join("") || '<p class="history-note">No recorded runs for this selection.</p>';
  }
  function setSnapshot(current) {
    snapshot=current;el("sample-open").disabled=!current?.point.sample_id;
    if(!current){el("snapshot-time").textContent="No samples at this time.";el("route-snapshot").replaceChildren();el("route-raw").replaceChildren();return;}
    const {point,run}=current;
    el("snapshot-time").textContent=`${run.name} · run ${run.spawn} · sample at ${clock(point.t)}`;
    el("route-snapshot").innerHTML=tablePairs([["Speed",`${fmt(point.speed)} km/h`],["Remaining crew",fmt(point.crew)],
      ["Gear / engine RPM",`${fmt(point.indicators.gear)} / ${fmt(point.indicators.rpm)}`],
      ["Map position",point.x == null?"Not recorded":`${point.x.toFixed(4)} / ${point.y.toFixed(4)}`],
      ["Sample ID",point.sample_id ?? "Unknown"]]);
    renderParameters();
  }
  function renderParameters() {
    if(!snapshot || !data)return;
    const v=data.summary.vehicles.find(v=>v.type === snapshot.run.vehicle),filter=el("parameter-search").value.toLowerCase();
    const current={};
    for(const namespace of ["indicators","state"])for(const [key,value] of Object.entries(snapshot.point[namespace] || {}))current[namespace+"."+key]=value;
    const entries=Object.entries(v?.parameters || {}).filter(([key])=>`${key} ${label(key)}`.toLowerCase().includes(filter));
    el("route-raw").innerHTML=`<table class="history-table"><thead><tr><th>Parameter</th><th>Now</th><th>Min</th><th>Max</th><th>Sample mean</th><th>Samples</th></tr></thead><tbody>${entries.map(([key,value])=>`<tr><td>${esc(label(key))}<small class="raw-field-name">${esc(key)}</small></td><td>${esc(fmt(current[key]))}</td><td>${fmt(value.min)}</td><td>${fmt(value.max)}</td><td>${fmt(value.mean)}</td><td>${value.count}</td></tr>`).join("") || '<tr><td colspan="6">No fields match this filter.</td></tr>'}</tbody></table>`;
  }
  function renderChart() {
    if(!data || !controls)return;
    const canvas=el("telemetry-chart"),ctx=canvas.getContext("2d"),w=canvas.clientWidth;
    if(!w)return;
    const h=220,ratio=devicePixelRatio || 1;canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);ctx.setTransform(ratio,0,0,ratio,0,0);
    const key=el("chart-metric").value,separator=key.indexOf("."),namespace=key.slice(0,separator),field=key.slice(separator+1);
    const runs=controls.runs(),numbers=runs.flatMap(run=>run.points.map(p=>p[namespace]?.[field])).filter(v=>typeof v === "number" && Number.isFinite(v));
    ctx.fillStyle="#0b0e12";ctx.fillRect(0,0,w,h);ctx.font="11px Segoe UI, sans-serif";
    if(!numbers.length){ctx.fillStyle="#8b9aae";ctx.fillText("No numeric samples for this selection.",15,35);el("chart-caption").textContent="";return;}
    let low=Math.min(...numbers),high=Math.max(...numbers);if(low===high){low-=1;high+=1;}
    const left=58,right=w-15,top=16,bottom=h-30,duration=Math.max(1,controls.duration?.() || data.summary.duration_s);
    const x=t=>left+t/duration*(right-left),y=value=>bottom-(value-low)/(high-low)*(bottom-top);
    ctx.strokeStyle="#232a33";ctx.fillStyle="#7f8a99";
    for(let i=0;i<=4;i++){const value=low+(high-low)*i/4,py=y(value);ctx.beginPath();ctx.moveTo(left,py);ctx.lineTo(right,py);ctx.stroke();ctx.fillText(fmt(value),3,py+4);}
    for(let i=0;i<=4;i++)ctx.fillText(clock(duration*i/4),Math.min(right-30,x(duration*i/4)),h-8);
    for(const run of runs){ctx.beginPath();ctx.lineWidth=1.8;ctx.strokeStyle=controls.color(run.vehicle);let previous=null;
      for(const p of run.points){const value=p[namespace]?.[field];if(typeof value !== "number" || !Number.isFinite(value)){previous=null;continue;}if(previous && p.t-previous.t<=15)ctx.lineTo(x(p.t),y(value));else ctx.moveTo(x(p.t),y(value));previous=p;}ctx.stroke();}
    ctx.strokeStyle="#f1f5fa";ctx.lineWidth=1;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x(controls.time()),top);ctx.lineTo(x(controls.time()),bottom);ctx.stroke();ctx.setLineDash([]);
    el("chart-caption").textContent=`${label(key)} · ${numbers.length} samples · range ${fmt(Math.min(...numbers))}–${fmt(Math.max(...numbers))}. Click the chart to move the playhead; gaps and separate runs are not joined.`;
  }
  function isOwn(name){const player=data?.summary.player;return !!(name && player && (name.toLowerCase()===player.toLowerCase() || name.toLowerCase().endsWith(" "+player.toLowerCase())));}
  function renderEvents() {
    if(!data)return;
    const search=el("event-search").value.toLowerCase(),scope=el("event-scope").value,type=el("event-type").value;
    const lethal=verb=>/destroyed|shot down|knocked out|wrecked|sunk|crashed/i.test(verb || "");
    const events=data.events.filter(event=>(type === "all" || event.verb === type) && (!search || JSON.stringify([event.msg,event.actor_name,event.target_name,event.actor_vehicle,event.target_vehicle]).toLowerCase().includes(search))
      && (scope === "all" || scope === "own" && (isOwn(event.actor_name)||isOwn(event.target_name)) || scope === "kills" && lethal(event.verb)&&isOwn(event.actor_name) || scope === "losses"&&lethal(event.verb)&&isOwn(event.target_name)));
    el("battle-events-title").textContent=`Combat event timeline · ${events.length} / ${data.events.length}`;
    el("events-more").hidden=events.length<=eventLimit;
    el("battle-events").innerHTML=events.slice(0,eventLimit).map(event=>{
      const t=Math.max(0,event.ts-data.session.start_ts);let raw;try{raw=JSON.parse(event.raw_json || "{}");}catch{raw=event.raw_json;}
      return `<details class="battle-event ${isOwn(event.actor_name)||isOwn(event.target_name)?"own-event":""}"><summary><button type="button" class="event-time" data-seek="${t}">${clock(t)}</button><span>${esc(event.msg || "Untitled event")}</span><small>${raw?.source === "clog"?"Game log":"HTTP feed"}</small></summary><div class="event-data"><div class="snapshot-table">${tablePairs([["Recorded at",new Date(event.ts*1000).toLocaleString("en-GB")],["Game clock",event.match_time == null?"Unknown":clock(event.match_time)],["Actor",event.actor_name || "Unknown"],["Actor vehicle",event.actor_vehicle || "Unknown"],["Target",event.target_name || "Unknown"],["Target vehicle",event.target_vehicle || "Unknown"],["Event type",event.verb || event.kind]])}</div>${(data.kill_reviews || []).some(k=>k.event_id===event.id)?`<button type="button" class="history-button" data-review-kill="${event.id}">Review kill on map</button>`:""}<pre>${esc(JSON.stringify(raw,null,2))}</pre></div></details>`;
    }).join("") || '<p class="history-note">No recorded events match this filter. Missing messages cannot be reconstructed from telemetry alone.</p>';
  }
  function renderRoster() {
    if(!data)return;
    const search=el("roster-search").value.toLowerCase(),roster=data.roster || {};
    el("battle-roster").innerHTML=["friendly","enemy","unknown"].map(team=>{
      const players=(roster[team] || []).filter(p=>JSON.stringify(p).toLowerCase().includes(search));
      return `<h3>${team === "friendly"?"Inferred friendly":team === "enemy"?"Inferred enemy":"Unassigned"} · ${players.length}</h3><table class="history-table"><thead><tr><th>Player</th><th>Observed vehicles / losses</th><th>Last game time</th></tr></thead><tbody>${players.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.vehicles.map(v=>`${esc(v.vehicle)} (${v.deaths})`).join(" · ")}</td><td>${p.last_time == null?"—":clock(p.last_time)}</td></tr>`).join("") || '<tr><td colspan="3">No matching players recorded.</td></tr>'}</tbody></table>`;
    }).join("");
  }
  async function openSample(sampleId=snapshot?.point.sample_id) {
    if(!sampleId)return;
    const id=sampleId,button=el("sample-open"),battle=data.session.id;
    button.disabled=true;
    try {
      const response=await fetch(`/api/history/${battle}/samples/${id}`);if(!response.ok)throw new Error("Sample could not be loaded.");
      sampleData=await response.json();el("sample-title").textContent=`Battle #${battle} · sample #${id}`;
      fillTree("sample-content",sampleData,"Complete sample");el("sample-dialog").showModal();
    } catch(error){el("snapshot-time").textContent=error.message;}finally{button.disabled=false;}
  }
  el("vehicle-gallery").addEventListener("click",event=>{const button=event.target.closest("[data-follow]");if(button){controls.selectVehicle(button.dataset.follow);el("route-canvas").scrollIntoView({behavior:"smooth",block:"center"});}});
  el("parameter-search").addEventListener("input",renderParameters);
  el("roster-search").addEventListener("input",renderRoster);
  for(const id of ["event-search","event-scope","event-type"])el(id).addEventListener(id==="event-search"?"input":"change",()=>{eventLimit=100;renderEvents();});
  el("events-more").addEventListener("click",()=>{eventLimit+=100;renderEvents();});
  for(const id of ["run-list","battle-events"])el(id).addEventListener("click",event=>{const button=event.target.closest("[data-seek]");if(button){event.preventDefault();controls.seek(Number(button.dataset.seek));}});
  el("chart-metric").addEventListener("change",renderChart);
  el("telemetry-chart").addEventListener("click",event=>{if(!data)return;const r=event.currentTarget.getBoundingClientRect();controls.seek(Math.max(0,Math.min(1,(event.clientX-r.left-58)/(r.width-73)))*(controls.duration?.() || data.summary.duration_s));});
  el("sample-open").addEventListener("click",()=>openSample());
  el("battle-events").addEventListener("click",event=>{const button=event.target.closest("[data-review-kill]");if(button)window.HistoryCombat.select(Number(button.dataset.reviewKill),true);});
  el("sample-close").addEventListener("click",()=>el("sample-dialog").close());
  el("sample-download").addEventListener("click",()=>{if(!sampleData)return;const url=URL.createObjectURL(new Blob([JSON.stringify(sampleData,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download=`battle-${data.session.id}-sample-${sampleData.id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  for(const [id,open] of [["details-expand",true],["details-collapse",false]])el(id).addEventListener("click",()=>el("battle-detail").querySelectorAll("details.detail-section").forEach(section=>{section.open=open;}));
  return {renderPeriod,renderBattle,setSnapshot,renderChart,renderRuns,openSample};
})();
