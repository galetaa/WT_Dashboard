/* Kill-notification positions, explicit evidence and optional estimated connections. */
window.HistoryCombat=(()=>{
  'use strict';
  const el=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=v=>v==null?'—':typeof v==='number'?v.toLocaleString('en-GB',{maximumFractionDigits:2}):String(v);
  const clock=t=>{const s=Math.max(0,Math.round(t));return`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;};
  let record=null,bridge=null,current=null;
  const kills=()=>record?.kill_reviews||[];
  function renderBattle(data,controls){record=data;bridge=controls;current=null;
    el('kill-select').innerHTML='<option value="">Select a kill…</option>'+kills().map(k=>`<option value="${k.event_id}">#${k.number} · ${clock(k.t)} · ${esc(k.event.target_vehicle||k.event.target_name||'Unknown target')}</option>`).join('');
    el('kill-select').disabled=!kills().length;
    el('kill-coverage').textContent=`${kills().filter(k=>k.origin).length}/${kills().length} positions`;
    el('kill-list-title').textContent=`Kills in this battle · ${kills().length}`;
    el('kill-list').innerHTML=kills().map(k=>`<button class="kill-entry" type="button" data-kill-id="${k.event_id}"><b>#${k.number} · ${clock(k.t)}</b><span>${esc(k.event.actor_vehicle||'Unknown vehicle')} → ${esc(k.event.target_vehicle||'Unknown vehicle')}</span><small>${esc(k.event.target_name||'Unknown player')} · ${k.origin?'Own position recorded':'Position unavailable'}${k.target?' · '+(k.target.method==='named_marker'?'Named target marker':'Estimated target marker'):''}</small></button>`).join('')||'<p class="history-note">No local-player kills could be established from this battle’s saved combat feed.</p>';
    renderDetails();
  }
  function select(id,focus=false){current=kills().find(k=>k.event_id===id)||null;el('kill-select').value=current?String(current.event_id):'';renderDetails();
    if(current&&focus)bridge.focus(current);else if(current)bridge.seek(current.t);else bridge.redraw();
    document.querySelectorAll('[data-kill-id]').forEach(b=>b.classList.toggle('selected',Number(b.dataset.killId)===current?.event_id));
  }
  function renderDetails(){const k=current;el('kill-focus').disabled=!k?.origin;el('kill-sample').disabled=!k?.sample_id;el('kill-previous').disabled=!kills().length;el('kill-next').disabled=!kills().length;
    if(!k){el('kill-details').innerHTML='<p class="history-note">Select a numbered map marker, a kill below, or “Review kill on map” in the combat timeline.</p>';return;}
    const i=k.snapshot?.indicators||{};
    const pairs=[['Kill',`#${k.number} · ${clock(k.t)}`],['Attacker',k.event.actor_name],['Your credited vehicle',k.event.actor_vehicle],['Target player',k.event.target_name],['Target vehicle',k.event.target_vehicle],['Outcome',k.event.verb],['Recorded time',new Date(k.event.ts*1000).toLocaleString('en-GB')],['Time source',k.timestamp_basis==='game_log'?'Game log timestamp':'HTTP message received; delivery can be delayed'],['Sample offset',k.sample_age_s==null?'No nearby sample':`${fmt(k.sample_age_s)} s before notification`],['Own map position',k.origin?`${k.origin.x.toFixed(5)} / ${k.origin.y.toFixed(5)}`:'Not recorded'],['Target position',k.target?`${k.target.x.toFixed(5)} / ${k.target.y.toFixed(5)} · ${k.target.confidence}`:'Not identifiable'],['2D map separation',k.line?.distance_m==null?'Unknown':`${fmt(k.line.distance_m)} m (estimated)`],['Signed speed / gear',`${fmt(i.speed)} km/h / ${fmt(i.gear)}`],['Crew / ready-rack ammo',`${fmt(i.crew_current)} / ${fmt(i.first_stage_ammo)}`]];
    el('kill-details').innerHTML=`<div class="snapshot-table">${pairs.map(([a,b])=>`<span>${esc(a)}</span><span>${esc(fmt(b))}</span>`).join('')}</div><p class="history-note">${esc(k.origin_note)} ${esc(k.target_note)} ${esc(k.line?.note||k.trajectory_note)}</p>${k.related_events?.length?`<details><summary>Related recorded messages · ${k.related_events.length}</summary>${k.related_events.map(e=>`<p class="history-note">${clock(Math.max(0,e.ts-record.session.start_ts))} · ${esc(e.msg)}</p>`).join('')}</details>`:''}<details><summary>Exact recorded kill message</summary><pre>${esc(k.event.msg)}</pre><pre>${esc(JSON.stringify(k.event,null,2))}</pre></details>`;
  }
  function visible(runs,until){const ids=new Set(runs.flatMap(r=>r.points.map(p=>p.sample_id)));
    return kills().filter(k=>k.origin&&k.t<=until+.0051&&ids.has(k.sample_id));
  }
  function layout(runs,until,scale){const placed=[];
    for(const k of visible(runs,until)){let x=k.origin.x,y=k.origin.y;const occupied=(a,b)=>placed.some(p=>Math.hypot(p.x-a,p.y-b)<22*scale);
      if(occupied(x,y)){let found=false;for(let ring=1;ring<=6&&!found;ring++)for(let i=0;i<12;i++){const angle=i*Math.PI/6,a=k.origin.x+Math.cos(angle)*24*ring*scale,b=k.origin.y+Math.sin(angle)*24*ring*scale;if(a>=0&&a<=1&&b>=0&&b<=1&&!occupied(a,b)){x=a;y=b;found=true;break;}}}
      placed.push({kill:k,x,y});
    }return placed;
  }
  function draw(ctx,width,zoom,until,runs){if(!el('map-kills').checked)return;const css=el('route-canvas').getBoundingClientRect().width||width,unit=width/css/zoom;
    for(const marker of layout(runs,until,unit/width)){const k=marker.kill,selected=current?.event_id===k.event_id,origin=k.origin;
      if(k.line&&k.target&&el('map-kill-lines').checked){ctx.strokeStyle=selected?'#fff2b0':'#ffc96c';ctx.lineWidth=(selected?2:1.4)*unit;ctx.setLineDash([6*unit,5*unit]);ctx.beginPath();ctx.moveTo(origin.x*width,origin.y*width);ctx.lineTo(k.target.x*width,k.target.y*width);ctx.stroke();ctx.setLineDash([]);const x=k.target.x*width,y=k.target.y*width;ctx.beginPath();ctx.moveTo(x-5*unit,y-5*unit);ctx.lineTo(x+5*unit,y+5*unit);ctx.moveTo(x+5*unit,y-5*unit);ctx.lineTo(x-5*unit,y+5*unit);ctx.stroke();}
      if(marker.x!==origin.x||marker.y!==origin.y){ctx.strokeStyle='#ffe3a6';ctx.lineWidth=unit;ctx.beginPath();ctx.moveTo(origin.x*width,origin.y*width);ctx.lineTo(marker.x*width,marker.y*width);ctx.stroke();ctx.fillStyle='#ffe3a6';ctx.beginPath();ctx.arc(origin.x*width,origin.y*width,2*unit,0,Math.PI*2);ctx.fill();}
      ctx.fillStyle=selected?'#ffe5a0':'#bd7731';ctx.strokeStyle=selected?'#fff':'#ffe3a6';ctx.lineWidth=(selected?2.5:1.5)*unit;ctx.beginPath();ctx.arc(marker.x*width,marker.y*width,(selected?11:9)*unit,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.fillStyle='#10151c';ctx.font=`bold ${10*unit}px Segoe UI,sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(k.number),marker.x*width,marker.y*width);ctx.textAlign='left';ctx.textBaseline='alphabetic';
    }
  }
  function hitTest(x,y,radius,until,runs,zoom){const scale=1/(el('route-canvas').clientWidth*zoom);let found=null,best=radius**2;for(const marker of layout(runs,until,scale)){const distance=(marker.x-x)**2+(marker.y-y)**2;if(distance<best){found=marker.kill;best=distance;}}return el('map-kills').checked?found:null;}
  el('kill-select').addEventListener('change',()=>select(Number(el('kill-select').value),true));
  el('kill-list').addEventListener('click',e=>{const b=e.target.closest('[data-kill-id]');if(b)select(Number(b.dataset.killId),true);});
  for(const [id,step]of[['kill-previous',-1],['kill-next',1]])el(id).addEventListener('click',()=>{const all=kills();if(all.length){const index=current?all.indexOf(current):-1;select(all[(index+step+all.length)%all.length].event_id,true);}});
  el('kill-focus').addEventListener('click',()=>{if(current)bridge.focus(current);});
  el('kill-sample').addEventListener('click',()=>{if(current?.sample_id)window.HistoryInspector.openSample(current.sample_id);});
  for(const id of['map-kills','map-kill-lines'])el(id).addEventListener('change',()=>bridge?.redraw());
  return{renderBattle,draw,hitTest,select};
})();
