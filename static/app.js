/* ==========================================================================
   app.js — Enterprise Supply Chain Control Tower (PS08) Application Logic
   ========================================================================== */

let currentUser = null;
let currentSessionToken = localStorage.getItem("control_tower_token") || "";

document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  checkAuth();
});

function setupEventListeners() {
  // Login Form Submission
  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value.trim();
      login(email, password);
    });
  }

  // Registration Form Submission
  const regForm = document.getElementById("register-form");
  if (regForm) {
    regForm.addEventListener("submit", (e) => {
      e.preventDefault();
      register();
    });
  }

  // Toggle Login/Register Cards
  document.getElementById("link-show-register")?.addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("auth-card-login").style.display = "none";
    document.getElementById("auth-card-register").style.display = "block";
  });

  document.getElementById("link-show-login")?.addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("auth-card-register").style.display = "none";
    document.getElementById("auth-card-login").style.display = "block";
  });

  // Password Visibility Toggle
  document.getElementById("btn-toggle-login-pw")?.addEventListener("click", () => {
    const pwInput = document.getElementById("login-password");
    if (pwInput.type === "password") {
      pwInput.type = "text";
    } else {
      pwInput.type = "password";
    }
  });

  // Product Listeners
  document.getElementById("btn-add-product")?.addEventListener("click", () => openAddProductModal());
  document.getElementById("form-add-product")?.addEventListener("submit", (e) => submitAddProduct(e));
  document.getElementById("form-edit-product")?.addEventListener("submit", (e) => submitEditProduct(e));

  // Module Add Listeners
  document.getElementById("btn-add-supplier")?.addEventListener("click", () => openAddSupplierModal());
  document.getElementById("btn-add-warehouse")?.addEventListener("click", () => openAddWarehouseModal());
  document.getElementById("btn-add-inventory")?.addEventListener("click", () => openAddInventoryModal());
  document.getElementById("btn-add-shipment")?.addEventListener("click", () => openAddShipmentModal());
  document.getElementById("btn-add-order")?.addEventListener("click", () => openAddOrderModal());
  document.getElementById("btn-add-customer")?.addEventListener("click", () => openAddCustomerModal());

  // Quick Manager Demo Login Button
  document.getElementById("btn-quick-manager")?.addEventListener("click", () => {
    document.getElementById("login-email").value = "ops@controltower.io";
    document.getElementById("login-password").value = "manager123";
    login("ops@controltower.io", "manager123");
  });

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

async function register() {
  const name = document.getElementById("reg-name").value.trim();
  const email = document.getElementById("reg-email").value.trim();
  const password = document.getElementById("reg-password").value.trim();
  const confirmPassword = document.getElementById("reg-confirm-password").value.trim();
  const department = document.getElementById("reg-department").value.trim();
  const phone = document.getElementById("reg-phone").value.trim();

  const errBox = document.getElementById("reg-error-msg");
  const succBox = document.getElementById("reg-success-msg");
  if (errBox) errBox.style.display = "none";
  if (succBox) succBox.style.display = "none";

  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name, email, password, confirm_password: confirmPassword, department, phone
      })
    });
    const data = await res.json();

    if (res.ok && data.status === "success") {
      if (succBox) {
        succBox.textContent = data.message || "Account created successfully. Please sign in.";
        succBox.style.display = "block";
      }
      setTimeout(() => {
        document.getElementById("login-email").value = email;
        document.getElementById("auth-card-register").style.display = "none";
        document.getElementById("auth-card-login").style.display = "block";
      }, 1500);
    } else {
      if (errBox) {
        errBox.textContent = data.detail || "Registration failed.";
        errBox.style.display = "block";
      }
    }
  } catch (err) {
    if (errBox) {
      errBox.textContent = "Network error connecting to server.";
      errBox.style.display = "block";
    }
  }
}

