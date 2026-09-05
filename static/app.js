document.addEventListener("DOMContentLoaded", () => {
  // Global State
  let sampleNotices = [];
  let currentPipelineResult = null;
  let actionHistory = [];
  let dataIndex = null;
  let typewriterInterval = null;
  let fullNarrationText = "";

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

  // Modals & Slideover
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

  const toastContainer = document.getElementById("toast-container");
  const cmdKeyLabel = document.getElementById("cmd-key-label");

  // Trace strip steps
  const traceStep1 = document.getElementById("trace-step-1");
  const traceStep2 = document.getElementById("trace-step-2");
  const traceStep3 = document.getElementById("trace-step-3");
  const traceStep4 = document.getElementById("trace-step-4");
  const traceStep5 = document.getElementById("trace-step-5");

  // Detect OS for shortcut hint
  if (navigator.platform.toUpperCase().indexOf('MAC') >= 0) {
    if (cmdKeyLabel) cmdKeyLabel.textContent = '⌘';
  }

  // Initialize App
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
          statusText.textContent = "Gemini API connected";
        } else {
          statusText.textContent = "Offline fallback active";
        }
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

    // Keyboard shortcut: Cmd/Ctrl + Enter
    noticeTextarea.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        runAnalysis();
      }
    });

    // Typewriter skippable click
    headlineText.addEventListener("click", () => {
      if (typewriterInterval) {
        clearInterval(typewriterInterval);
        typewriterInterval = null;
        headlineText.textContent = fullNarrationText;
      }
    });

    // PDF Export
    btnExportPdf.addEventListener("click", () => {
      window.print();
    });

    // Audit Modal
    btnOpenAudit.addEventListener("click", () => {
      fetchAuditHistory();
      auditModal.style.display = "flex";
    });

    btnCloseAudit.addEventListener("click", () => {
      auditModal.style.display = "none";
    });

    // Index Modal
    btnOpenIndex.addEventListener("click", () => {
      renderDataIndexTab("tab-suppliers");
      indexModal.style.display = "flex";
    });

    btnCloseIndex.addEventListener("click", () => {
      indexModal.style.display = "none";
    });

    // Slide-over close
    btnCloseSlideover.addEventListener("click", () => {
      slideoverBackdrop.style.display = "none";
    });

    slideoverBackdrop.addEventListener("click", (e) => {
      if (e.target === slideoverBackdrop) {
        slideoverBackdrop.style.display = "none";
      }
    });

    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
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

    // Show Skeleton Loading Placeholder
    skeletonContainer.style.display = "flex";

    resetTraceStrip();
    traceStep1.classList.add("active");

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (!prefersReducedMotion) {
      await new Promise(r => setTimeout(r, 100));
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

      // Hide Skeleton Loading
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

    if (!data.match_found || isShortCircuited) {
      // Short-circuit: Steps 1 & 2 fill in; 3, 4, 5 stay unfilled
      traceStep1.classList.add("active");
      traceStep2.classList.add("active");
      traceStep3.classList.add("unfilled");
      traceStep4.classList.add("unfilled");
      traceStep5.classList.add("unfilled");

      updateKpiHeroStrip([], 0);

      noImpactAlert.style.display = "flex";
      noImpactAlert.className = "outcome-banner status-warn-banner";
      calloutBadgeText.textContent = "No match identified";
      alertTitle.textContent = "No matching distributor record found in database";
      alertBody.textContent = "Disruption notice text was processed through local vector retrieval and Stage 1 entity resolution. No matching supplier, shipment, or stock item was identified in distributor database records.";
      alertTags.innerHTML = `
        <span>Retrieval similarity: ${(stage1.retrieval_meta ? stage1.retrieval_meta.best_similarity : 0).toFixed(2)}</span>
        <span>Stage 1 short-circuit executed</span>
      `;
      return;
    }

    // Full pipeline completion
    [traceStep1, traceStep2, traceStep3, traceStep4, traceStep5].forEach(s => s.classList.add("active"));

    const affectedOrders = stage4.affected_orders || [];
    updateKpiHeroStrip(affectedOrders, stage2.total_at_risk_value || 0);

    if (stage4.no_impact || (stage3.total_orders_affected === 0)) {
      noImpactAlert.style.display = "flex";
      noImpactAlert.className = "outcome-banner status-good-banner";
      calloutBadgeText.textContent = "Resolved clear";
      alertTitle.textContent = "Zero pending customer orders affected by this disruption";
      alertBody.textContent = stage4.headline || "Disruption notice was matched to supplier records and traced through active shipments and inventory records. Zero pending customer orders are affected because warehouse stock levels are sufficient to cover current demand.";
      alertTags.innerHTML = `
        <span>Entity matched: ${(stage1.candidate_matches && stage1.candidate_matches[0] ? stage1.candidate_matches[0].entity_id : '-')}</span>
        <span>Graph traversal confirmed zero shortfall</span>
      `;
    } else {
      pipelineDetailsContainer.style.display = "flex";
      btnExportPdf.style.display = "inline-flex";

      // Typewriter reveal for Stage 4 narration text
      fullNarrationText = stage4.headline || `Disruption impacts ${stage2.total_orders_affected} order(s) totaling $${(stage2.total_at_risk_value || 0).toLocaleString()} at risk.`;
      startTypewriterReveal(fullNarrationText);

      stage1Summary.textContent = `${(stage1.candidate_matches || []).length} entity candidate(s) matched (${stage1.notice_summary || ''}).`;
      stage2Summary.textContent = `${stage2.total_orders_affected || 0} order(s) affected across ${(stage2.affected_skus || []).length} SKU(s). Total at risk: $${(stage2.total_at_risk_value || 0).toLocaleString()}.`;

      renderManifestRows(affectedOrders);
    }
  }

  function startTypewriterReveal(text) {
    if (typewriterInterval) clearInterval(typewriterInterval);
    headlineText.textContent = "";
    
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
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

    if (sumCost > 500) {
      kpiCostAtRisk.className = "kpi-number mono-num status-critical";
    } else if (sumCost > 0) {
      kpiCostAtRisk.className = "kpi-number mono-num status-warn";
    } else {
      kpiCostAtRisk.className = "kpi-number mono-num";
    }

    kpiNearestDeadline.textContent = minDays !== 999 ? `${minDays} days` : "-";

    legendGoodCount.textContent = countGood;
    legendWarnCount.textContent = countWarn;
    legendCriticalCount.textContent = countCritical;

    if (count === 0) {
      segGood.style.width = "33%";
      segWarn.style.width = "33%";
      segCritical.style.width = "34%";
      segGood.title = "Low Urgency: 0 orders";
      segWarn.title = "Medium Urgency: 0 orders";
      segCritical.title = "High Urgency: 0 orders";
    } else {
      const pctGood = Math.round((countGood / count) * 100);
      const pctWarn = Math.round((countWarn / count) * 100);
      const pctCrit = Math.max(0, 100 - pctGood - pctWarn);

      segGood.style.width = `${pctGood}%`;
      segWarn.style.width = `${pctWarn}%`;
      segCritical.style.width = `${pctCrit}%`;

      segGood.title = `Low Urgency (0-40): ${countGood} order(s)`;
      segWarn.title = `Medium Urgency (41-70): ${countWarn} order(s)`;
      segCritical.title = `High Urgency (71-100): ${countCritical} order(s)`;
    }
  }

  function renderManifestRows(orders) {
    actionCardsSection.style.display = "flex";
    actionCardsList.innerHTML = "";

    orders.forEach(ord => {
      const row = document.createElement("div");

      const score = ord.urgency_score;
      let scoreColorClass = "status-good";
      let statusRowClass = "status-good-row";
      if (score > 70) {
        scoreColorClass = "status-critical";
        statusRowClass = "status-critical-row";
      } else if (score > 40) {
        scoreColorClass = "status-warn";
        statusRowClass = "status-warn-row";
      }

      row.className = `manifest-row ${statusRowClass}`;
      row.dataset.orderId = ord.order_id;

      const isVip = ord.customer_tier === "VIP";
      const tierBadge = isVip
        ? '<span class="badge badge-vip">VIP tier</span>'
        : '<span class="badge">Standard tier</span>';

      let optionsHtml = '<div class="options-collapsible-list">';
      (ord.options || []).forEach(opt => {
        const isRec = opt.action === ord.recommended_option;
        optionsHtml += `
          <div class="option-row-item ${isRec ? 'recommended' : ''}">
            <div class="opt-title">
              <span>${formatOptionName(opt.action)}</span>
              ${isRec ? '<span class="recommended-pill">Recommended</span>' : ''}
            </div>
            <div class="opt-desc">${opt.tradeoff}</div>
            <div class="opt-metrics">${formatOptionCost(opt)}</div>
          </div>
        `;
      });
      optionsHtml += '</div>';

      const approveActionText = getActionText(ord.recommended_option);

      row.innerHTML = `
        <div class="row-status-bar"></div>
        <div class="cell-order">
          <a class="order-id-link" onclick="openRecordSlideover('${ord.order_id}')">${ord.order_id}</a>
          <span class="customer-name">${ord.customer_name || ord.order_id}</span>
          <div style="margin-top: 4px;">${tierBadge}</div>
        </div>
        <div class="cell-urgency">
          <span class="urgency-num ${scoreColorClass}">${ord.urgency_score.toFixed(1)}</span>
          <span class="urgency-label">Urgency score</span>
        </div>
        <div></div>
        <div class="cell-detail">
          <div class="shortfall-text">${formatShortfallSummary(ord.shortfall_summary)}</div>
          ${optionsHtml}
          <div class="row-actions-bar">
            <span class="recommendation-reason">Reason: ${ord.recommendation_reason}</span>
            <div class="action-buttons-group">
              <button class="btn btn-approve" id="btn-approve-${ord.order_id}" onclick="handleDecision('${ord.order_id}', '${ord.recommended_option}', 'APPROVED')">
                <svg class="btn-check-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 8 12 12 14 14"/></svg>
                <span class="btn-text">${approveActionText}</span>
              </button>
              <button class="btn btn-reject" id="btn-reject-${ord.order_id}" onclick="handleDecision('${ord.order_id}', '${ord.recommended_option}', 'REJECTED')">Reject option</button>
            </div>
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

  function formatOptionCost(opt) {
    if (opt.cost_estimate !== undefined) {
      return `$${opt.cost_estimate.toFixed(2)}`;
    }
    return "";
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
    return summaryText.replace(/\b(ORD-\d+|SHP-\d+|SKU-\d+|SUP-\d+|CUST-\d+)\b/g, '<span class="record-citation" onclick="openRecordSlideover(\'$1\')">$1</span>');
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
    
    // Render key-value pairs
    let fieldsHtml = "";
    Object.keys(recData).forEach(k => {
      const val = recData[k];
      const valStr = typeof val === "object" ? JSON.stringify(val) : String(val);
      fieldsHtml += `
        <div class="field-pair">
          <span class="field-key">${k}</span>
          <span class="field-val">${valStr}</span>
        </div>
      `;
    });
    slideoverFields.innerHTML = fieldsHtml;
    slideoverRawJson.textContent = JSON.stringify(recData, null, 2);

    slideoverBackdrop.style.display = "flex";
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
          operator_notes: `${decision} by operator via console manifest row.`
        })
      });
      await res.json();

      const row = document.querySelector(`.manifest-row[data-order-id="${orderId}"]`);
      if (row) {
        if (decision === "APPROVED") {
          row.classList.add("approved-row");
          const approveBtn = document.getElementById(`btn-approve-${orderId}`);
          if (approveBtn) {
            approveBtn.classList.add("approved");
            approveBtn.innerHTML = `
              <svg class="btn-check-icon" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
              <span>Action approved</span>
            `;
          }
          showToast(`Action approved for order ${orderId} (${action})`, "good");
        } else {
          row.classList.add("rejected-row");
          showToast(`Option rejected for order ${orderId}`, "muted");
        }
      }

      fetchAuditHistory();
    } catch (e) {
      alert("Error recording decision: " + e.message);
    }
  };

  function showToast(msg, type = "good") {
    const toast = document.createElement("div");
    toast.className = `toast-message ${type === "good" ? "toast-good" : "toast-muted"}`;
    toast.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 8 12 12 14 14"/></svg>
      <span>${msg}</span>
    `;
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
            <td class="mono-num">${a.order_id}</td>
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
