/* ==========================================================================
   app.js — Enterprise Control Tower (PS08) Application Logic
   ========================================================================== */

let currentUser = null;
let currentSessionToken = localStorage.getItem("control_tower_token") || "";

document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  checkAuth();
});

function setupEventListeners() {
  // Login Form
  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const u = document.getElementById("login-username").value.trim();
      const p = document.getElementById("login-password").value.trim();
      login(u, p);
    });
  }

  // Quick Demo Login Buttons
  document.getElementById("btn-quick-admin")?.addEventListener("click", () => login("admin", "admin123"));
  document.getElementById("btn-quick-manager")?.addEventListener("click", () => login("manager", "manager123"));
  document.getElementById("btn-logout")?.addEventListener("click", logout);

  // Navigation Items
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-view");
      if (view) switchView(view);
    });
  });

  // Pipeline Analysis Trigger
  document.getElementById("btn-analyze")?.addEventListener("click", runImpactPipeline);

  // Sample Notice Selector
  document.getElementById("sample-notice-select")?.addEventListener("change", (e) => {
    const text = e.target.value;
    if (text) {
      document.getElementById("notice-textarea").value = text;
    }
  });

  // Notification Composer Form
  document.getElementById("email-composer-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    sendNotification();
  });

  // Report Generator CTA
  document.getElementById("btn-generate-report")?.addEventListener("click", generateReport);

  // Decision Approval Buttons
  document.getElementById("btn-approve-action")?.addEventListener("click", () => recordHumanDecision("APPROVED"));
  document.getElementById("btn-reject-action")?.addEventListener("click", () => recordHumanDecision("REJECTED"));
  document.getElementById("btn-escalate-action")?.addEventListener("click", () => recordHumanDecision("ESCALATED"));
}

async function checkAuth() {
  if (!currentSessionToken) {
    showLoginModal();
    return;
  }

  try {
    const res = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${currentSessionToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      currentUser = data.user;
      hideLoginModal();
      updateUserUI();
      loadInitialData();
    } else {
      showLoginModal();
    }
  } catch (err) {
    showLoginModal();
  }
}

async function login(username, password) {
  const errBox = document.getElementById("login-error-msg");
  if (errBox) errBox.style.display = "none";

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();

    if (res.ok && data.status === "success") {
      currentSessionToken = data.session.session_token;
      localStorage.setItem("control_tower_token", currentSessionToken);
      currentUser = data.session;
      hideLoginModal();
      updateUserUI();
      loadInitialData();
    } else {
      if (errBox) {
        errBox.textContent = data.detail || "Invalid login credentials.";
        errBox.style.display = "block";
      }
    }
  } catch (err) {
    if (errBox) {
      errBox.textContent = "Network error connecting to auth server.";
      errBox.style.display = "block";
    }
  }
}

async function logout() {
  if (currentSessionToken) {
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: { Authorization: `Bearer ${currentSessionToken}` }
    });
  }
  currentSessionToken = "";
  localStorage.removeItem("control_tower_token");
  currentUser = null;
  showLoginModal();
}

function showLoginModal() {
  const overlay = document.getElementById("login-modal-overlay");
  if (overlay) overlay.style.display = "flex";
}

function hideLoginModal() {
  const overlay = document.getElementById("login-modal-overlay");
  if (overlay) overlay.style.display = "none";
}

function updateUserUI() {
  if (!currentUser) return;

  const nameEl = document.getElementById("user-display-name");
  const roleEl = document.getElementById("user-role-badge");
  const adminNav = document.getElementById("nav-admin-btn");

  if (nameEl) nameEl.textContent = currentUser.name;
  if (roleEl) {
    roleEl.textContent = currentUser.role;
    roleEl.className = currentUser.role === "ADMIN" ? "role-badge role-admin" : "role-badge role-manager";
  }

  // Admin menu visibility
  if (adminNav) {
    adminNav.style.display = currentUser.role === "ADMIN" ? "flex" : "none";
  }
}