async function login(email, password) {
  const errBox = document.getElementById("login-error-msg");
  if (errBox) errBox.style.display = "none";

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
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
        errBox.textContent = data.detail || "Invalid email or password.";
        errBox.style.display = "block";
      }
    }
  } catch (err) {
    if (errBox) {
      errBox.textContent = "Invalid email or password.";
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
  document.getElementById("auth-card-register").style.display = "none";
  document.getElementById("auth-card-login").style.display = "block";
}

function hideLoginModal() {
  const overlay = document.getElementById("login-modal-overlay");
  if (overlay) overlay.style.display = "none";
}

function updateUserUI() {
  if (!currentUser) return;

  const nameEl = document.getElementById("user-display-name");
  const roleEl = document.getElementById("user-role-badge");

  if (nameEl) nameEl.textContent = currentUser.name;
  if (roleEl) {
    roleEl.textContent = currentUser.role || "MANAGER";
    roleEl.className = "role-badge role-manager";
  }
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${currentSessionToken}`
  };
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

  const titleEl = document.getElementById("page-view-title");
  if (titleEl) {
    titleEl.textContent = viewId.replace("-", " ").toUpperCase();
  }

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
  }
}

async function loadInitialData() {
  loadSampleNotices();
  loadDashboard();
}

async function loadSampleNotices() {
  try {
    const res = await fetch("/api/sample-notices", { headers: authHeaders() });
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
   VIEW LOADERS & MODULE CRUD
   ========================================================================== */

async function loadDashboard() {
  try {
    const [disRes, shipRes, escRes] = await Promise.all([
      fetch("/api/disruptions", { headers: authHeaders() }),
      fetch("/api/shipments", { headers: authHeaders() }),
      fetch("/api/escalations", { headers: authHeaders() })
    ]);

    const disruptions = (await disRes.json()).disruptions || [];
    const shipments = (await shipRes.json()).shipments || [];
    const escalations = (await escRes.json()).escalations || [];

    document.getElementById("dash-active-disruptions").textContent = disruptions.filter(d => d.status !== 'RESOLVED').length;
    document.getElementById("dash-pending-escalations").textContent = escalations.filter(e => e.status === 'PENDING').length;
    document.getElementById("sidebar-escalations-badge").textContent = escalations.filter(e => e.status === 'PENDING').length;

    const delCount = shipments.filter(s => s.status === 'DELIVERED').length;
    const transCount = shipments.filter(s => s.status === 'IN TRANSIT').length;
    const delayCount = shipments.filter(s => s.status === 'DELAYED').length;
    const cancelCount = shipments.filter(s => s.status === 'CANCELLED').length;

    document.getElementById("ship-count-delivered").textContent = delCount;
    document.getElementById("ship-count-intransit").textContent = transCount;
    document.getElementById("ship-count-delayed").textContent = delayCount;
    document.getElementById("ship-count-cancelled").textContent = cancelCount;

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

/* --- PRODUCT CRUD --- */
async function loadProducts() {
  try {
    const res = await fetch("/api/products", { headers: authHeaders() });
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
            <button class="btn btn-secondary btn-sm" onclick="openEditProductModal('${p.id}')">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="confirmDelete('product', '${p.id}')">Delete</button>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function openAddProductModal() {
  const errBox = document.getElementById("add-p-error");
  if (errBox) errBox.style.display = "none";

  const form = document.getElementById("form-add-product");
  if (form) form.reset();

  const select = document.getElementById("add-p-supplier");
  if (select) {
    select.innerHTML = '<option value="">Loading suppliers...</option>';
    try {
      const res = await fetch("/api/suppliers", { headers: authHeaders() });
      const data = await res.json();
      if (data.suppliers) {
        select.innerHTML = '<option value="">Select Supplier...</option>' +
          data.suppliers.map(s => `<option value="${s.id}">${s.name} (${s.id})</option>`).join('');
      }
    } catch (err) {
      select.innerHTML = '<option value="">Select Supplier...</option>';
    }
  }

  const overlay = document.getElementById("modal-add-product-overlay");
  if (overlay) overlay.style.display = "flex";
}

async function submitAddProduct(e) {
  e.preventDefault();
  const name = document.getElementById("add-p-name").value.trim();
  const sku = document.getElementById("add-p-sku").value.trim();
  const category = document.getElementById("add-p-category").value.trim();
  const supplierId = document.getElementById("add-p-supplier").value;
  const cost = parseFloat(document.getElementById("add-p-cost").value);
  const reorder = parseInt(document.getElementById("add-p-reorder").value || "50");

  const errBox = document.getElementById("add-p-error");
  if (errBox) errBox.style.display = "none";

  if (!name || !sku || !category || !supplierId || isNaN(cost) || cost < 0) {
    if (errBox) {
      errBox.textContent = "Please fill in all required fields with valid values.";
      errBox.style.display = "block";
    }
    return;
  }

  try {
    const res = await fetch("/api/products", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        name, sku, category, supplier_id: supplierId, unit_cost: cost, reorder_level: reorder, status: "ACTIVE"
      })
    });
    const data = await res.json();
    if (res.ok && data.status === "success") {
      closeModal("modal-add-product-overlay");
      alert(data.message || "Product added successfully.");
      loadProducts();
    } else {
      if (errBox) {
        errBox.textContent = data.detail || "Failed to add product.";
        errBox.style.display = "block";
      }
    }
  } catch (err) {
    if (errBox) {
      errBox.textContent = "Network error while creating product.";
      errBox.style.display = "block";
    }
  }
}

async function openEditProductModal(productId) {
  const errBox = document.getElementById("edit-p-error");
  if (errBox) errBox.style.display = "none";

  try {
    const res = await fetch("/api/products", { headers: authHeaders() });
    const data = await res.json();
    const product = (data.products || []).find(p => p.id === productId);
    if (!product) {
      alert("Product not found.");
      return;
    }

    document.getElementById("edit-p-id").value = product.id;
    document.getElementById("edit-p-name").value = product.name;
    document.getElementById("edit-p-sku").value = product.sku;
    document.getElementById("edit-p-category").value = product.category;
    document.getElementById("edit-p-cost").value = product.unit_cost;
    document.getElementById("edit-p-reorder").value = product.reorder_level || 50;

    const select = document.getElementById("edit-p-supplier");
    if (select) {
      const supRes = await fetch("/api/suppliers", { headers: authHeaders() });
      const supData = await supRes.json();
      if (supData.suppliers) {
        select.innerHTML = supData.suppliers.map(s => 
          `<option value="${s.id}" ${s.id === product.supplier_id ? 'selected' : ''}>${s.name} (${s.id})</option>`
        ).join('');
      }
    }

    const overlay = document.getElementById("modal-edit-product-overlay");
    if (overlay) overlay.style.display = "flex";
  } catch (err) {
    alert("Error fetching product details.");
  }
}

async function submitEditProduct(e) {
  e.preventDefault();
  const productId = document.getElementById("edit-p-id").value;
  const name = document.getElementById("edit-p-name").value.trim();
  const sku = document.getElementById("edit-p-sku").value.trim();
  const category = document.getElementById("edit-p-category").value.trim();
  const supplierId = document.getElementById("edit-p-supplier").value;
  const cost = parseFloat(document.getElementById("edit-p-cost").value);
  const reorder = parseInt(document.getElementById("edit-p-reorder").value || "50");

  const errBox = document.getElementById("edit-p-error");
  if (errBox) errBox.style.display = "none";

  if (!name || !sku || !category || !supplierId || isNaN(cost) || cost < 0) {
    if (errBox) {
      errBox.textContent = "Please fill in all required fields with valid values.";
      errBox.style.display = "block";
    }
    return;
  }

  try {
    const res = await fetch(`/api/products/${productId}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({
        id: productId, name, sku, category, supplier_id: supplierId, unit_cost: cost, reorder_level: reorder, status: "ACTIVE"
      })
    });
    const data = await res.json();
    if (res.ok && data.status === "success") {
      closeModal("modal-edit-product-overlay");
      alert(data.message || "Product updated successfully.");
      loadProducts();
    } else {
      if (errBox) {
        errBox.textContent = data.detail || "Failed to update product.";
        errBox.style.display = "block";
      }
    }
  } catch (err) {
    if (errBox) {
      errBox.textContent = "Network error while updating product.";
      errBox.style.display = "block";
    }
  }
}

