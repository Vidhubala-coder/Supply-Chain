document.addEventListener("DOMContentLoaded", () => {
  // Global State
  let sampleNotices = [];
  let currentPipelineResult = null;
  let actionHistory = [];
  let dataIndex = null;
  let typewriterInterval = null;
  let fullNarrationText = "";
  let pendingEscalations = [];

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

  // KPI Strip Elements
  const kpiOrdersAffected = document.getElementById("kpi-orders-affected");
  const kpiTotalRisk = document.getElementById("kpi-total-risk");
  const kpiCostAtRisk = document.getElementById("kpi-cost-at-risk");
  const kpiNearestDeadline = document.getElementById("kpi-nearest-deadline");

  const segGood = document.getElementById("seg-good");
  const segWarn = document.getElementById("seg-warn");
  const segCritical = document.getElementById("seg-critical");
  const legendGoodCount = document.getElementById("legend-good-count");
  const legendWarnCount = document.getElementById("legend-warn-count");
  const legendCriticalCount = document.getElementById("legend-critical-count");

  // Results containers
  const emptyState = document.getElementById("empty-state");
  const skeletonContainer = document.getElementById("skeleton-loading-container");
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
  const btnExportPdf = document.getElementById("btn-export-pdf");

  // Modals & Slide-overs
  const auditModal = document.getElementById("audit-modal");
  const btnOpenAudit = document.getElementById("btn-open-audit");
  const btnCloseAudit = document.getElementById("btn-close-audit");
  const auditTableBody = document.getElementById("audit-table-body");
  const auditCount = document.getElementById("audit-count");

  const indexModal = document.getElementById("index-modal");
  const btnOpenIndex = document.getElementById("btn-open-index");
  const btnCloseIndex = document.getElementById("btn-close-index");
  const dataIndexJson = document.getElementById("data-index-json");

  const slideoverBackdrop = document.getElementById("slideover-backdrop");
  const slideoverTitle = document.getElementById("slideover-title");
  const slideoverFields = document.getElementById("slideover-fields");
  const slideoverRawJson = document.getElementById("slideover-raw-json");
  const btnCloseSlideover = document.getElementById("btn-close-slideover");

  const evidenceBackdrop = document.getElementById("evidence-slideover-backdrop");
  const evTitle = document.getElementById("evidence-slideover-title");
  const evSourceTable = document.getElementById("ev-source-table");
  const evRecordIds = document.getElementById("ev-record-ids");
  const evFormulaString = document.getElementById("ev-formula-string");
  const evCalculatedResult = document.getElementById("ev-calculated-result");
  const evRawValuesJson = document.getElementById("ev-raw-values-json");
  const btnCloseEvidence = document.getElementById("btn-close-evidence");

  const toastContainer = document.getElementById("toast-container");
  const cmdKeyLabel = document.getElementById("cmd-key-label");

  // Trace strip steps
  const traceStep1 = document.getElementById("trace-step-1");
  const traceStep2 = document.getElementById("trace-step-2");
  const traceStep3 = document.getElementById("trace-step-3");
  const traceStep4 = document.getElementById("trace-step-4");
  const traceStep5 = document.getElementById("trace-step-5");

  // View Navigation Elements
  const navItems = document.querySelectorAll(".nav-item");
  const viewPanes = document.querySelectorAll(".view-pane");
  const pageViewTitle = document.getElementById("page-view-title");

  // Initialize App
  initHealthCheck();
  initSampleNotices();
  initDataIndex();
  initEventListeners();

  window.switchView = function(viewName) {
    navItems.forEach(item => {
      if (item.dataset.view === viewName) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });

    viewPanes.forEach(pane => {
      if (pane.id === `view-${viewName}`) {
        pane.style.display = "block";
      } else {
        pane.style.display = "none";
      }
    });

    if (viewName === "dashboard") pageViewTitle.textContent = "Dashboard Overview";
    if (viewName === "disruptions") pageViewTitle.textContent = "Disruption Impact Analyzer";
    if (viewName === "escalations") pageViewTitle.textContent = "Incident Escalations Manager";

    updateDashboardKPIs();
  };

  async function initHealthCheck() {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      if (data.status === "online") {
        statusPill.classList.add("active");
        statusText.textContent = data.gemini_api_configured ? "Gemini API connected" : "Offline fallback active";
      }
    } catch (e) {
      statusPill.classList.add("offline");
      statusText.textContent = "API unreachable";
    }
  }

  async function initSampleNotices() {
    try {
      const res = await fetch("/api/sample-notices");
      const data = await res.json();
      sampleNotices = data.notices || [];

      sampleSelect.innerHTML = '<option value="">Select a pre-loaded scenario...</option>';
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
    navItems.forEach(item => {
      item.addEventListener("click", () => switchView(item.dataset.view));
    });

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
        noticeMetaCard.style.display = "flex";
      }
    });

    btnAnalyze.addEventListener("click", runAnalysis);

    noticeTextarea.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        runAnalysis();
      }
    });

    headlineText.addEventListener("click", () => {
      if (typewriterInterval) {
        clearInterval(typewriterInterval);
        typewriterInterval = null;
        headlineText.textContent = fullNarrationText;
      }
    });

    btnExportPdf.addEventListener("click", () => window.print());

    btnOpenAudit.addEventListener("click", () => {
      fetchAuditHistory();
      auditModal.style.display = "flex";
    });

    btnCloseAudit.addEventListener("click", () => auditModal.style.display = "none");

    btnOpenIndex.addEventListener("click", () => {
      renderDataIndexTab("tab-suppliers");
      indexModal.style.display = "flex";
    });

    btnCloseIndex.addEventListener("click", () => indexModal.style.display = "none");

    btnCloseSlideover.addEventListener("click", () => slideoverBackdrop.style.display = "none");

    slideoverBackdrop.addEventListener("click", (e) => {
      if (e.target === slideoverBackdrop) slideoverBackdrop.style.display = "none";
    });

    btnCloseEvidence.addEventListener("click", () => evidenceBackdrop.style.display = "none");

    evidenceBackdrop.addEventListener("click", (e) => {
      if (e.target === evidenceBackdrop) evidenceBackdrop.style.display = "none";
    });
  }

  function resetTraceStrip() {
    [traceStep1, traceStep2, traceStep3, traceStep4, traceStep5].forEach(step => {
      step.classList.remove("active", "unfilled");
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
    btnExportPdf.style.display = "none";
    skeletonContainer.style.display = "flex";

    resetTraceStrip();
    traceStep1.classList.add("active");
    traceStep2.classList.add("active");

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notice_text: text })
      });
      const data = await res.json();
      currentPipelineResult = data;

      skeletonContainer.style.display = "none";
      renderPipelineResult(data);
    } catch (e) {
      skeletonContainer.style.display = "none";
      alert("Error analyzing disruption notice: " + e.message);
    } finally {
      btnAnalyze.disabled = false;
      analyzeSpinner.style.display = "none";
      btnAnalyzeText.textContent = "Run impact pipeline";
    }
  }

  function renderPipelineResult(data) {
    const isShortCircuited = data.short_circuited;
    const stage1 = data.stage1 || {};
    const stage2 = data.stage2 || {};
    const stage3 = data.stage3 || {};
    const stage4 = data.stage4 || {};
    const contradiction = data.contradiction;
    const matchState = data.match_state || (data.match_found ? "EXACT" : "UNMAPPED");

    const ambiguousWrap = document.getElementById("ambiguous-candidates-wrap");
    const contradictionWrap = document.getElementById("contradiction-action-wrap");
    ambiguousWrap.style.display = "none";
    contradictionWrap.style.display = "none";

    // Handle Short-Circuited / Special States (UNMAPPED, AMBIGUOUS, CRITICAL CONTRADICTION)
    if (!data.match_found || isShortCircuited) {
      traceStep1.classList.add("active");
      traceStep2.classList.add("active");
      traceStep3.classList.add("unfilled");
      traceStep4.classList.add("unfilled");
      traceStep5.classList.add("unfilled");

      updateKpiHeroStrip([], 0);

      noImpactAlert.style.display = "flex";

      if (matchState === "AMBIGUOUS") {
        noImpactAlert.className = "outcome-banner status-warn-banner";
        calloutBadgeText.textContent = "AMBIGUOUS MATCH";
        alertTitle.textContent = "Multiple Candidate Entities Matched Notice";
        alertBody.textContent = "Stage 1 entity resolution found 2 or more entities within a close confidence band. Human clarification is required before proceeding.";

        let candHtml = '<div style="font-weight:600; margin-bottom:8px;">Candidate Matches:</div><div style="display:flex; gap:10px; flex-wrap:wrap;">';
        (data.candidate_matches || stage1.candidate_matches || []).forEach(c => {
          candHtml += `
            <div style="background:var(--bg); border:1px solid var(--border); padding:8px 12px; border-radius:6px; font-size:12px;">
              <strong>${c.entity_type.toUpperCase()}: ${c.entity_id}</strong> (Conf: ${c.confidence})
              <button class="btn btn-primary btn-sm" style="margin-left:8px;" onclick="clarifyEntity('${c.entity_id}')">Select & Resolve</button>
            </div>
          `;
        });
        candHtml += `
          <button class="btn btn-escalate" style="margin-left:auto;" onclick="escalateCurrentNotice('Ambiguous entity match requires manager decision')">Escalate Notice</button>
        </div>`;
        ambiguousWrap.innerHTML = candHtml;
        ambiguousWrap.style.display = "block";
      } else if (contradiction && contradiction.severity === "CRITICAL") {
        noImpactAlert.className = "outcome-banner status-critical-banner";
        calloutBadgeText.textContent = "CRITICAL CONTRADICTION";
        alertTitle.textContent = "CRITICAL CONTRADICTION DETECTED";
        alertBody.textContent = contradiction.summary;
        contradictionWrap.style.display = "block";
      } else {
        noImpactAlert.className = "outcome-banner status-warn-banner";
        calloutBadgeText.textContent = "UNMAPPED";
        alertTitle.textContent = "No matching distributor record found in database";
        alertBody.textContent = "No entity matched above lower confidence threshold. Human operator review required.";
        contradictionWrap.style.display = "block";
      }

      alertTags.innerHTML = `<span>State: ${matchState}</span><span>Pipeline Short-Circuited</span>`;
      return;
    }

    // Full pipeline completion (EXACT match)
    [traceStep1, traceStep2, traceStep3, traceStep4, traceStep5].forEach(s => s.classList.add("active"));

    const affectedOrders = stage4.affected_orders || [];
    updateKpiHeroStrip(affectedOrders, stage2.total_at_risk_value || 0);

    if (stage4.no_impact || (stage3.total_orders_affected === 0)) {
      noImpactAlert.style.display = "flex";
      noImpactAlert.className = "outcome-banner status-good-banner";
      calloutBadgeText.textContent = "Resolved clear";
      alertTitle.textContent = "Zero pending customer orders affected by this disruption";
      alertBody.textContent = stage4.headline || "Zero pending orders affected by disruption.";
      alertTags.innerHTML = `<span>Entity matched: ${stage1.candidate_matches ? stage1.candidate_matches[0].entity_id : '-'}</span>`;
    } else {
      pipelineDetailsContainer.style.display = "flex";
      btnExportPdf.style.display = "inline-flex";

      fullNarrationText = stage4.headline || `Disruption impacts ${stage2.total_orders_affected} order(s) at risk.`;
      startTypewriterReveal(fullNarrationText);

      stage1Summary.textContent = `${(stage1.candidate_matches || []).length} candidate(s) matched (${stage1.notice_summary || ''}).`;
      stage2Summary.textContent = `${stage2.total_orders_affected || 0} order(s) affected. Total risk: $${(stage2.total_at_risk_value || 0).toLocaleString()}.`;

      renderPolicyCitations(stage4.policy_citations || []);
      renderImpactChainDiagram(data);
      renderDecisionTimeline(data.timeline || []);
      renderManifestRows(affectedOrders);
    }
  }

  function renderPolicyCitations(citations) {
    const wrap = document.getElementById("policy-citations-wrap");
    const list = document.getElementById("policy-citations-list");
    if (!citations || citations.length === 0) {
      wrap.style.display = "none";
      return;
    }
    wrap.style.display = "block";
    let html = "";
    citations.forEach(c => {
      html += `
        <div class="policy-card">
          <div class="policy-heading">${c.citation}</div>
          <div class="policy-snippet">"${c.snippet}"</div>
        </div>
      `;
    });
    list.innerHTML = html;
  }

  function renderDecisionTimeline(timelineEvents) {
    const wrap = document.getElementById("decision-timeline-wrap");
    const list = document.getElementById("decision-timeline-list");
    if (!timelineEvents || timelineEvents.length === 0) {
      wrap.style.display = "none";
      return;
    }
    wrap.style.display = "block";
    let html = "";
    timelineEvents.forEach(ev => {
      html += `
        <div class="timeline-item">
          <span class="timeline-dot"></span>
          <span class="timeline-title">${ev.stage}</span>
          <span class="timeline-time">${ev.timestamp}</span>
          <div class="timeline-details">${ev.details}</div>
        </div>
      `;
    });
    list.innerHTML = html;
  }

  window.clarifyEntity = async function(entityId) {
    const text = noticeTextarea.value.trim();
    btnAnalyze.disabled = true;
    try {
      const res = await fetch("/api/disruption/clarify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notice_text: text, entity_id: entityId })
      });
      const data = await res.json();
      currentPipelineResult = data;
      renderPipelineResult(data);
      showToast(`Entity clarified to ${entityId}. Pipeline resumed.`, "good");
    } catch (e) {
      alert("Error clarifying entity: " + e.message);
    } finally {
      btnAnalyze.disabled = false;
    }
  };

  window.escalateCurrentNotice = async function(notes = "Operator requested escalation") {
    try {
      const res = await fetch("/api/action/escalate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_id: "INCIDENT-NOTICE",
          action: "escalate_notice",
          operator_notes: notes
        })
      });
      await res.json();
      showToast("Incident notice escalated to manager log.", "good");
      fetchAuditHistory();
      updateDashboardKPIs();
    } catch (e) {
      alert("Error escalating notice: " + e.message);
    }
  };

  function startTypewriterReveal(text) {
    if (typewriterInterval) clearInterval(typewriterInterval);
    headlineText.textContent = "";
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      headlineText.textContent = text;
      return;
    }
    let idx = 0;
    typewriterInterval = setInterval(() => {
      if (idx < text.length) {
        headlineText.textContent += text.charAt(idx);
        idx++;
      } else {
        clearInterval(typewriterInterval);
        typewriterInterval = null;
      }
    }, 15);
  }

  function updateKpiHeroStrip(orders, totalAtRiskValue) {
    const count = orders.length;
    kpiOrdersAffected.textContent = count;

    let sumRisk = 0;
    let sumCost = 0;
    let minDays = 999;
    let countGood = 0;
    let countWarn = 0;
    let countCritical = 0;

    orders.forEach(o => {
      const score = o.urgency_score || 0;
      sumRisk += score;
      if (score <= 40) countGood++;
      else if (score <= 70) countWarn++;
      else countCritical++;

      const recOpt = (o.options || []).find(opt => opt.action === o.recommended_option);
      if (recOpt && recOpt.cost_estimate) {
        sumCost += recOpt.cost_estimate;
      }

      if (o.days_late_estimate && o.days_late_estimate > 0 && o.days_late_estimate < minDays) {
        minDays = o.days_late_estimate;
      }
    });

    kpiTotalRisk.textContent = sumRisk.toFixed(1);
    kpiCostAtRisk.textContent = `$${sumCost.toFixed(2)}`;
    kpiNearestDeadline.textContent = minDays !== 999 ? `${minDays} days` : "-";

    legendGoodCount.textContent = countGood;
    legendWarnCount.textContent = countWarn;
    legendCriticalCount.textContent = countCritical;
  }

  function renderManifestRows(orders) {
    actionCardsSection.style.display = "flex";
    actionCardsList.innerHTML = "";

    orders.forEach(ord => {
      const row = document.createElement("div");
      row.className = "manifest-row";
      row.dataset.orderId = ord.order_id;

      const score = ord.urgency_score || 0;
      let scoreColorClass = "status-good";
      if (score > 70) scoreColorClass = "status-critical";
      else if (score > 40) scoreColorClass = "status-warn";

      const tierBadge = ord.customer_tier === "VIP" ? '<span class="badge badge-vip">VIP</span>' : '<span class="badge">Standard</span>';

      // Requirement 10: Side-by-Side What-If Option Cards Grid
      let sideBySideOptionsHtml = '<div class="options-side-by-side-grid">';
      (ord.options || []).forEach(opt => {
        const isRec = opt.action === ord.recommended_option;
        const optEvKey = JSON.stringify(opt.evidence || {}).replace(/"/g, '&quot;');

        sideBySideOptionsHtml += `
          <div class="option-card ${isRec ? 'recommended' : ''}">
            <div class="option-card-header">
              <span>${opt.title || opt.action.toUpperCase()}</span>
              ${isRec ? '<span class="recommended-pill">Rec</span>' : ''}
            </div>
            <div class="option-card-tradeoff">${opt.tradeoff}</div>
            <div class="option-card-cost">
              <span>$${(opt.cost_estimate || 0).toFixed(2)}</span>
              <button class="btn-why-evidence" onclick="openEvidenceSlideover('Option Cost Evidence', ${optEvKey})">Why?</button>
            </div>
          </div>
        `;
      });
      sideBySideOptionsHtml += '</div>';

      const approveActionText = getActionText(ord.recommended_option);

      const shortfallEvKey = JSON.stringify((ord.evidence || {}).shortfall_qty || {}).replace(/"/g, '&quot;');
      const urgencyEvKey = JSON.stringify((ord.evidence || {}).urgency_score || {}).replace(/"/g, '&quot;');

      row.innerHTML = `
        <div class="row-status-bar"></div>
        <div class="cell-order">
          <a class="order-id-link" onclick="openRecordSlideover('${ord.order_id}')">${ord.order_id}</a>
          <span class="customer-name">${ord.customer_name || ord.order_id}</span>
          <div style="margin-top: 4px;">${tierBadge}</div>
        </div>
        <div class="cell-urgency">
          <span class="urgency-num ${scoreColorClass}">${score.toFixed(1)}</span>
          <button class="btn-why-evidence" onclick="openEvidenceSlideover('Urgency Score Evidence', ${urgencyEvKey})">Why?</button>
        </div>
        <div class="cell-detail">
          <div class="shortfall-text">
            ${formatShortfallSummary(ord.shortfall_summary)}
            <button class="btn-why-evidence" onclick="openEvidenceSlideover('Shortfall Quantity Evidence', ${shortfallEvKey})">Why?</button>
          </div>
          ${sideBySideOptionsHtml}
          <div class="row-actions-bar">
            <span class="recommendation-reason">Reason: ${ord.recommendation_reason}</span>
            <div class="action-buttons-group">
              <button class="btn btn-approve" id="btn-approve-${ord.order_id}" onclick="handleDecision('${ord.order_id}', '${ord.recommended_option}', 'APPROVED')">
                <span class="btn-text">${approveActionText}</span>
              </button>
              <button class="btn btn-reject" id="btn-reject-${ord.order_id}" onclick="handleDecision('${ord.order_id}', '${ord.recommended_option}', 'REJECTED')">Reject</button>
              <button class="btn btn-escalate" id="btn-escalate-${ord.order_id}" onclick="handleDecision('${ord.order_id}', '${ord.recommended_option}', 'ESCALATED')">Escalate</button>
            </div>
          </div>
        </div>
      `;

      actionCardsList.appendChild(row);
    });
  }

  function getActionText(actionKey) {
    if (actionKey === "expedite") return "Approve expedite shipment";
    if (actionKey === "part_ship") return "Approve part-shipment";
    if (actionKey === "reallocate") return "Approve safety stock reallocation";
    if (actionKey === "notify_customer") return "Approve customer notification";
    return "Approve action";
  }

  function formatShortfallSummary(summaryText) {
    if (!summaryText) return "";
    return summaryText.replace(/\b(ORD-\d+|SHP-\d+|SKU-\d+|SUP-\d+|CUST-\d+)\b/g, '<span class="record-citation" onclick="openRecordSlideover(\'$1\')">$1</span>');
  }

  // Slide-Over for Evidence & "Why?" Support (Item 3)
  window.openEvidenceSlideover = function(title, evidenceObj) {
    if (!evidenceObj || typeof evidenceObj !== "object") return;
    evTitle.textContent = title;
    evSourceTable.textContent = evidenceObj.source_table || "-";
    evRecordIds.textContent = (evidenceObj.record_ids || []).join(", ") || "-";
    evFormulaString.textContent = evidenceObj.formula_string || "-";
    evCalculatedResult.textContent = String(evidenceObj.calculated_result !== undefined ? evidenceObj.calculated_result : "-");
    evRawValuesJson.textContent = JSON.stringify(evidenceObj.raw_values || {}, null, 2);

    evidenceBackdrop.style.display = "flex";
  };

  function renderImpactChainDiagram(data) {
    const wrap = document.getElementById("impact-chain-wrap");
    const flow = document.getElementById("impact-chain-flow");
    if (!data || !data.stage2) {
      wrap.style.display = "none";
      return;
    }
    wrap.style.display = "block";

    const stage1 = data.stage1 || {};
    const stage2 = data.stage2 || {};
    const stage3 = data.stage3 || {};
    const affectedOrders = stage3.affected_orders || [];

    const firstMatch = (stage1.candidate_matches || [])[0] || {};
    const supplierId = (stage2.matched_entity_ids || []).find(id => String(id).startsWith("SUP-")) || firstMatch.entity_id || "SUP-101";
    const shipmentId = (stage2.affected_shipments || [])[0] || "SHP-2002";
    const skuId = (stage2.affected_skus || [])[0] || "SKU-1002";

    let supName = supplierId;
    if (dataIndex && dataIndex.suppliers) {
      const supObj = dataIndex.suppliers.find(s => s.id === supplierId);
      if (supObj) supName = `${supObj.name}`;
    }

    let skuName = skuId;
    let invText = "Stock available";
    if (dataIndex && dataIndex.stock) {
      const stObj = dataIndex.stock.find(s => s.sku === skuId);
      if (stObj) {
        skuName = `${stObj.name}`;
        invText = `${stObj.on_hand} on hand`;
      }
    }

    const uniqueCustomers = new Set(affectedOrders.map(o => o.customer_id)).size;

    const nodes = [
      { type: "Supplier", val: supName, recId: supplierId },
      { type: "Shipment", val: shipmentId, recId: shipmentId },
      { type: "Product", val: skuName, recId: skuId },
      { type: "Warehouse", val: "Main Hub", recId: null },
      { type: "Inventory", val: invText, recId: skuId },
      { type: "Orders", val: `${stage2.total_orders_affected || affectedOrders.length} affected`, recId: affectedOrders[0] ? affectedOrders[0].order_id : null },
      { type: "Customers", val: `${uniqueCustomers} affected`, recId: affectedOrders[0] ? affectedOrders[0].customer_id : null }
    ];

    let html = "";
    nodes.forEach((n, idx) => {
      const clickAttr = n.recId ? `onclick="openRecordSlideover('${n.recId}')"` : '';
      html += `
        <div class="chain-node" ${clickAttr} title="${n.recId ? 'Click to inspect ' + n.recId : n.val}">
          <div class="chain-node-type">${n.type}</div>
          <div class="chain-node-val">${n.val}</div>
        </div>
      `;
      if (idx < nodes.length - 1) {
        html += `<span class="chain-connector">&rarr;</span>`;
      }
    });

    flow.innerHTML = html;
  }

  // Slide-Over Panel for Clickable Record-ID Grounding Proof
  window.openRecordSlideover = function(recordId) {
    if (!dataIndex) return;
    let recData = null;
    let recType = "Record";

    if (recordId.startsWith("ORD-")) {
      recData = dataIndex.orders.find(o => o.order_id === recordId);
      recType = "Customer Order Record";
    } else if (recordId.startsWith("SKU-")) {
      recData = dataIndex.stock.find(s => s.sku === recordId);
      recType = "Stock Inventory Record";
    } else if (recordId.startsWith("SHP-")) {
      recData = dataIndex.shipments.find(s => s.shipment_id === recordId);
      recType = "In-Transit Shipment Record";
    } else if (recordId.startsWith("SUP-")) {
      recData = dataIndex.suppliers.find(s => s.id === recordId);
      recType = "Supplier Master Record";
    } else if (recordId.startsWith("CUST-")) {
      recData = dataIndex.customers.find(c => c.customer_id === recordId);
      recType = "Customer Profile Record";
    }

    if (!recData) return;

    slideoverTitle.textContent = `${recType}: ${recordId}`;

    // Render Shipment Timeline if Shipment Record
    const timelineWrap = document.getElementById("shipment-timeline-wrap");
    const timelineFlow = document.getElementById("shipment-step-timeline");

    if (recordId.startsWith("SHP-") && recData) {
      timelineWrap.style.display = "block";
      const status = String(recData.status || "in_transit").toLowerCase();

      const steps = [
        { name: "Created", key: "created" },
        { name: "Dispatched", key: "dispatched" },
        { name: "In Transit", key: "in_transit" },
        { name: "Delayed / Audit", key: "delayed" },
        { name: "Delivered", key: "delivered" }
      ];

      const isDelayed = status.includes("delay") || status.includes("halt");
      const isDelivered = status === "delivered" || status === "completed";

      let html = "";
      steps.forEach(s => {
        let stepClass = "shipment-step";
        if (s.key === "created" || s.key === "dispatched") {
          stepClass += " completed";
        } else if (s.key === "in_transit") {
          stepClass += (isDelivered || isDelayed) ? " completed" : " active";
        } else if (s.key === "delayed") {
          if (isDelayed) stepClass += " delayed active";
          else if (isDelivered) stepClass += " completed";
        } else if (s.key === "delivered") {
          if (isDelivered) stepClass += " completed active";
        }

        html += `
          <div class="${stepClass}">
            <div class="shipment-step-dot"></div>
            <div class="shipment-step-name">${s.name}</div>
          </div>
        `;
      });
      timelineFlow.innerHTML = html;
    } else {
      timelineWrap.style.display = "none";
    }

    let fieldsHtml = "";
    Object.keys(recData).forEach(k => {
      const val = recData[k];
      const valStr = typeof val === "object" ? JSON.stringify(val) : String(val);
      fieldsHtml += `<div class="field-pair"><span class="field-key">${k}</span><span class="field-val">${valStr}</span></div>`;
    });
    slideoverFields.innerHTML = fieldsHtml;
    slideoverRawJson.textContent = JSON.stringify(recData, null, 2);
    slideoverBackdrop.style.display = "flex";
  };

  window.handleDecision = async function(orderId, action, decision) {
    let endpoint = "/api/action/approve";
    if (decision === "REJECTED") endpoint = "/api/action/reject";
    if (decision === "ESCALATED") endpoint = "/api/action/escalate";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_id: orderId,
          action: action,
          operator_notes: `${decision} by human operator via console.`
        })
      });
      await res.json();

      const row = document.querySelector(`.manifest-row[data-order-id="${orderId}"]`);
      if (row) {
        if (decision === "APPROVED") {
          row.classList.add("approved-row");
          showToast(`Action approved for order ${orderId}`, "good");
        } else if (decision === "ESCALATED") {
          row.classList.add("escalated-row");
          showToast(`Order ${orderId} escalated to management`, "muted");
        } else {
          row.classList.add("rejected-row");
          showToast(`Option rejected for order ${orderId}`, "muted");
        }
      }

      fetchAuditHistory();
      updateDashboardKPIs();
    } catch (e) {
      alert("Error recording decision: " + e.message);
    }
  };

  function showToast(msg, type = "good") {
    const toast = document.createElement("div");
    toast.className = `toast-message ${type === "good" ? "toast-good" : "toast-muted"}`;
    toast.innerHTML = `<span>${msg}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 200);
    }, 3000);
  }

  async function fetchAuditHistory() {
    try {
      const res = await fetch("/api/action/history");
      const data = await res.json();
      actionHistory = data.history || [];
      auditCount.textContent = actionHistory.length;

      const sidebarEscBadge = document.getElementById("sidebar-escalations-badge");
      const escalations = actionHistory.filter(a => a.status === "ESCALATED");
      sidebarEscBadge.textContent = escalations.length;

      if (actionHistory.length === 0) {
        auditTableBody.innerHTML = '<tr><td colspan="6" class="text-muted text-center">No decisions logged in this session.</td></tr>';
        return;
      }

      let html = "";
      actionHistory.forEach(a => {
        html += `
          <tr title="Exact timestamp: ${a.timestamp}">
            <td class="mono-num">${a.id}</td>
            <td class="mono-num">${a.timestamp}</td>
            <td class="mono-num">${a.order_id || '-'}</td>
            <td>${a.stage || a.chosen_action}</td>
            <td>${a.status}</td>
            <td>${a.details || a.operator_notes || '-'}</td>
          </tr>
        `;
      });
      auditTableBody.innerHTML = html;

      renderEscalationsView(escalations);
      updateDashboardKPIs();
    } catch (e) {
      console.error("Failed to fetch audit history", e);
    }
  }

  function renderEscalationsView(escalations) {
    const container = document.getElementById("escalations-list");
    if (!escalations || escalations.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <h3>No active escalations</h3>
          <p class="text-muted">All disruption notices and orders have been resolved.</p>
        </div>
      `;
      return;
    }

    let html = "";
    escalations.forEach(esc => {
      html += `
        <div class="escalation-card">
          <div>
            <div style="font-weight:600;">Incident ${esc.id} - Ref: ${esc.order_id}</div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">${esc.timestamp} | ${esc.operator_notes}</div>
          </div>
          <span class="badge badge-escalations">PENDING MANAGER REVIEW</span>
        </div>
      `;
    });
    container.innerHTML = html;
  }

  function updateDashboardKPIs() {
    const dashActive = document.getElementById("dash-active-disruptions");
    const dashOrders = document.getElementById("dash-orders-at-risk");
    const dashCust = document.getElementById("dash-customers-impacted");
    const dashEsc = document.getElementById("dash-pending-escalations");
    const dashRecent = document.getElementById("dash-recent-actions-list");

    const escalations = actionHistory.filter(a => a.status === "ESCALATED");

    if (dashActive) dashActive.textContent = currentPipelineResult ? (currentPipelineResult.match_found ? "1" : "0") : "1";
    if (dashOrders) dashOrders.textContent = currentPipelineResult && currentPipelineResult.stage2 ? currentPipelineResult.stage2.total_orders_affected : "3";
    if (dashCust) dashCust.textContent = currentPipelineResult && currentPipelineResult.stage3 && currentPipelineResult.stage3.affected_orders ? new Set(currentPipelineResult.stage3.affected_orders.map(o => o.customer_id)).size : "2";
    if (dashEsc) dashEsc.textContent = escalations.length;

    if (dashRecent) {
      if (actionHistory.length === 0) {
        dashRecent.innerHTML = '<span class="text-muted">No recent pipeline decisions logged.</span>';
      } else {
        let rHtml = "";
        actionHistory.slice(-5).reverse().forEach(a => {
          rHtml += `
            <div style="padding:6px 0; border-bottom:1px solid var(--border); font-size:12px;">
              <strong>[${a.status}]</strong> ${a.order_id || 'Incident'} - ${a.timestamp}
            </div>
          `;
        });
        dashRecent.innerHTML = rHtml;
      }
    }
  }
});
