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

  const pipelineDetailsContainer = document.getElementById("pipeline-details-container");
  const headlineBanner = document.getElementById("headline-banner");
  const headlineText = document.getElementById("headline-text");
  const stage1Body = document.getElementById("stage1-body");
  const stage2Body = document.getElementById("stage2-body");

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

  // Stepper cards
  const step1 = document.getElementById("step-1-card");
  const step2 = document.getElementById("step-2-card");
  const step3 = document.getElementById("step-3-card");
  const step4 = document.getElementById("step-4-card");

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
        if (data.gemini_api_configured) {
          statusText.textContent = "Gemini LLM Active";
          statusPill.style.color = "var(--accent-emerald)";
        } else {
          statusText.textContent = "Offline Fallback Mode";
          statusPill.style.color = "var(--accent-amber)";
        }
      }
    } catch (e) {
      statusText.textContent = "API Error";
    }
  }

  async function initSampleNotices() {
    try {
      const res = await fetch("/api/sample-notices");
      const data = await res.json();
      sampleNotices = data.notices || [];

      sampleSelect.innerHTML = '<option value="">-- Select a Sample Disruption Notice --</option>';
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

  async function runAnalysis() {
    const text = noticeTextarea.value.trim();
    if (!text) {
      alert("Please enter or select a disruption notice first.");
      return;
    }

    // UI Loading state
    btnAnalyze.disabled = true;
    analyzeSpinner.style.display = "inline-block";
    btnAnalyzeText.textContent = "Analyzing Pipeline...";
    emptyState.style.display = "none";
    noImpactAlert.style.display = "none";
    pipelineDetailsContainer.style.display = "none";
    actionCardsSection.style.display = "none";

    resetStepper();
    step1.classList.add("active");

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notice_text: text })
      });
      const data = await res.json();
      currentPipelineResult = data;

      renderPipelineResult(data);
    } catch (e) {
      alert("Error analyzing notice: " + e.message);
    } finally {
      btnAnalyze.disabled = false;
      analyzeSpinner.style.display = "none";
      btnAnalyzeText.textContent = "🚀 Run 4-Stage Impact Pipeline";
    }
  }

  function resetStepper() {
    step1.classList.remove("active");
    step2.classList.remove("active");
    step3.classList.remove("active");
    step4.classList.remove("active");
  }

  function renderPipelineResult(data) {
    const isShortCircuited = data.short_circuited;
    const stage1 = data.stage1 || {};
    const stage2 = data.stage2 || {};
    const stage3 = data.stage3 || {};
    const stage4 = data.stage4 || {};

    // Check match_found
    if (!data.match_found || isShortCircuited) {
      step1.classList.add("active");
      noImpactAlert.style.display = "flex";
      noImpactAlert.className = "alert-card warning";
      alertTitle.textContent = "No Matching Distributor Record Found (Stage 1 Short-Circuit)";
      alertBody.textContent = stage1.ambiguity_notes || "Notice text does not match any known supplier, shipment, or stock SKU in distributor database.";
      alertTags.innerHTML = `
        <span class="badge badge-amber">Stage 1 Short-Circuit</span>
        <span class="badge badge-amber">match_found: false</span>
        <span class="badge badge-cyan">Zero Stage 2-4 Calls</span>
      `;
      return;
    }

    // Match found! Activate all steps
    step1.classList.add("active");
    step2.classList.add("active");
    step3.classList.add("active");
    step4.classList.add("active");

    // Check No Impact vs Impact
    if (stage4.no_impact || stage3.total_orders_affected === 0) {
      noImpactAlert.style.display = "flex";
      noImpactAlert.className = "alert-card";
      alertTitle.textContent = "No Pending Orders Affected (Zero Risk)";
      alertBody.textContent = stage4.headline || "Notice matched a supplier/shipment, but deterministic graph traversal confirmed 0 pending customer orders are impacted.";
      alertTags.innerHTML = `
        <span class="badge badge-cyan">Grounding Proved Zero Impact</span>
        <span class="badge badge-amber">no_impact: true</span>
      `;
    } else {
      pipelineDetailsContainer.style.display = "flex";
      headlineText.textContent = stage4.headline || `Disruption impacts ${stage2.total_orders_affected} order(s) totaling $${stage2.total_at_risk_value} at risk.`;
      
      renderStage1Details(stage1);
      renderStage2Details(stage2, stage3);
      renderActionCards(stage4.affected_orders || []);
    }
  }

  function renderStage1Details(s1) {
    let html = `
      <p><strong>Notice Summary:</strong> ${s1.notice_summary || '-'}</p>
      <div style="margin-top: 8px;"><strong>Candidate Matches (Retrieved &amp; Resolved):</strong></div>
      <ul style="padding-left: 18px; margin-top: 4px;">
    `;
    (s1.candidate_matches || []).forEach(c => {
      html += `<li><strong>[${c.entity_type.toUpperCase()}] ${c.entity_id}</strong> — Confidence: ${(c.confidence*100).toFixed(0)}% (${c.reason})</li>`;
    });
    html += `</ul>`;
    if (s1.ambiguity_notes) {
      html += `<div style="margin-top: 8px; color: var(--accent-amber);">⚠️ <em>Ambiguity Notes: ${s1.ambiguity_notes}</em></div>`;
    }
    stage1Body.innerHTML = html;
  }

  function renderStage2Details(s2, s3) {
    let html = `
      <div style="display: flex; gap: 16px; flex-wrap: wrap;">
        <div><strong>Matched Entities:</strong> ${(s2.matched_entity_ids || []).join(', ')}</div>
        <div><strong>Affected SKUs:</strong> ${(s2.affected_skus || []).join(', ')}</div>
        <div><strong>Affected Shipments:</strong> ${(s2.affected_shipments || []).join(', ')}</div>
        <div><strong>Total At-Risk Value:</strong> <span style="color: var(--accent-rose); font-weight: 700;">$${(s2.total_at_risk_value || 0).toLocaleString()}</span></div>
      </div>
    `;
    stage2Body.innerHTML = html;
  }

  function renderActionCards(orders) {
    actionCardsSection.style.display = "flex";
    actionCardsList.innerHTML = "";

    orders.forEach(ord => {
      const card = document.createElement("div");
      card.className = "action-card";
      card.dataset.orderId = ord.order_id;

      const isVip = ord.customer_tier === "VIP";
      const vipBadge = isVip ? '<span class="badge badge-vip">★ VIP TIER</span>' : '<span class="badge badge-cyan">STANDARD TIER</span>';

      let optionsHtml = '<div class="options-grid">';
      (ord.options || []).forEach(opt => {
        const isRec = opt.action === ord.recommended_option;
        optionsHtml += `
          <div class="option-box ${isRec ? 'recommended' : ''}">
            <div class="option-box-header">
              <span>${opt.action.toUpperCase()}</span>
              ${isRec ? '<span class="rec-pill">RECOMMENDED</span>' : ''}
            </div>
            <div>${opt.tradeoff}</div>
          </div>
        `;
      });
      optionsHtml += '</div>';

      card.innerHTML = `
        <div class="card-top">
          <div class="order-title">
            <h4>Order <span class="record-link" onclick="inspectRecord('${ord.order_id}')">${ord.order_id}</span></h4>
            ${vipBadge}
          </div>
          <div class="urgency-badge">Urgency Score: ${ord.urgency_score}/100</div>
        </div>
        <div class="card-summary">
          📌 <strong>Shortfall &amp; Impact:</strong> ${ord.shortfall_summary}
        </div>
        ${optionsHtml}
        <div class="card-actions">
          <div class="rec-reason">💡 <strong>Why:</strong> ${ord.recommendation_reason}</div>
          <div class="action-buttons">
            <button class="btn btn-success" onclick="handleDecision('${ord.order_id}', '${ord.recommended_option}', 'APPROVED')">Approve Recommended Action</button>
            <button class="btn btn-danger" onclick="handleDecision('${ord.order_id}', '${ord.recommended_option}', 'REJECTED')">Reject</button>
          </div>
        </div>
      `;

      actionCardsList.appendChild(card);
    });
  }

  window.inspectRecord = function(orderId) {
    if (!dataIndex) return;
    const ord = dataIndex.orders.find(o => o.order_id === orderId);
    if (ord) {
      alert(`RECORD DETAILS [${orderId}]:\nCustomer: ${ord.customer_name} (${ord.customer_tier})\nSKU: ${ord.sku} (${ord.sku_name})\nQuantity: ${ord.qty}\nOrder Value: $${ord.order_value}\nPromised Date: ${ord.promised_date}`);
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
          operator_notes: `${decision} by human operator via UI card.`
        })
      });
      const data = await res.json();
      alert(`Decision recorded! Action ${orderId} marked as ${decision}.`);

      // Update card UI state
      const card = document.querySelector(`.action-card[data-order-id="${orderId}"]`);
      if (card) {
        card.style.opacity = "0.6";
        card.style.borderColor = decision === "APPROVED" ? "var(--accent-emerald)" : "var(--accent-rose)";
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
        auditTableBody.innerHTML = '<tr><td colspan="6" class="text-center">No decisions recorded yet.</td></tr>';
        return;
      }

      let html = "";
      actionHistory.forEach(a => {
        const badge = a.status === "APPROVED" ? 'badge-cyan' : 'badge-rose';
        html += `
          <tr>
            <td>${a.id}</td>
            <td>${a.timestamp}</td>
            <td><strong>${a.order_id}</strong></td>
            <td>${a.chosen_action}</td>
            <td><span class="badge ${badge}">${a.status}</span></td>
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