/* --- SUPPLIERS CRUD --- */
async function loadSuppliers() {
  try {
    const res = await fetch("/api/suppliers", { headers: authHeaders() });
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
            <button class="btn btn-secondary btn-sm" onclick="openEditSupplierModal('${s.id}')">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="confirmDelete('supplier', '${s.id}')">Delete</button>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function openAddSupplierModal() {
  const name = prompt("Supplier Name:");
  if (!name) return;
  const contact = prompt("Contact Person Name:");
  if (!contact) return;
  const email = prompt("Email Address:");
  if (!email) return;
  const location = prompt("Location / Region:");
  if (!location) return;

  try {
    const res = await fetch("/api/suppliers", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ name, contact, email, location, performance: 95.0, status: "ACTIVE" })
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || "Supplier added successfully.");
      loadSuppliers();
    } else {
      alert(data.detail || "Error adding supplier.");
    }
  } catch (err) {
    alert("Network error creating supplier.");
  }
}

async function openEditSupplierModal(supplierId) {
  try {
    const res = await fetch("/api/suppliers", { headers: authHeaders() });
    const data = await res.json();
    const supplier = (data.suppliers || []).find(s => s.id === supplierId);
    if (!supplier) return alert("Supplier not found.");

    const name = prompt("Edit Supplier Name:", supplier.name);
    if (!name) return;
    const contact = prompt("Edit Contact Person:", supplier.contact);
    if (!contact) return;
    const email = prompt("Edit Email Address:", supplier.email);
    if (!email) return;
    const location = prompt("Edit Location:", supplier.location);
    if (!location) return;

    const putRes = await fetch(`/api/suppliers/${supplierId}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ name, contact, email, location, performance: supplier.performance, status: supplier.status })
    });
    const putData = await putRes.json();
    if (putRes.ok) {
      alert(putData.message || "Supplier updated successfully.");
      loadSuppliers();
    } else {
      alert(putData.detail || "Error updating supplier.");
    }
  } catch (err) {
    alert("Network error updating supplier.");
  }
}

/* --- WAREHOUSES CRUD --- */
async function loadWarehouses() {
  try {
    const res = await fetch("/api/warehouses", { headers: authHeaders() });
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
          <td>
            <button class="btn btn-secondary btn-sm" onclick="openEditWarehouseModal('${w.id}')">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="confirmDelete('warehouse', '${w.id}')">Delete</button>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function openAddWarehouseModal() {
  const name = prompt("Warehouse / Facility Name:");
  if (!name) return;
  const location = prompt("Location:");
  if (!location) return;
  const capacityStr = prompt("Total Capacity (sqft):", "50000");
  if (!capacityStr) return;
  const capacity = parseInt(capacityStr);

  try {
    const res = await fetch("/api/warehouses", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ name, location, capacity, current_utilization: 50.0, status: "ACTIVE" })
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || "Warehouse added successfully.");
      loadWarehouses();
    } else {
      alert(data.detail || "Error adding warehouse.");
    }
  } catch (err) {
    alert("Network error creating warehouse.");
  }
}

async function openEditWarehouseModal(warehouseId) {
  try {
    const res = await fetch("/api/warehouses", { headers: authHeaders() });
    const data = await res.json();
    const warehouse = (data.warehouses || []).find(w => w.id === warehouseId);
    if (!warehouse) return alert("Warehouse not found.");

    const name = prompt("Edit Facility Name:", warehouse.name);
    if (!name) return;
    const location = prompt("Edit Location:", warehouse.location);
    if (!location) return;
    const capacityStr = prompt("Edit Capacity (sqft):", warehouse.capacity);
    if (!capacityStr) return;
    const capacity = parseInt(capacityStr);

    const putRes = await fetch(`/api/warehouses/${warehouseId}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ name, location, capacity, current_utilization: warehouse.current_utilization, status: warehouse.status })
    });
    const putData = await putRes.json();
    if (putRes.ok) {
      alert(putData.message || "Warehouse updated successfully.");
      loadWarehouses();
    } else {
      alert(putData.detail || "Error updating warehouse.");
    }
  } catch (err) {
    alert("Network error updating warehouse.");
  }
}