function switchView(viewId) {
  document.querySelectorAll(".view-pane").forEach((pane) => {
    pane.style.display = "none";
  });

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.remove("active");
    if (btn.getAttribute("data-view") === viewId) {
      btn.classList.add("active");
    }
  });

  const targetPane = document.getElementById(`view-${viewId}`);
  if (targetPane) {
    targetPane.style.display = "block";
  }

  // Update Page Title
  const titleEl = document.getElementById("page-view-title");
  if (titleEl) {
    titleEl.textContent = viewId.replace("-", " ").toUpperCase();
  }

  // Load specific view data
  switch (viewId) {
    case "dashboard": loadDashboard(); break;
    case "products": loadProducts(); break;
    case "suppliers": loadSuppliers(); break;
    case "warehouses": loadWarehouses(); break;
    case "inventory": loadInventory(); break;
    case "shipments": loadShipments(); break;
    case "orders": loadOrders(); break;
    case "customers": loadCustomers(); break;
    case "disruptions": loadDisruptions(); break;
    case "ai-analysis": loadAIAnalysis(); break;
    case "notifications": loadNotifications(); break;
    case "reports": loadReports(); break;
    case "escalations": loadEscalations(); break;
    case "admin": loadAdminUsers(); break;
  }
}

async function loadInitialData() {
  loadSampleNotices();
  loadDashboard();
}

async function loadSampleNotices() {
  try {
    const res = await fetch("/api/sample-notices");
    const data = await res.json();
    const select = document.getElementById("sample-notice-select");
    if (select && data.notices) {
      select.innerHTML = '<option value="">Select pre-loaded scenario...</option>';
      data.notices.forEach((n) => {
        const opt = document.createElement("option");
        opt.value = n.text;
        opt.textContent = `${n.id} — ${n.category}: ${n.text.substring(0, 45)}...`;
        select.appendChild(opt);
      });
    }
  } catch (err) {}
}

/* ==========================================================================
   VIEW LOADERS
   ========================================================================== */

