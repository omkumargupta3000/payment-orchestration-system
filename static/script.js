// Simple vanilla JS dashboard - no build step, no framework needed.

const API_BASE = "/api";

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = Array.isArray(data.detail)
      ? data.detail.join(", ")
      : data.detail || "Request failed";
    throw new Error(message);
  }
  return data;
}

function formatCurrency(amount) {
  return "₹" + Number(amount).toFixed(2);
}

function formatDate(isoString) {
  const d = new Date(isoString);
  return d.toLocaleString();
}

function randomIdempotencyKey() {
  return "PAY-" + Math.random().toString(36).slice(2, 10).toUpperCase();
}

// ---- summary cards -----------------------------------------------------

async function loadSummary() {
  const summary = await fetchJSON(`${API_BASE}/analytics/summary`);
  document.getElementById("stat-total").textContent = summary.total_transactions;
  document.getElementById("stat-success").textContent = summary.successful_transactions;
  document.getElementById("stat-failed").textContent = summary.failed_transactions;
  document.getElementById("stat-rate").textContent = summary.success_rate + "%";
  document.getElementById("stat-amount").textContent = formatCurrency(summary.total_amount);
  document.getElementById("stat-latency").textContent =
    Math.round(summary.average_latency_ms) + " ms";
}

// ---- PSP performance -----------------------------------------------------

async function loadPSPPerformance() {
  const psps = await fetchJSON(`${API_BASE}/analytics/psps`);
  const container = document.getElementById("psp-performance");
  container.innerHTML = "";

  psps.forEach((psp) => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <span class="card-label">${psp.name} ${psp.is_active ? "" : "(inactive)"}</span>
      <span class="card-value">${
        psp.observed_success_rate !== null ? psp.observed_success_rate + "%" : "-"
      }</span>
      <span class="hint">${psp.total_transactions_handled} txns · ${psp.failures} failed · configured ${(
      psp.configured_success_rate * 100
    ).toFixed(0)}% / ${psp.configured_avg_latency_ms}ms</span>
    `;
    container.appendChild(card);
  });
}

// ---- PSP config panel -----------------------------------------------------

async function loadPSPConfig() {
  const psps = await fetchJSON(`${API_BASE}/psps`);
  const container = document.getElementById("psp-config-list");
  container.innerHTML = "";

  psps.forEach((psp) => {
    const row = document.createElement("div");
    row.className = "psp-config-row";
    row.innerHTML = `
      <span class="psp-name">${psp.name}</span>
      <label>
        Success rate
        <input type="number" min="0" max="1" step="0.01" value="${psp.success_rate}" data-field="success_rate" />
      </label>
      <label>
        Latency (ms)
        <input type="number" min="1" step="10" value="${psp.avg_latency_ms}" data-field="avg_latency_ms" />
      </label>
      <label>
        <input type="checkbox" ${psp.is_active ? "checked" : ""} data-field="is_active" />
        Active
      </label>
      <button class="small-btn" data-action="save">Save</button>
    `;

    row.querySelector('[data-action="save"]').addEventListener("click", async () => {
      const successRateInput = row.querySelector('[data-field="success_rate"]');
      const latencyInput = row.querySelector('[data-field="avg_latency_ms"]');
      const activeInput = row.querySelector('[data-field="is_active"]');

      try {
        await fetchJSON(`${API_BASE}/psps/${encodeURIComponent(psp.name)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            success_rate: parseFloat(successRateInput.value),
            avg_latency_ms: parseInt(latencyInput.value, 10),
            is_active: activeInput.checked,
          }),
        });
        await loadPSPPerformance();
      } catch (err) {
        alert("Failed to update PSP: " + err.message);
      }
    });

    container.appendChild(row);
  });
}

// ---- transaction table -----------------------------------------------------

async function loadTransactions() {
  const status = document.getElementById("filter-status").value;
  const url = new URL(`${API_BASE}/payments`, window.location.origin);
  if (status) url.searchParams.set("status", status);

  const transactions = await fetchJSON(url);
  const tbody = document.getElementById("transactions-body");
  tbody.innerHTML = "";

  transactions.forEach((txn) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${txn.transaction_id}</td>
      <td>${txn.order_id}</td>
      <td>${formatCurrency(txn.amount)}</td>
      <td>${txn.selected_psp || "-"}</td>
      <td><span class="status-badge status-${txn.status}">${txn.status}</span></td>
      <td>${txn.retry_count}</td>
      <td>${formatDate(txn.created_at)}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ---- payment form -----------------------------------------------------

document.getElementById("generate-key-btn").addEventListener("click", () => {
  document.getElementById("idempotency_key").value = randomIdempotencyKey();
});

document.getElementById("payment-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const submitBtn = document.getElementById("submit-btn");
  const resultBox = document.getElementById("payment-result");
  submitBtn.disabled = true;
  submitBtn.textContent = "Processing...";

  const payload = {
    customer_id: document.getElementById("customer_id").value,
    order_id: document.getElementById("order_id").value,
    amount: parseFloat(document.getElementById("amount").value),
    currency: document.getElementById("currency").value,
    payment_method: document.getElementById("payment_method").value,
    idempotency_key: document.getElementById("idempotency_key").value,
  };

  try {
    const txn = await fetchJSON(`${API_BASE}/payments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    resultBox.classList.remove("hidden");
    resultBox.innerHTML = `
      <div class="row"><span>Transaction ID</span><strong>${txn.transaction_id}</strong></div>
      <div class="row"><span>Status</span><strong>${txn.status}</strong></div>
      <div class="row"><span>Selected PSP</span><strong>${txn.selected_psp || "-"}</strong></div>
      <div class="row"><span>Retry Count</span><strong>${txn.retry_count}</strong></div>
      <div class="row"><span>Processing Time</span><strong>${txn.processing_time_ms} ms</strong></div>
    `;

    await Promise.all([loadSummary(), loadPSPPerformance(), loadTransactions()]);
  } catch (err) {
    resultBox.classList.remove("hidden");
    resultBox.innerHTML = `<div class="row"><span>Error</span><strong>${err.message}</strong></div>`;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Process Payment";
    document.getElementById("idempotency_key").value = randomIdempotencyKey();
  }
});

document.getElementById("refresh-btn").addEventListener("click", loadTransactions);
document.getElementById("filter-status").addEventListener("change", loadTransactions);

// ---- initial load -----------------------------------------------------

document.getElementById("order_id").value = "ORD" + Math.floor(1000 + Math.random() * 9000);
document.getElementById("idempotency_key").value = randomIdempotencyKey();

loadSummary();
loadPSPPerformance();
loadPSPConfig();
loadTransactions();
