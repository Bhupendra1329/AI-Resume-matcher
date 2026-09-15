const API_BASE = ""; // same origin as this page (FastAPI serves both)

let currentUser = null; // { user_id, name, token }

// ---------- helpers ----------
async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (currentUser && currentUser.token) {
    headers["Authorization"] = `Bearer ${currentUser.token}`;
  }
  const res = await fetch(API_BASE + path, { ...options, headers });
  let data;
  try {
    data = await res.json();
  } catch {
    data = {};
  }
  if (!res.ok && !data.message) {
    data.message = data.detail || "Something went wrong.";
  }
  data.__status = res.status;
  return data;
}

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

// ---------- auth tabs ----------
const tabBtns = document.querySelectorAll(".tab-btn");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");

tabBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    tabBtns.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    if (btn.dataset.tab === "login") { show(loginForm); hide(registerForm); }
    else { show(registerForm); hide(loginForm); }
  });
});

// ---------- register ----------
registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("reg-name").value;
  const email = document.getElementById("reg-email").value;
  const password = document.getElementById("reg-password").value;
  const msg = document.getElementById("register-msg");

  const data = await api("/register", {
    method: "POST",
    body: JSON.stringify({ name, email, password }),
  });

  if (data.message === "User Registered Successfully") {
    msg.style.color = "#10b981";
    msg.textContent = "Account created! Please log in.";
    registerForm.reset();
    setTimeout(() => document.querySelector('[data-tab="login"]').click(), 800);
  } else {
    msg.style.color = "#ef4444";
    msg.textContent = data.message || "Something went wrong.";
  }
});

// ---------- login ----------
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;
  const msg = document.getElementById("login-msg");

  const data = await api("/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  if (data.message === "Login Successful") {
    currentUser = { user_id: data.user_id, name: data.name, token: data.access_token };
    localStorage.setItem("resume_matcher_user", JSON.stringify(currentUser));
    enterApp();
  } else {
    msg.textContent = data.message || "Login failed.";
  }
});

// ---------- logout ----------
document.getElementById("logout-btn").addEventListener("click", () => {
  currentUser = null;
  localStorage.removeItem("resume_matcher_user");
  hide(document.getElementById("app-screen"));
  show(document.getElementById("auth-screen"));
});

// ---------- enter app ----------
async function enterApp() {
  hide(document.getElementById("auth-screen"));
  show(document.getElementById("app-screen"));
  document.getElementById("user-name-label").textContent = `${currentUser.name}`;
  await loadDashboard();
  await loadApplications();
  await loadMatchHistory();
}

// ---------- nav switching ----------
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach(v => hide(v));
    show(document.getElementById(btn.dataset.view));
  });
});

// ---------- dashboard ----------
async function loadDashboard() {
  const data = await api("/dashboard");
  document.getElementById("stat-total").textContent = data.total_applications ?? 0;
  document.getElementById("stat-applied").textContent = data.applied ?? 0;
  document.getElementById("stat-interview").textContent = data.interview ?? 0;
  document.getElementById("stat-offer").textContent = data.offer ?? 0;
  document.getElementById("stat-rejected").textContent = data.rejected ?? 0;
}

// ---------- applications list ----------
async function loadApplications() {
  const search = document.getElementById("search-input").value.trim();
  const status = document.getElementById("filter-status").value;

  let path = "/applications";
  if (search) path = `/applications/search?company=${encodeURIComponent(search)}`;
  else if (status) path = `/applications?status=${encodeURIComponent(status)}`;

  const apps = await api(path);
  const list = Array.isArray(apps) ? apps : [];
  renderApplications(list);
  populateAppLinkDropdown(list);
}

function renderApplications(apps) {
  const list = document.getElementById("app-list");
  list.innerHTML = "";

  if (!apps.length) {
    list.innerHTML = `<div class="empty-state">No applications yet. Click "+ Add Application" to get started.</div>`;
    return;
  }

  apps.forEach(app => {
    const card = document.createElement("div");
    card.className = "app-card";
    card.innerHTML = `
      <div class="app-info">
        <h4>${escapeHtml(app.role)} · ${escapeHtml(app.company)}</h4>
        <p>${escapeHtml(app.notes || "No notes")}</p>
      </div>
      <div class="app-actions">
        <span class="status-badge ${app.status}">${app.status}</span>
        <select data-id="${app.id}" class="status-select">
          <option value="Applied" ${app.status === "Applied" ? "selected" : ""}>Applied</option>
          <option value="Interview" ${app.status === "Interview" ? "selected" : ""}>Interview</option>
          <option value="Offer" ${app.status === "Offer" ? "selected" : ""}>Offer</option>
          <option value="Rejected" ${app.status === "Rejected" ? "selected" : ""}>Rejected</option>
        </select>
        <button class="icon-btn delete-btn" data-id="${app.id}" title="Delete">🗑️</button>
      </div>
    `;
    list.appendChild(card);
  });

  document.querySelectorAll(".status-select").forEach(sel => {
    sel.addEventListener("change", async (e) => {
      const id = e.target.dataset.id;
      await api(`/applications/${id}?status=${encodeURIComponent(e.target.value)}`, { method: "PUT" });
      await loadDashboard();
      await loadApplications();
    });
  });

  document.querySelectorAll(".delete-btn").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const id = e.target.dataset.id;
      if (!confirm("Delete this application?")) return;
      await api(`/applications/${id}`, { method: "DELETE" });
      await loadDashboard();
      await loadApplications();
    });
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

