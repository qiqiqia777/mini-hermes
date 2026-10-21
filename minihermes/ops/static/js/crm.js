// The CRM page reads independently from the dashboard's five-second /api/data poll.
const crmState = {
  opportunities: [],
  selectedId: null,
  loading: false,
  loaded: false,
  error: "",
};

async function loadCrmOpportunities(force = false) {
  if (crmState.loading || (crmState.loaded && !force)) return;

  crmState.loading = true;
  crmState.error = "";
  crmState.opportunities = [];
  crmState.selectedId = null;
  if (activeView === "crm") render();

  try {
    const response = await fetch("/api/crm/opportunities", {
      headers: {Accept: "application/json"},
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload?.error || `Request failed (HTTP ${response.status}).`);
    }
    if (!payload || !Array.isArray(payload.opportunities)) {
      throw new Error("The CRM response did not contain an opportunity list.");
    }
    crmState.opportunities = payload.opportunities;
  } catch (error) {
    crmState.error = error?.message || "Could not load CRM opportunities.";
  } finally {
    crmState.loading = false;
    crmState.loaded = true;
    if (activeView === "crm") render();
  }
}

function selectCrmOpportunity(id) {
  crmState.selectedId = Number(id);
  render();
}

function crmOpportunityCard(opportunity) {
  const selected = Number(opportunity.id) === crmState.selectedId;
  return `<button type="button" class="crm-opportunity${selected ? " selected" : ""}"
      aria-pressed="${selected}" onclick="selectCrmOpportunity(${Number(opportunity.id)})">
    <span class="crm-opportunity-name">${esc(opportunity.name)}</span>
    <span class="crm-opportunity-meta">Customer: ${esc(opportunity.customer_name || "No customer linked")}</span>
    <span class="crm-opportunity-meta">Stage: ${esc(opportunity.stage_name || "No stage")}</span>
  </button>`;
}

function crmOpportunityDetails(opportunity) {
  if (!opportunity) {
    return `<div class="card empty">Select an opportunity to see its details.</div>`;
  }
  return `<div class="card crm-detail-card">
    <div class="meta">Selected opportunity</div>
    <h2>${esc(opportunity.name)}</h2>
    <div class="crm-detail-row"><span>Customer</span><b>${esc(opportunity.customer_name || "No customer linked")}</b></div>
    <div class="crm-detail-row"><span>Stage</span><b>${esc(opportunity.stage_name || "No stage")}</b></div>
  </div>`;
}

function renderCrm() {
  const header = `<div class="crm-toolbar">
    <div><h2>Odoo opportunities</h2>
      <div class="meta">Read-only CRM records. Selecting an opportunity does not change Odoo.</div></div>
    <button class="save" type="button" onclick="loadCrmOpportunities(true)" ${crmState.loading ? "disabled" : ""}>Reload</button>
  </div>`;

  if (crmState.loading) {
    return header + `<div class="card empty" role="status">Loading opportunities…</div>`;
  }
  if (crmState.error) {
    return header + `<div class="card crm-error" role="alert">
      <b>Could not load opportunities</b><div class="meta">${esc(crmState.error)}</div>
      <button class="save" type="button" onclick="loadCrmOpportunities(true)">Retry</button>
    </div>`;
  }
  if (!crmState.opportunities.length) {
    return header + `<div class="card empty">No opportunities found in Odoo.</div>`;
  }

  const selected = crmState.opportunities.find(
    opportunity => Number(opportunity.id) === crmState.selectedId,
  );
  return header + `<div class="crm-layout">
    <div class="crm-list" aria-label="Odoo opportunities">
      ${crmState.opportunities.map(crmOpportunityCard).join("")}
    </div>
    <div class="crm-detail">${crmOpportunityDetails(selected)}</div>
  </div>`;
}

VIEWS.crm = function () {
  if (!crmState.loaded && !crmState.loading) loadCrmOpportunities();
  return renderCrm();
};