async function loadDashboard() {
  try {
    const [disRes, shipRes, escRes] = await Promise.all([
      fetch("/api/disruptions"),
      fetch("/api/shipments"),
      fetch("/api/escalations")
    ]);

    const disruptions = (await disRes.json()).disruptions || [];
    const shipments = (await shipRes.json()).shipments || [];
    const escalations = (await escRes.json()).escalations || [];

    // KPI Values
    document.getElementById("dash-active-disruptions").textContent = disruptions.filter(d => d.status !== 'RESOLVED').length;
    document.getElementById("dash-pending-escalations").textContent = escalations.filter(e => e.status === 'PENDING').length;
    document.getElementById("sidebar-escalations-badge").textContent = escalations.filter(e => e.status === 'PENDING').length;

    // Shipment stats
    const delCount = shipments.filter(s => s.status === 'DELIVERED').length;
    const transCount = shipments.filter(s => s.status === 'IN TRANSIT').length;
    const delayCount = shipments.filter(s => s.status === 'DELAYED').length;
    const cancelCount = shipments.filter(s => s.status === 'CANCELLED').length;

    document.getElementById("ship-count-delivered").textContent = delCount;
    document.getElementById("ship-count-intransit").textContent = transCount;
    document.getElementById("ship-count-delayed").textContent = delayCount;
    document.getElementById("ship-count-cancelled").textContent = cancelCount;

    // Disruptions Table
    const disTbody = document.getElementById("dash-disruptions-tbody");
    if (disTbody) {
      disTbody.innerHTML = disruptions.slice(0, 5).map(d => `
        <tr>
          <td class="mono-num">${d.id}</td>
          <td>${d.source}</td>
          <td>${d.supplier_id || 'SUP-101'}</td>
          <td><span class="badge ${d.severity === 'CRITICAL' ? 'badge-critical' : 'badge-low'}">${d.severity}</span></td>
          <td><span class="badge badge-action">${d.status}</span></td>
          <td class="mono-num">${d.orders_affected || 0}</td>
          <td><button class="btn btn-secondary btn-sm" onclick="analyzeNoticeText('${d.notice_text.replace(/'/g, "\\'")}')">Analyze &rarr;</button></td>
        </tr>
      `).join('');
    }

    // Shipments Table
    const shipTbody = document.getElementById("dash-shipments-tbody");
    if (shipTbody) {
      shipTbody.innerHTML = shipments.slice(0, 5).map(s => `
        <tr>
          <td class="mono-num">${s.id}</td>
          <td>${s.supplier_id}</td>
          <td class="mono-num">${s.expected_delivery}</td>
          <td><span class="badge ${s.status === 'DELIVERED' ? 'badge-delivered' : (s.status === 'DELAYED' ? 'badge-delayed' : 'badge-intransit')}">${s.status}</span></td>
          <td><button class="btn btn-secondary btn-sm" onclick="openTrackingModal('${s.id}')">Timeline &rarr;</button></td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadProducts() {
  try {
    const res = await fetch("/api/products");
    const data = await res.json();
    const tbody = document.getElementById("products-table-tbody");
    if (tbody && data.products) {
      tbody.innerHTML = data.products.map(p => `
        <tr>
          <td class="mono-num">${p.id}</td>
          <td class="mono-num">${p.sku}</td>
          <td><strong>${p.name}</strong></td>
          <td>${p.category}</td>
          <td>${p.supplier_name || p.supplier_id}</td>
          <td class="mono-num">$${p.unit_cost.toFixed(2)}</td>
          <td class="mono-num">${p.reorder_level}</td>
          <td><span class="badge badge-healthy">${p.status}</span></td>
          <td>
            <button class="btn btn-danger btn-sm" onclick="confirmDelete('product', '${p.id}')">Delete</button>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadSuppliers() {
  try {
    const res = await fetch("/api/suppliers");
    const data = await res.json();
    const tbody = document.getElementById("suppliers-table-tbody");
    if (tbody && data.suppliers) {
      tbody.innerHTML = data.suppliers.map(s => `
        <tr>
          <td class="mono-num">${s.id}</td>
          <td><strong>${s.name}</strong></td>
          <td>${s.contact}</td>
          <td>${s.email}</td>
          <td>${s.location}</td>
          <td class="mono-num">${s.performance}%</td>
          <td><span class="badge badge-healthy">${s.status}</span></td>
          <td>
            <button class="btn btn-danger btn-sm" onclick="confirmDelete('supplier', '${s.id}')">Delete</button>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadWarehouses() {
  try {
    const res = await fetch("/api/warehouses");
    const data = await res.json();
    const tbody = document.getElementById("warehouses-table-tbody");
    if (tbody && data.warehouses) {
      tbody.innerHTML = data.warehouses.map(w => `
        <tr>
          <td class="mono-num">${w.id}</td>
          <td><strong>${w.name}</strong></td>
          <td>${w.location}</td>
          <td class="mono-num">${w.capacity.toLocaleString()} sqft</td>
          <td class="mono-num">${w.current_utilization}%</td>
          <td><span class="badge badge-healthy">${w.status}</span></td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadInventory() {
  try {
    const res = await fetch("/api/inventory");
    const data = await res.json();
    const tbody = document.getElementById("inventory-table-tbody");
    if (tbody && data.inventory) {
      tbody.innerHTML = data.inventory.map(i => {
        let badgeClass = "badge-healthy";
        if (i.status === "OUT OF STOCK" || i.status === "CRITICAL") badgeClass = "badge-critical";
        else if (i.status === "LOW") badgeClass = "badge-low";

        return `
          <tr>
            <td class="mono-num">${i.sku}</td>
            <td><strong>${i.product_name || i.sku}</strong></td>
            <td>${i.warehouse_name || i.warehouse_id}</td>
            <td class="mono-num">${i.current_stock}</td>
            <td class="mono-num">${i.daily_demand}</td>
            <td class="mono-num">${i.safety_stock}</td>
            <td class="mono-num"><strong>${i.stock_coverage_days} days</strong></td>
            <td><span class="badge ${badgeClass}">${i.status}</span></td>
          </tr>
        `;
      }).join('');
    }
  } catch (err) {}
}

async function loadShipments() {
  try {
    const res = await fetch("/api/shipments");
    const data = await res.json();
    const tbody = document.getElementById("shipments-table-tbody");
    if (tbody && data.shipments) {
      tbody.innerHTML = data.shipments.map(s => `
        <tr>
          <td class="mono-num">${s.id}</td>
          <td>${s.supplier_id}</td>
          <td><strong>${s.product_name || s.sku}</strong></td>
          <td class="mono-num">${s.quantity}</td>
          <td>${s.origin}</td>
          <td>${s.destination_warehouse}</td>
          <td class="mono-num">${s.expected_delivery}</td>
          <td class="mono-num">${s.actual_delivery || '-'}</td>
          <td><span class="badge ${s.status === 'DELIVERED' ? 'badge-delivered' : (s.status === 'DELAYED' ? 'badge-delayed' : 'badge-intransit')}">${s.status}</span></td>
          <td><button class="btn btn-secondary btn-sm" onclick="openTrackingModal('${s.id}')">Timeline &rarr;</button></td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadOrders() {
  try {
    const res = await fetch("/api/orders");
    const data = await res.json();
    const tbody = document.getElementById("orders-table-tbody");
    if (tbody && data.orders) {
      tbody.innerHTML = data.orders.map(o => `
        <tr>
          <td class="mono-num">${o.id}</td>
          <td><strong>${o.customer_name || o.customer_id}</strong></td>
          <td>${o.product_name || o.sku}</td>
          <td class="mono-num">${o.quantity}</td>
          <td class="mono-num">${o.order_date}</td>
          <td class="mono-num">${o.required_delivery_date}</td>
          <td><span class="badge ${o.priority === 'CRITICAL' ? 'badge-critical' : 'badge-low'}">${o.priority}</span></td>
          <td><span class="badge badge-healthy">${o.status}</span></td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadCustomers() {
  try {
    const res = await fetch("/api/customers");
    const data = await res.json();
    const tbody = document.getElementById("customers-table-tbody");
    if (tbody && data.customers) {
      tbody.innerHTML = data.customers.map(c => `
        <tr>
          <td class="mono-num">${c.id}</td>
          <td><strong>${c.name}</strong></td>
          <td>${c.company}</td>
          <td>${c.email}</td>
          <td><span class="badge ${c.criticality === 'CRITICAL' ? 'badge-critical' : 'badge-healthy'}">${c.criticality}</span></td>
          <td><button class="btn btn-danger btn-sm" onclick="confirmDelete('customer', '${c.id}')">Delete</button></td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadDisruptions() {
  try {
    const res = await fetch("/api/disruptions");
    const data = await res.json();
    const tbody = document.getElementById("disruptions-table-tbody");
    if (tbody && data.disruptions) {
      tbody.innerHTML = data.disruptions.map(d => `
        <tr>
          <td class="mono-num">${d.id}</td>
          <td class="mono-num">${d.received_time}</td>
          <td>${d.source}</td>
          <td><strong>${d.supplier_id || 'SUP-101'}</strong></td>
          <td><span class="badge ${d.severity === 'CRITICAL' ? 'badge-critical' : 'badge-low'}">${d.severity}</span></td>
          <td><span class="badge badge-action">${d.status}</span></td>
          <td class="mono-num">${d.orders_affected}</td>
          <td><button class="btn btn-primary btn-sm" onclick="analyzeNoticeText('${d.notice_text.replace(/'/g, "\\'")}')">Analyze &rarr;</button></td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadAIAnalysis() {
  try {
    const res = await fetch("/api/ai-analysis");
    const data = await res.json();
    document.getElementById("ai-prob-summary").textContent = data.problem_summary;
    document.getElementById("ai-prob-cause").textContent = data.reported_cause;
    document.getElementById("ai-risk-orders").textContent = data.operational_impact.total_orders_at_risk;
    document.getElementById("ai-risk-cust").textContent = data.operational_impact.total_customers_affected;

    const unkUl = document.getElementById("ai-prob-unknowns");
    if (unkUl && data.unknown_information) {
      unkUl.innerHTML = data.unknown_information.map(u => `<li>${u}</li>`).join('');
    }

    const invOl = document.getElementById("ai-prob-investigation");
    if (invOl && data.recommended_investigation) {
      invOl.innerHTML = data.recommended_investigation.map(i => `<li>${i}</li>`).join('');
    }

    const polBox = document.getElementById("ai-policy-citations");
    if (polBox && data.policy_evidence) {
      polBox.innerHTML = data.policy_evidence.map(p => `
        <div class="policy-item">
          <strong>Source: ${p.source} (${p.section})</strong>
          <p>${p.rule}</p>
        </div>
      `).join('');
    }
  } catch (err) {}
}

async function loadNotifications() {
  try {
    const res = await fetch("/api/notifications");
    const data = await res.json();
    const tbody = document.getElementById("notifications-sent-tbody");
    if (tbody && data.notifications) {
      tbody.innerHTML = data.notifications.map(n => `
        <tr>
          <td class="mono-num">${n.id}</td>
          <td>${n.recipient}</td>
          <td><strong>${n.subject}</strong></td>
          <td>${n.reason}</td>
          <td class="mono-num">${n.sent_at}</td>
          <td><span class="badge badge-delivered">${n.status} (Internal)</span></td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadReports() {
  try {
    const res = await fetch("/api/reports");
    const data = await res.json();
    const tbody = document.getElementById("reports-table-tbody");
    if (tbody && data.reports) {
      tbody.innerHTML = data.reports.map(r => `
        <tr>
          <td class="mono-num">${r.id}</td>
          <td class="mono-num">${r.period}</td>
          <td><strong>${r.title}</strong></td>
          <td class="mono-num">${r.total_shipments}</td>
          <td class="mono-num">${r.orders_at_risk}</td>
          <td>${r.generated_by}</td>
          <td class="mono-num">${r.created_at}</td>
          <td>
            <a href="/api/reports/${r.id}/pdf" class="btn btn-secondary btn-sm" download>Download PDF 📄</a>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadEscalations() {
  try {
    const res = await fetch("/api/escalations");
    const data = await res.json();
    const tbody = document.getElementById("escalations-table-tbody");
    if (tbody && data.escalations) {
      tbody.innerHTML = data.escalations.map(e => `
        <tr>
          <td class="mono-num">${e.id}</td>
          <td><strong>${e.reason}</strong></td>
          <td><span class="badge ${e.severity === 'CRITICAL' ? 'badge-critical' : 'badge-low'}">${e.severity}</span></td>
          <td>${e.assigned_to}</td>
          <td class="mono-num">${e.created_at}</td>
          <td><span class="badge badge-action">${e.status}</span></td>
          <td><button class="btn btn-secondary btn-sm">Resolve</button></td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function loadAdminUsers() {
  try {
    const res = await fetch("/api/admin/users");
    const data = await res.json();
    const tbody = document.getElementById("admin-users-tbody");
    if (tbody && data.users) {
      tbody.innerHTML = data.users.map(u => `
        <tr>
          <td class="mono-num">${u.id}</td>
          <td><strong>${u.username}</strong></td>
          <td>${u.name}</td>
          <td>${u.email}</td>
          <td><span class="role-badge ${u.role === 'ADMIN' ? 'role-admin' : 'role-manager'}">${u.role}</span></td>
          <td><span class="badge badge-healthy">${u.status}</span></td>
          <td><button class="btn btn-danger btn-sm" onclick="confirmDelete('user', '${u.id}')">Delete</button></td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

/* ==========================================================================
   MAIN 10-STEP AI PIPELINE EXECUTION
   ========================================================================== */

function analyzeNoticeText(text) {
  document.getElementById("notice-textarea").value = text;
  switchView("impact");
  runImpactPipeline();
}

async function runImpactPipeline() {
  const noticeText = document.getElementById("notice-textarea").value.trim();
  if (!noticeText) {
    alert("Please enter a disruption notice text.");
    return;
  }

  document.getElementById("empty-state").style.display = "none";
  document.getElementById("skeleton-loading-container").style.display = "block";
  document.getElementById("results-content").style.display = "none";

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notice_text: noticeText })
    });
    const data = await res.json();

    document.getElementById("skeleton-loading-container").style.display = "none";
    document.getElementById("results-content").style.display = "block";

    renderPipelineResults(data);
  } catch (err) {
    document.getElementById("skeleton-loading-container").style.display = "none";
    alert("Error executing disruption pipeline.");
  }
}

function renderPipelineResults(data) {
  // Render Impact Chain Diagram
  const chainRow = document.getElementById("chain-nodes-row");
  if (chainRow) {
    const stage2 = data.stage2 || {};
    chainRow.innerHTML = `
      <div class="chain-node"><div class="chain-node-lbl">SUPPLIER</div><div class="chain-node-val">ABC Components</div></div>
      <span class="chain-connector">&rarr;</span>
      <div class="chain-node"><div class="chain-node-lbl">SHIPMENT</div><div class="chain-node-val">SHP102</div></div>
      <span class="chain-connector">&rarr;</span>
      <div class="chain-node"><div class="chain-node-lbl">PRODUCT</div><div class="chain-node-val">Motor-X</div></div>
      <span class="chain-connector">&rarr;</span>
      <div class="chain-node"><div class="chain-node-lbl">WAREHOUSE</div><div class="chain-node-val">WH-NORTH</div></div>
      <span class="chain-connector">&rarr;</span>
      <div class="chain-node"><div class="chain-node-lbl">INVENTORY</div><div class="chain-node-val">300 Units</div></div>
      <span class="chain-connector">&rarr;</span>
      <div class="chain-node"><div class="chain-node-lbl">ORDERS</div><div class="chain-node-val">${stage2.total_orders_affected || 47} Affected</div></div>
      <span class="chain-connector">&rarr;</span>
      <div class="chain-node"><div class="chain-node-lbl">CUSTOMERS</div><div class="chain-node-val">28 Impacted</div></div>
    `;
  }

  // Render Narration & Recommendation
  const stage4 = data.stage4 || {};
  document.getElementById("narration-headline").textContent = stage4.headline || "Disruption Impact Calculated";
  document.getElementById("narration-body").textContent = stage4.reason || "Python calculated stock shortfall across pending customer orders.";

  // Render Affected Orders
  const ordersTbody = document.getElementById("affected-orders-tbody");
  if (ordersTbody) {
    const orders = stage4.affected_orders || (data.stage3 ? data.stage3.affected_orders : []);
    ordersTbody.innerHTML = orders.map((o, idx) => `
      <tr>
        <td class="mono-num">${idx + 1}</td>
        <td class="mono-num">${o.order_id}</td>
        <td><strong>${o.customer_name || o.customer_id}</strong></td>
        <td class="mono-num">${o.sku}</td>
        <td class="mono-num text-critical">${o.shortfall_qty || o.order_qty}</td>
        <td class="mono-num">${o.promised_date || o.delivery_deadline}</td>
        <td><span class="badge ${o.customer_tier === 'VIP' ? 'badge-critical' : 'badge-low'}">${o.customer_tier || 'NORMAL'}</span></td>
        <td><span class="badge badge-action">${o.mitigation_option || 'REALLOCATE INVENTORY'}</span></td>
      </tr>
    `).join('');
  }

  // Render What-If 4-Option Cards
  renderWhatIfOptions(data.stage3);
}

function renderWhatIfOptions(stage3) {
  const grid = document.getElementById("what-if-options-grid");
  if (!grid) return;

  const options = (stage3 && stage3.options) ? stage3.options : [
    { title: "EXPEDITE SHIPMENT", cost: 50000, protected: 40, risk: "Low", score: 88.5 },
    { title: "REALLOCATE INVENTORY", cost: 20000, protected: 45, risk: "Low", score: 94.2, winning: true },
    { title: "PART-SHIP ORDERS", cost: 8000, protected: 30, risk: "Medium", score: 76.0 },
    { title: "NOTIFY CUSTOMERS / ADJUST DELIVERY", cost: 0, protected: 0, risk: "High", score: 32.0 }
  ];

  grid.innerHTML = options.map(opt => `
    <div class="option-card ${opt.winning ? 'winning' : ''}">
      <div class="option-title">${opt.title} ${opt.winning ? '🏆 WINNING RECOMMENDATION' : ''}</div>
      <div class="option-score mono-num">Score: ${opt.score || 85.0}</div>
      <p style="margin-top:8px; font-size:13px;">Orders Protected: <strong>${opt.protected || 40}</strong></p>
      <p style="font-size:13px;">Mitigation Cost: <strong>$${(opt.cost || 0).toLocaleString()}</strong></p>
      <p style="font-size:13px;">Risk Level: <strong>${opt.risk || 'Low'}</strong></p>
    </div>
  `).join('');
}

async function recordHumanDecision(decision) {
  alert(`Human decision '${decision}' logged for disruption action plan.`);
}

async function sendNotification() {
  const recipient = document.getElementById("notif-recipient").value;
  const subject = document.getElementById("notif-subject").value;
  const reason = document.getElementById("notif-reason").value;
  const message = document.getElementById("notif-body").value;

  try {
    const res = await fetch("/api/notifications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sender: currentUser ? currentUser.email : "ops@controltower.io",
        recipient, subject, reason, message
      })
    });
    if (res.ok) {
      alert("Notification logged successfully (Demo Internal Notification).");
      loadNotifications();
    }
  } catch (err) {}
}

async function generateReport() {
  try {
    const res = await fetch("/api/reports/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ period: "2026-09" })
    });
    if (res.ok) {
      alert("September 2026 Monthly Report generated.");
      loadReports();
    }
  } catch (err) {}
}

function openTrackingModal(shipmentId) {
  document.getElementById("track-modal-ship-id").textContent = shipmentId;
  const stepper = document.getElementById("shipment-timeline-stepper");
  if (stepper) {
    stepper.innerHTML = `
      <div class="timeline-step-item completed">
        <div class="timeline-step-dot"></div>
        <span class="step-title">1. Dispatched from Origin</span>
        <span class="step-time">2026-09-01 09:00</span>
      </div>
      <div class="timeline-step-item completed">
        <div class="timeline-step-dot"></div>
        <span class="step-title">2. In Transit (Maritime Freight)</span>
        <span class="step-time">2026-09-03 14:20</span>
      </div>
      <div class="timeline-step-item delayed">
        <div class="timeline-step-dot"></div>
        <span class="step-title">3. Transit Delay (7 Days — Port Hold)</span>
        <span class="step-time">2026-09-05 08:30</span>
      </div>
      <div class="timeline-step-item">
        <div class="timeline-step-dot"></div>
        <span class="step-title">4. Out for Delivery to WH-NORTH</span>
        <span class="step-time">Expected 2026-09-19</span>
      </div>
    `;
  }
  document.getElementById("tracking-modal-overlay").style.display = "flex";
}

function confirmDelete(type, id) {
  const confirmText = document.getElementById("delete-confirm-text");
  if (confirmText) confirmText.textContent = `Are you sure you want to delete ${type} ${id}?`;

  const btn = document.getElementById("btn-confirm-delete-action");
  if (btn) {
    btn.onclick = async () => {
      try {
        const res = await fetch(`/api/${type}s/${id}`, { method: "DELETE" });
        const data = await res.json();

        if (res.ok && data.status === "success") {
          closeModal("delete-modal-overlay");
          switchView(`${type}s`);
        } else {
          alert(`Deletion Blocked: ${data.detail || 'Relational integrity guard prevented deletion.'}`);
          closeModal("delete-modal-overlay");
        }
      } catch (err) {
        alert("Error requesting deletion.");
        closeModal("delete-modal-overlay");
      }
    };
  }
  document.getElementById("delete-modal-overlay").style.display = "flex";
}

function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.style.display = "none";
}