/* --- INVENTORY CRUD --- */
async function loadInventory() {
  try {
    const res = await fetch("/api/inventory", { headers: authHeaders() });
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
            <td>
              <button class="btn btn-secondary btn-sm" onclick="openEditInventoryModal('${i.id}')">Edit</button>
              <button class="btn btn-danger btn-sm" onclick="confirmDelete('inventory', '${i.id}')">Delete</button>
            </td>
          </tr>
        `;
      }).join('');
    }
  } catch (err) {}
}

async function openAddInventoryModal() {
  const productId = prompt("Product ID (e.g. PRD-SKU-101):");
  if (!productId) return;
  const warehouseId = prompt("Warehouse ID (e.g. WH-NORTH):");
  if (!warehouseId) return;
  const stockStr = prompt("Current Stock Quantity:", "500");
  if (!stockStr) return;
  const demandStr = prompt("Daily Demand Quantity:", "25");
  if (!demandStr) return;
  const safetyStr = prompt("Safety Stock Quantity:", "100");

  try {
    const res = await fetch("/api/inventory", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        product_id: productId, warehouse_id: warehouseId,
        current_stock: parseInt(stockStr), daily_demand: parseInt(demandStr), safety_stock: parseInt(safetyStr || "0")
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || "Inventory allocation added successfully.");
      loadInventory();
    } else {
      alert(data.detail || "Error adding inventory.");
    }
  } catch (err) {
    alert("Network error creating inventory allocation.");
  }
}

async function openEditInventoryModal(inventoryId) {
  try {
    const res = await fetch("/api/inventory", { headers: authHeaders() });
    const data = await res.json();
    const item = (data.inventory || []).find(i => i.id === inventoryId);
    if (!item) return alert("Inventory item not found.");

    const stockStr = prompt("Edit Current Stock Quantity:", item.current_stock);
    if (!stockStr) return;
    const demandStr = prompt("Edit Daily Demand:", item.daily_demand);
    if (!demandStr) return;
    const safetyStr = prompt("Edit Safety Stock:", item.safety_stock);

    const putRes = await fetch(`/api/inventory/${inventoryId}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({
        product_id: item.product_id, warehouse_id: item.warehouse_id,
        current_stock: parseInt(stockStr), daily_demand: parseInt(demandStr), safety_stock: parseInt(safetyStr || "0")
      })
    });
    const putData = await putRes.json();
    if (putRes.ok) {
      alert(putData.message || "Inventory updated successfully.");
      loadInventory();
    } else {
      alert(putData.detail || "Error updating inventory.");
    }
  } catch (err) {
    alert("Network error updating inventory.");
  }
}

