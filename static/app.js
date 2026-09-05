document.addEventListener("DOMContentLoaded", () => {
  // Global State
  let sampleNotices = [];
  let currentPipelineResult = null;
  let actionHistory = [];
  let dataIndex = null;

  // DOM Elements
  const sampleSelect = document.getElementById("sample-notice-select");
  const noticeTextarea = document.getElementById("notice-textarea");
  const btnAnalyze = document.getElementById("btn-analyze");
  const btnAnalyzeText = document.getElementById("btn-analyze-text");
  const analyzeSpinner = document.getElementById("analyze-spinner");
  const noticeMetaCard = document.getElementById("notice-meta-card");
  const metaCategory = document.getElementById("meta-category");
  const metaDesc = document.getElementById("meta-desc");
  const statusPill = document.getElementById("system-status-pill");
  const statusText = document.getElementById("status-text");

  const emptyState = document.getElementById("empty-state");
  const noImpactAlert = document.getElementById("no-impact-alert");
  const alertTitle = document.getElementById("alert-title");
  const alertBody = document.getElementById("alert-body");
  const alertTags = document.getElementById("alert-tags");
  const calloutBadgeText = document.getElementById("callout-badge-text");

  const pipelineDetailsContainer = document.getElementById("pipeline-details-container");
  const headlineText = document.getElementById("headline-text");
  const stage1Summary = document.getElementById("stage1-summary");
  const stage2Summary = document.getElementById("stage2-summary");

  const actionCardsSection = document.getElementById("action-cards-section");
  const actionCardsList = document.getElementById("action-cards-list");

  const auditModal = document.getElementById("audit-modal");
  const btnOpenAudit = document.getElementById("btn-open-audit");
  const btnCloseAudit = document.getElementById("btn-close-audit");
  const auditTableBody = document.getElementById("audit-table-body");
  const auditCount = document.getElementById("audit-count");

  const indexModal = document.getElementById("index-modal");
  const btnOpenIndex = document.getElementById("btn-open-index");
  const btnCloseIndex = document.getElementById("btn-close-index");
  const dataIndexJson = document.getElementById("data-index-json");

  // Trace strip steps
  const traceStep1 = document.getElementById("trace-step-1");
  const traceStep2 = document.getElementById("trace-step-2");
  const traceStep3 = document.getElementById("trace-step-3");
  const traceStep4 = document.getElementById("trace-step-4");
  const traceStep5 = document.getElementById("trace-step-5");

  // Initialize Console
  initHealthCheck();
  initSampleNotices();
  initDataIndex();
  initEventListeners();

  async function initHealthCheck() {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      if (data.status === "online") {
        statusPill.classList.add("active");
        if (data.gemini_api_configured) {
          statusText.textContent = "Gemini LLM active";
        } else {
          statusText.textContent = "Offline fallback active";
        }
      }
    } catch (e) {
      statusPill.classList.add("offline");
      statusText.textContent = "System offline";
    }
  }

  async function initSampleNotices() {
    try {
      const res = await fetch("/api/sample-notices");
      const data = await res.json();
      sampleNotices = data.notices || [];

      sampleSelect.innerHTML = '<option value="">Choose a sample disruption notice...</option>';
      sampleNotices.forEach(n => {
        const opt = document.createElement("option");
        opt.value = n.id;
        opt.textContent = `[${n.category}] ${n.title}`;
        sampleSelect.appendChild(opt);
      });
    } catch (e) {
      console.error("Failed to load sample notices", e);
    }
  }

  async function initDataIndex() {
    try {
      const res = await fetch("/api/data-index");
      dataIndex = await res.json();
    } catch (e) {
      console.error("Failed to load data index", e);
    }
  }

  function initEventListeners() {
    sampleSelect.addEventListener("change", (e) => {
      const selectedId = e.target.value;
      if (!selectedId) {
        noticeMetaCard.style.display = "none";
        return;
      }
      const match = sampleNotices.find(n => n.id === selectedId);
      if (match) {
        noticeTextarea.value = match.text;
        metaCategory.textContent = match.category;
        metaDesc.textContent = match.title;
        noticeMetaCard.style.display = "block";
      }
    });

    btnAnalyze.addEventListener("click", runAnalysis);

    btnOpenAudit.addEventListener("click", () => {
      fetchAuditHistory();
      auditModal.style.display = "flex";
    });

    btnCloseAudit.addEventListener("click", () => {
      auditModal.style.display = "none";
    });

    btnOpenIndex.addEventListener("click", () => {
      renderDataIndexTab("tab-suppliers");
      indexModal.style.display = "flex";
    });

    btnCloseIndex.addEventListener("click", () => {
      indexModal.style.display = "none";
    });

    document.querySelectorAll(".tab-item").forEach(btn => {
      btn.addEventListener("click", (e) => {
        document.querySelectorAll(".tab-item").forEach(b => b.classList.remove("active"));
        e.target.classList.add("active");
        renderDataIndexTab(e.target.dataset.tab);
      });
    });
  }

  function renderDataIndexTab(tabKey) {
    if (!dataIndex) return;
    let key = "suppliers";
    if (tabKey === "tab-shipments") key = "shipments";
    if (tabKey === "tab-stock") key = "stock";
    if (tabKey === "tab-orders") key = "orders";

    dataIndexJson.textContent = JSON.stringify(dataIndex[key], null, 2);
  }

  function resetTraceStrip() {
    [traceStep1, traceStep2, traceStep3, traceStep4, traceStep5].forEach(step => {
      step.classList.remove("active", "dimmed");
    });
  }

  async function runAnalysis() {
    const text = noticeTextarea.value.trim();
    if (!text) {
      alert("Please enter or select a disruption notice first.");
      return;
    }

    btnAnalyze.disabled = true;
    analyzeSpinner.style.display = "inline-block";
    btnAnalyzeText.textContent = "Processing pipeline...";

    emptyState.style.display = "none";
    noImpactAlert.style.display = "none";
    pipelineDetailsContainer.style.display = "none";
    actionCardsSection.style.display = "none";

    resetTraceStrip();
    traceStep1.classList.add("active");

    // Check prefers-reduced-motion
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (!prefersReducedMotion) {
      await new Promise(r => setTimeout(r, 120));
      traceStep2.classList.add("active");
    } else {
      traceStep2.classList.add("active");
    }

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notice_text: text })
      });
      const data = await res.json();
      currentPipelineResult = data;

      renderPipelineResult(data, prefersReducedMotion);
    } catch (e) {
      alert("Error analyzing disruption notice: " + e.message);
    } finally {
      btnAnalyze.disabled = false;
      analyzeSpinner.style.display = "none";
      btnAnalyzeText.textContent = "Run impact pipeline";
    }
  }

  function renderPipelineResult(data, prefersReducedMotion) {
    const isShortCircuited = data.short_circuited;
    const stage1 = data.stage1 || {};
    const stage2 = data.stage2 || {};
    const stage3 = data.stage3 || {};
    const stage4 = data.stage4 || {};

    // Match found check
    if (!data.match_found || isShortCircuited) {
      // VISUALLY OBVIOUS SHORT-CIRCUIT: Steps 1 & 2 fill in, Steps 3, 4, 5 stay dimmed!
      traceStep1.classList.add("active");
      traceStep2.classList.add("active");
      traceStep3.classList.add("dimmed");
      traceStep4.classList.add("dimmed");
      traceStep5.classList.add("dimmed");

      noImpactAlert.style.display = "flex";
      noImpactAlert.className = "resolved-callout-card short-circuit";
      calloutBadgeText.textContent = "No match identified";
      alertTitle.textContent = "No matching distributor record found in database";
      alertBody.textContent = "Disruption notice text was processed through local vector retrieval and Stage 1 entity resolution. No matching supplier, shipment, or stock item was identified in distributor database records.";
      alertTags.innerHTML = `
        <span>Retrieval similarity score: ${(stage1.retrieval_meta ? stage1.retrieval_meta.best_similarity : 0).toFixed(2)}</span>
        <span>Stage 1 short-circuit executed</span>
      `;
      return;
    }

    // Full match found: activate all steps
    [traceStep1, traceStep2, traceStep3, traceStep4, traceStep5].forEach(s => s.classList.add("active"));

    // Check No Impact vs Impact
    if (stage4.no_impact || (stage3.total_orders_affected === 0)) {
      noImpactAlert.style.display = "flex";
      noImpactAlert.className = "resolved-callout-card";
      calloutBadgeText.textContent = "Resolved clear";
      alertTitle.textContent = "Zero pending customer orders affected by this disruption";
      alertBody.textContent = stage4.headline || "Disruption notice was matched to supplier records and traced through active shipments and inventory records. Zero pending customer orders are affected because warehouse stock levels are sufficient to cover current demand.";
      alertTags.innerHTML = `
        <span>Entity matched: ${(stage1.candidate_matches && stage1.candidate_matches[0] ? stage1.candidate_matches[0].entity_id : '-')}</span>
        <span>Graph traversal confirmed zero shortfall</span>
      `;
    } else {
      pipelineDetailsContainer.style.display = "flex";
      headlineText.textContent = stage4.headline || `Disruption impacts ${stage2.total_orders_affected} order(s) totaling $${(stage2.total_at_risk_value || 0).toLocaleString()} at risk.`;

      stage1Summary.textContent = `${(stage1.candidate_matches || []).length} entity candidate(s) matched (${stage1.notice_summary || ''}).`;
      stage2Summary.textContent = `${stage2.total_orders_affected || 0} order(s) affected across ${(stage2.affected_skus || []).length} SKU(s). Total at risk: $${(stage2.total_at_risk_value || 0).toLocaleString()}.`;

      renderLedgerManifest(stage4.affected_orders || []);
    }
  }

  function renderLedgerManifest(orders) {
    actionCardsSection.style.display = "flex";
    actionCardsList.innerHTML = "";

    orders.forEach(ord => {
      const row = document.createElement("div");
      row.className = "ledger-row";
      row.dataset.orderId = ord.order_id;

      const isUrgent = ord.urgency_score > 60;
      const scoreClass = isUrgent ? "urgent" : "steady";

      let optionsHtml = '<div class="inline-options-list">';
      (ord.options || []).forEach(opt => {
        const isRec = opt.action === ord.recommended_option;
        optionsHtml += `
          <div class="inline-option-item ${isRec ? 'recommended' : ''}">
            <div class="opt-name">
              ${formatOptionName(opt.action)}
              ${isRec ? '<span class="opt-recommended-flag">Recommended</span>' : ''}
            </div>
            <div class="opt-tradeoff">${opt.tradeoff}</div>
          </div>
        `;
      });
      optionsHtml += '</div>';

      const approveActionText = getActionText(ord.recommended_option);

      row.innerHTML = `
        <div class="ledger-cell">
          <span class="ledger-order-id" onclick="inspectRecord('${ord.order_id}')">${ord.order_id}</span>
        </div>
        <div class="ledger-cell">
          <span class="ledger-customer">${ord.customer_name || ord.order_id}</span>
          <span class="ledger-tier">${ord.customer_tier} Tier</span>
        </div>
        <div class="ledger-cell">
          <span class="ledger-score ${scoreClass}">${ord.urgency_score}</span>
          <span class="score-caption">Urgency score</span>
        </div>
        <div class="ledger-detail">
          <div class="shortfall-summary-text">${formatShortfallSummary(ord.shortfall_summary)}</div>
          ${optionsHtml}
          <div class="ledger-row-actions">
            <span class="reason-text">${ord.recommendation_reason}</span>
            <button class="btn btn-action-approve" onclick="handleDecision('${ord.order_id}', '${ord.recommended_option}', 'APPROVED')">${approveActionText}</button>
            <button class="btn btn-action-reject" onclick="handleDecision('${ord.order_id}', '${ord.recommended_option}', 'REJECTED')">Reject option</button>
          </div>
        </div>
      `;

      actionCardsList.appendChild(row);
    });
  }

  function formatOptionName(actionKey) {
    if (actionKey === "expedite") return "Expedite air freight replacement";
    if (actionKey === "part_ship") return "Part-ship available stock immediately";
    if (actionKey === "reallocate") return "Reallocate warehouse safety stock";
    if (actionKey === "notify_customer") return "Notify customer & reschedule delivery";
    return actionKey;
  }

  function getActionText(actionKey) {
    if (actionKey === "expedite") return "Approve expedite air freight";
    if (actionKey === "part_ship") return "Approve partial shipment";
    if (actionKey === "reallocate") return "Approve safety stock reallocation";
    if (actionKey === "notify_customer") return "Approve customer notification";
    return "Approve action";
  }

  function formatShortfallSummary(summaryText) {
    if (!summaryText) return "";
    // Wrap record IDs like ORD-5001, SHP-2002, SKU-1002 in monospace record tags
    return summaryText.replace(/\b(ORD-\d+|SHP-\d+|SKU-\d+|SUP-\d+|CUST-\d+)\b/g, '<span class="record-tag" onclick="inspectRecord(\'$1\')">$1</span>');
  }

  window.inspectRecord = function(recordId) {
    if (!dataIndex) return;
    if (recordId.startsWith("ORD-")) {
      const ord = dataIndex.orders.find(o => o.order_id === recordId);
      if (ord) {
        alert(`Order ${recordId}:\nCustomer: ${ord.customer_name} (${ord.customer_tier})\nSKU: ${ord.sku} (${ord.sku_name})\nQuantity: ${ord.qty}\nValue: $${ord.order_value}\nPromised date: ${ord.promised_date}`);
      }
    } else if (recordId.startsWith("SKU-")) {
      const st = dataIndex.stock.find(s => s.sku === recordId);
      if (st) {
        alert(`Stock item ${recordId}:\nName: ${st.name}\nOn hand: ${st.on_hand}\nReserved: ${st.reserved}\nSafety stock: ${st.safety_stock}\nUnit cost: $${st.unit_cost}`);
      }
    } else if (recordId.startsWith("SHP-")) {
      const shp = dataIndex.shipments.find(s => s.shipment_id === recordId);
      if (shp) {
        alert(`Shipment ${recordId}:\nSupplier: ${shp.supplier_id}\nSKU: ${shp.sku}\nQuantity: ${shp.qty}\nCarrier: ${shp.carrier}\nETA: ${shp.eta}`);
      }
    }
  };

  window.handleDecision = async function(orderId, action, decision) {
    const endpoint = decision === "APPROVED" ? "/api/action/approve" : "/api/action/reject";
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_id: orderId,
          action: action,
          operator_notes: `${decision} by operator.`
        })
      });
      await res.json();

      const row = document.querySelector(`.ledger-row[data-order-id="${orderId}"]`);
      if (row) {
        row.style.opacity = "0.5";
      }

      fetchAuditHistory();
    } catch (e) {
      alert("Error recording action: " + e.message);
    }
  };

  async function fetchAuditHistory() {
    try {
      const res = await fetch("/api/action/history");
      const data = await res.json();
      actionHistory = data.history || [];
      auditCount.textContent = actionHistory.length;

      if (actionHistory.length === 0) {
        auditTableBody.innerHTML = '<tr><td colspan="6" class="text-muted text-center">No decisions recorded in current session.</td></tr>';
        return;
      }

      let html = "";
      actionHistory.forEach(a => {
        html += `
          <tr>
            <td class="mono-val">${a.id}</td>
            <td class="mono-val">${a.timestamp}</td>
            <td class="mono-val">${a.order_id}</td>
            <td>${a.chosen_action}</td>
            <td>${a.status}</td>
            <td>${a.operator_notes}</td>
          </tr>
        `;
      });
      auditTableBody.innerHTML = html;
    } catch (e) {
      console.error("Failed to fetch audit history", e);
    }
  }
});
