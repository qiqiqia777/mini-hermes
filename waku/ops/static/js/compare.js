// waku dashboard — Model arena: race ONE message through several models at once.
// Split out of app.js: classic <script>, shared global scope (no build step,
// no modules). Loads after views.js so it can hang a page onto VIEWS.
//
// Each contestant runs server-side in its own throwaway home (see
// compare_models in dashboard.py) — this is a benchmark, not a conversation, so
// nothing here touches your real memory or calendar.

// State survives the 5s refresh redraw (the view rebuilds from here).
let compareState = { message: "Build a Kanto team around Pikachu — search current picks, remember it, and schedule two training sessions this week.",
                     picked: null, running: false, results: null };

// Which models are offered: your pinned shortlist (models.json). Default-pick
// the first (flagship) of each provider so the race is one brain per lab.
function compareModels(d){
  const pinned = ((d.settings && d.settings.pinned) || []);
  if (compareState.picked === null){
    const seen = new Set();
    compareState.picked = new Set(pinned.filter(p => {
      const first = !seen.has(p.provider); seen.add(p.provider); return first;
    }).map(p => `${p.provider}:${p.model}`));
  }
  return pinned;
}

function toggleCompareModel(spec){
  const s = compareState.picked;
  s.has(spec) ? s.delete(spec) : s.add(spec);
  render();
}

async function runCompare(){
  const specs = [...compareState.picked];
  if (!compareState.message.trim() || !specs.length || compareState.running) return;
  editing = false;   // release the typing lock so the racing/results redraws show
  compareState.running = true; compareState.results = null; render();
  const r = await postJSON("/api/compare", {message: compareState.message, models: specs});
  compareState.running = false;
  compareState.results = r.error ? {error: r.error} : r.results;
  render();
}

// One contestant's result column. Reuses the shared formatters (gateBadge/
// toolRow/renderMarkdown/secs/money) so it reads like the chat cards.
function compareCol(res){
  if (res.error) return `<div class="cmp-col err"><div class="cmp-h"><code>${esc(res.model)}</code>
    <span class="srcpill apple">error</span></div><div class="meta">${esc(res.error)}</div></div>`;
  const tools = (res.tools||[]).map(t => `<span class="stage done">tool · ${esc(t.tool)}</span>`).join("");
  return `<div class="cmp-col">
    <div class="cmp-h"><span class="mm-prov">${esc(res.provider)}</span> <code>${esc(res.model)}</code></div>
    <div class="cmp-stats">
      <span class="badge ${res.gate&&res.gate.decision==="retrieve"?"retrieve":""}">gate · ${esc(res.gate?res.gate.decision:"—")}</span>
      <span class="chip">${secs(res.latency_ms)}</span>
      <span class="chip">${res.iterations??"?"} iter</span>
      <span class="chip money">${money(res.cost_usd||0)}</span>
      <span class="chip">${(res.tokens_in||0)+(res.tokens_out||0)} tok</span>
    </div>
    ${tools?`<div class="stages" style="flex-wrap:wrap">${tools}</div>`:""}
    <div class="r cmp-reply">${renderMarkdown(res.reply||"")}</div>
  </div>`;
}

VIEWS.compare = function(d){
  const pinned = compareModels(d);
  const chips = pinned.length ? pinned.map(p => {
    const spec = `${p.provider}:${p.model}`, on = compareState.picked.has(spec);
    return `<label class="cmp-pick ${on?"on":""}"><input type="checkbox" ${on?"checked":""}
      onchange="toggleCompareModel('${esc(spec)}')"> <span class="mm-prov">${esc(p.provider)}</span> ${esc(p.model)}</label>`;
  }).join("") : `<div class="meta">No models pinned yet — add some in Settings.</div>`;
  const n = compareState.picked ? compareState.picked.size : 0;

  let grid = "";
  if (compareState.running){
    grid = `<div class="cmp-grid">${[...compareState.picked].map(s =>
      `<div class="cmp-col"><div class="cmp-h"><code>${esc(s.split(":")[1])}</code></div>
       <div class="meta">racing… <span class="caret"></span></div></div>`).join("")}</div>`;
  } else if (compareState.results){
    if (compareState.results.error) grid = `<div class="card empty">Error: ${esc(compareState.results.error)}</div>`;
    else {
      const rows = compareState.results;
      const fastest = Math.min(...rows.filter(r=>!r.error).map(r=>r.latency_ms));
      const cheapest = Math.min(...rows.filter(r=>!r.error).map(r=>r.cost_usd||0));
      grid = `<div class="meta" style="margin:2px 0 8px">Isolated temp runs — nothing saved to your data.
        Fastest: <b>${secs(fastest)}</b> · Cheapest: <b>${money(cheapest)}</b></div>
        <div class="cmp-grid">${rows.map(compareCol).join("")}</div>`;
    }
  }

  return `<div class="card">
    <div class="meta" style="margin-bottom:6px">One message, every brain at once — same harness, isolated homes, real receipts (gate · latency · cost · tools). Compare, don't guess.</div>
    <textarea id="cmp-msg" class="cmp-input" rows="2" onfocus="markEditing()"
      oninput="compareState.message=this.value">${esc(compareState.message)}</textarea>
    <div class="cmp-picks">${chips}</div>
    <div style="margin-top:10px">
      <button class="save" onclick="runCompare()" ${(!n||compareState.running)?"disabled":""}>
        ${compareState.running?"Racing…":`Race ${n} model${n===1?"":"s"}`}</button>
    </div>
  </div>${grid}`;
};