document.getElementById("search-input").addEventListener("input", debounce(loadApplications, 300));
document.getElementById("filter-status").addEventListener("change", loadApplications);

function debounce(fn, delay) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}

// ---------- add application modal ----------
const addModal = document.getElementById("add-modal");
document.getElementById("add-app-btn").addEventListener("click", () => show(addModal));
document.getElementById("cancel-add").addEventListener("click", () => hide(addModal));

document.getElementById("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const company = document.getElementById("add-company").value;
  const role = document.getElementById("add-role").value;
  const status = document.getElementById("add-status").value;
  const notes = document.getElementById("add-notes").value;

  await api("/applications", {
    method: "POST",
    body: JSON.stringify({ company, role, status, notes }),
  });

  e.target.reset();
  hide(addModal);
  await loadDashboard();
  await loadApplications();
});

// ============================================================
// RESUME MATCHER
// ============================================================

function populateAppLinkDropdown(apps) {
  const sel = document.getElementById("match-app-link");
  const current = sel.value;
  sel.innerHTML = `<option value="">— Not linked to a specific application —</option>`;
  apps.forEach(app => {
    const opt = document.createElement("option");
    opt.value = app.id;
    opt.textContent = `${app.role} · ${app.company}`;
    sel.appendChild(opt);
  });
  sel.value = current;
}

document.getElementById("match-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("match-msg");
  msg.style.color = "#6b7280";
  msg.textContent = "Analyzing...";

  const fileInput = document.getElementById("match-resume");
  const jd = document.getElementById("match-jd").value;
  const appLink = document.getElementById("match-app-link").value;

  if (!fileInput.files.length) {
    msg.style.color = "#ef4444";
    msg.textContent = "Please choose a resume file.";
    return;
  }

  const formData = new FormData();
  formData.append("resume", fileInput.files[0]);
  formData.append("job_description", jd);
  if (appLink) formData.append("application_id", appLink);

  const data = await api("/match/analyze", { method: "POST", body: formData });

  if (data.__status && data.__status >= 400) {
    msg.style.color = "#ef4444";
    msg.textContent = data.message || "Analysis failed.";
    return;
  }

  msg.textContent = "";
  renderMatchResult(data);
  await loadMatchHistory();
});

function renderMatchResult(data) {
  const resultSection = document.getElementById("match-result");
  show(resultSection);

  const ring = document.getElementById("score-ring");
  ring.style.setProperty("--pct", data.match_score);
  document.getElementById("score-value").textContent = `${data.match_score}%`;

  const matchedWrap = document.getElementById("matched-skills");
  const missingWrap = document.getElementById("missing-skills");
  matchedWrap.innerHTML = "";
  missingWrap.innerHTML = "";

  if (data.matched_skills.length) {
    data.matched_skills.forEach(s => {
      const chip = document.createElement("span");
      chip.className = "chip matched-chip";
      chip.textContent = s;
      matchedWrap.appendChild(chip);
    });
  } else {
    matchedWrap.innerHTML = `<span style="color:#9ca3af;font-size:13px;">No overlapping skills found</span>`;
  }

  if (data.missing_skills.length) {
    data.missing_skills.forEach(s => {
      const chip = document.createElement("span");
      chip.className = "chip missing-chip";
      chip.textContent = s;
      missingWrap.appendChild(chip);
    });
  } else {
    missingWrap.innerHTML = `<span style="color:#9ca3af;font-size:13px;">No missing skills detected 🎉</span>`;
  }

  const suggestionEl = document.getElementById("suggestion-text");
  if (data.missing_skills.length) {
    suggestionEl.textContent =
      `To improve your match for this role, consider highlighting or gaining experience in: ${data.missing_skills.join(", ")}.`;
  } else {
    suggestionEl.textContent = "Your resume already covers every skill this matcher detected in the job description. Nice work!";
  }
}

async function loadMatchHistory() {
  const rows = await api("/match/history");
  const list = document.getElementById("match-history-list");
  list.innerHTML = "";

  if (!Array.isArray(rows) || !rows.length) {
    list.innerHTML = `<div class="empty-state">No resume analyses yet. Run your first match above.</div>`;
    return;
  }

  rows.forEach(r => {
    const item = document.createElement("div");
    item.className = "history-item";
    const date = new Date(r.created_at).toLocaleDateString();
    item.innerHTML = `
      <span>${escapeHtml(r.resume_filename)} · ${date}</span>
      <span class="h-score">${r.match_score}%</span>
    `;
    list.appendChild(item);
  });
}

// ---------- restore session ----------
const saved = localStorage.getItem("resume_matcher_user");
if (saved) {
  currentUser = JSON.parse(saved);
  enterApp();
}