/* --- SHIPMENTS CRUD --- */
async function loadShipments() {
  try {
    const res = await fetch("/api/shipments", { headers: authHeaders() });
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
          <td>
            <button class="btn btn-secondary btn-sm" onclick="openTrackingModal('${s.id}')">Timeline</button>
            <button class="btn btn-secondary btn-sm" onclick="openEditShipmentModal('${s.id}')">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="confirmDelete('shipment', '${s.id}')">Delete</button>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function openAddShipmentModal() {
  const supplierId = prompt("Supplier ID (e.g. SUP-101):");
  if (!supplierId) return;
  const productId = prompt("Product ID (e.g. PRD-SKU-101):");
  if (!productId) return;
  const qtyStr = prompt("Quantity:", "1000");
  if (!qtyStr) return;
  const origin = prompt("Origin City / Location:", "Berlin Depot");
  if (!origin) return;
  const destWh = prompt("Destination Warehouse ID:", "WH-NORTH");
  if (!destWh) return;
  const eta = prompt("Expected Delivery Date (YYYY-MM-DD):", "2026-09-20");
  if (!eta) return;

  try {
    const res = await fetch("/api/shipments", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        supplier_id: supplierId, product_id: productId, quantity: parseInt(qtyStr),
        origin, destination_warehouse_id: destWh, expected_delivery: eta, status: "PLANNED"
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || "Shipment created successfully.");
      loadShipments();
    } else {
      alert(data.detail || "Error creating shipment.");
    }
  } catch (err) {
    alert("Network error creating shipment.");
  }
}

async function openEditShipmentModal(shipmentId) {
  try {
    const res = await fetch("/api/shipments", { headers: authHeaders() });
    const data = await res.json();
    const item = (data.shipments || []).find(s => s.id === shipmentId);
    if (!item) return alert("Shipment not found.");

    const qtyStr = prompt("Edit Quantity:", item.quantity);
    if (!qtyStr) return;
    const eta = prompt("Edit Expected Delivery (YYYY-MM-DD):", item.expected_delivery);
    if (!eta) return;
    const status = prompt("Edit Status (PLANNED, IN TRANSIT, DELAYED, DELIVERED, CANCELLED):", item.status);
    if (!status) return;

    const putRes = await fetch(`/api/shipments/${shipmentId}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({
        supplier_id: item.supplier_id, product_id: item.product_id, quantity: parseInt(qtyStr),
        origin: item.origin, destination_warehouse_id: item.destination_warehouse, expected_delivery: eta, status
      })
    });
    const putData = await putRes.json();
    if (putRes.ok) {
      alert(putData.message || "Shipment updated successfully.");
      loadShipments();
    } else {
      alert(putData.detail || "Error updating shipment.");
    }
  } catch (err) {
    alert("Network error updating shipment.");
  }
}

/* --- ORDERS CRUD --- */
async function loadOrders() {
  try {
    const res = await fetch("/api/orders", { headers: authHeaders() });
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
          <td>
            <button class="btn btn-secondary btn-sm" onclick="openEditOrderModal('${o.id}')">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="confirmDelete('order', '${o.id}')">Delete</button>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function openAddOrderModal() {
  const customerId = prompt("Customer ID (e.g. CUST-101):");
  if (!customerId) return;
  const productId = prompt("Product ID (e.g. PRD-SKU-101):");
  if (!productId) return;
  const qtyStr = prompt("Order Quantity:", "200");
  if (!qtyStr) return;
  const deliveryDate = prompt("Required Delivery Date (YYYY-MM-DD):", "2026-09-25");
  if (!deliveryDate) return;
  const priority = prompt("Priority (NORMAL, HIGH, CRITICAL):", "NORMAL");

  try {
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        customer_id: customerId, product_id: productId, quantity: parseInt(qtyStr),
        order_date: new Date().toISOString().substring(0, 10), required_delivery_date: deliveryDate,
        status: "PENDING", priority: priority || "NORMAL"
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || "Order created successfully.");
      loadOrders();
    } else {
      alert(data.detail || "Error creating order.");
    }
  } catch (err) {
    alert("Network error creating order.");
  }
}

async function openEditOrderModal(orderId) {
  try {
    const res = await fetch("/api/orders", { headers: authHeaders() });
    const data = await res.json();
    const item = (data.orders || []).find(o => o.id === orderId);
    if (!item) return alert("Order not found.");

    const qtyStr = prompt("Edit Quantity:", item.quantity);
    if (!qtyStr) return;
    const deliveryDate = prompt("Edit Required Delivery Date (YYYY-MM-DD):", item.required_delivery_date);
    if (!deliveryDate) return;
    const status = prompt("Edit Status (PENDING, CONFIRMED, PROCESSING, SHIPPED, DELIVERED, CANCELLED):", item.status);
    if (!status) return;
    const priority = prompt("Edit Priority (NORMAL, HIGH, CRITICAL):", item.priority);

    const putRes = await fetch(`/api/orders/${orderId}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({
        customer_id: item.customer_id, product_id: item.product_id, quantity: parseInt(qtyStr),
        order_date: item.order_date, required_delivery_date: deliveryDate, status, priority: priority || "NORMAL"
      })
    });
    const putData = await putRes.json();
    if (putRes.ok) {
      alert(putData.message || "Order updated successfully.");
      loadOrders();
    } else {
      alert(putData.detail || "Error updating order.");
    }
  } catch (err) {
    alert("Network error updating order.");
  }
}

/* --- CUSTOMERS CRUD --- */
async function loadCustomers() {
  try {
    const res = await fetch("/api/customers", { headers: authHeaders() });
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
          <td>
            <button class="btn btn-secondary btn-sm" onclick="openEditCustomerModal('${c.id}')">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="confirmDelete('customer', '${c.id}')">Delete</button>
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function openAddCustomerModal() {
  const name = prompt("Customer Name:");
  if (!name) return;
  const company = prompt("Company Name:");
  if (!company) return;
  const email = prompt("Email Address:");
  if (!email) return;
  const priority = prompt("Priority Tier (NORMAL, HIGH, CRITICAL):", "NORMAL");

  try {
    const res = await fetch("/api/customers", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ name, company, email, priority: priority || "NORMAL" })
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || "Customer added successfully.");
      loadCustomers();
    } else {
      alert(data.detail || "Error adding customer.");
    }
  } catch (err) {
    alert("Network error creating customer.");
  }
}

async function openEditCustomerModal(customerId) {
  try {
    const res = await fetch("/api/customers", { headers: authHeaders() });
    const data = await res.json();
    const customer = (data.customers || []).find(c => c.id === customerId);
    if (!customer) return alert("Customer not found.");

    const name = prompt("Edit Customer Name:", customer.name);
    if (!name) return;
    const company = prompt("Edit Company Name:", customer.company);
    if (!company) return;
    const email = prompt("Edit Email Address:", customer.email);
    if (!email) return;
    const priority = prompt("Edit Tier (NORMAL, HIGH, CRITICAL):", customer.priority);

    const putRes = await fetch(`/api/customers/${customerId}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ name, company, email, priority: priority || "NORMAL" })
    });
    const putData = await putRes.json();
    if (putRes.ok) {
      alert(putData.message || "Customer updated successfully.");
      loadCustomers();
    } else {
      alert(putData.detail || "Error updating customer.");
    }
  } catch (err) {
    alert("Network error updating customer.");
  }
}

/* --- OTHER MODULE LOADERS --- */
async function loadDisruptions() {
  try {
    const res = await fetch("/api/disruptions", { headers: authHeaders() });
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
    const res = await fetch("/api/ai-analysis", { headers: authHeaders() });
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
    const res = await fetch("/api/notifications", { headers: authHeaders() });
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
    const res = await fetch("/api/reports", { headers: authHeaders() });
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
    const res = await fetch("/api/escalations", { headers: authHeaders() });
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
          <td>
            ${e.status === 'RESOLVED' ? '<span class="badge badge-delivered">Resolved</span>' : `<button class="btn btn-secondary btn-sm" onclick="resolveEscalation('${e.id}')">Resolve</button>`}
          </td>
        </tr>
      `).join('');
    }
  } catch (err) {}
}

async function resolveEscalation(id) {
  try {
    const res = await fetch(`/api/escalations/${id}/resolve`, {
      method: "POST",
      headers: authHeaders()
    });
    if (res.ok) {
      alert(`Escalation ${id} resolved successfully.`);
      loadEscalations();
    }
  } catch (err) {
    alert("Error resolving escalation.");
  }
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
      headers: authHeaders(),
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

  const stage4 = data.stage4 || {};
  document.getElementById("narration-headline").textContent = stage4.headline || "Disruption Impact Calculated";
  document.getElementById("narration-body").textContent = stage4.reason || "Python calculated stock shortfall across pending customer orders.";

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
      headers: authHeaders(),
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
      headers: authHeaders(),
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
        const endpoint = `/api/${type}s/${id}`;
        const res = await fetch(endpoint, {
          method: "DELETE",
          headers: authHeaders()
        });
        const data = await res.json();

        if (res.ok && (data.status === "success" || data.message)) {
          closeModal("delete-modal-overlay");
          alert(data.message || `${type.toUpperCase()} deleted successfully.`);
          const targetView = `${type}s`;
          switchView(targetView);
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
