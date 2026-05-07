const state = {
  currentUser: null,
  currentView: "database",
  currentDatabaseView: "all",
  features: [],
  users: [],
  mentionableUsers: [],
  filters: {
    status: "",
    area: "",
    source: "",
    quickWin: false,
  },
  editingId: null,
};

const loginView = document.getElementById("login-view");
const appView = document.getElementById("app-view");
const databaseView = document.getElementById("database-view");
const usersView = document.getElementById("users-view");
const navTabs = document.querySelectorAll(".nav-tab");
const loginForm = document.getElementById("login-form");
const loginFeedback = document.getElementById("login-feedback");
const ssoPanel = document.getElementById("sso-panel");
const microsoftLoginButton = document.getElementById("microsoft-login-button");
const logoutButton = document.getElementById("logout-button");
const userName = document.getElementById("user-name");
const userRole = document.getElementById("user-role");
const featureModal = document.getElementById("feature-modal");
const modalBackdrop = document.getElementById("modal-backdrop");
const closeModalButton = document.getElementById("close-modal");
const newFeatureButton = document.getElementById("new-feature-button");
const newFeatureInline = document.getElementById("new-feature-inline");
const databaseViewTabs = document.querySelectorAll(".view-tab");
const featureForm = document.getElementById("feature-form");
const formTitle = document.getElementById("form-title");
const submitButton = document.getElementById("submit-button");
const cancelEditButton = document.getElementById("cancel-edit");
const featureTable = document.getElementById("feature-table");
const stats = document.getElementById("stats");
const feedback = document.getElementById("feedback");
const filterStatus = document.getElementById("filter-status");
const filterArea = document.getElementById("filter-area");
const filterSource = document.getElementById("filter-source");
const filterQuickWin = document.getElementById("filter-quick-win");
const taggedUsersOptions = document.getElementById("tagged-users-options");
const userAdminPanel = document.getElementById("user-admin-panel");
const userReadonlyPanel = document.getElementById("user-readonly-panel");
const userForm = document.getElementById("user-form");
const userTable = document.getElementById("user-table");
const userFeedback = document.getElementById("user-feedback");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function isAdmin() {
  return state.currentUser?.role === "admin";
}

function canEdit() {
  return ["admin", "editor"].includes(state.currentUser?.role);
}

function getFeatureSources(feature) {
  return Array.isArray(feature.request_sources) && feature.request_sources.length
    ? feature.request_sources
    : feature.request_source
      ? [feature.request_source]
      : [];
}

function showMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.remove("hidden", "error");
  if (isError) {
    element.classList.add("error");
  } else {
    element.classList.remove("error");
  }
}

function clearMessage(element) {
  element.textContent = "";
  element.classList.add("hidden");
  element.classList.remove("error");
}

function setAuthView(isAuthenticated) {
  loginView.classList.toggle("hidden", isAuthenticated);
  appView.classList.toggle("hidden", !isAuthenticated);
}

function setActiveView(view) {
  state.currentView = view;
  databaseView.classList.toggle("hidden", view !== "database");
  usersView.classList.toggle("hidden", view !== "users");
  navTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === view);
  });
}

function setEditingEnabled(enabled) {
  const disabled = !enabled;
  Array.from(featureForm.elements).forEach((field) => {
    if (field.tagName !== "BUTTON") {
      field.disabled = disabled;
    }
  });
  submitButton.disabled = disabled;
  newFeatureButton.disabled = disabled;
  newFeatureInline.disabled = disabled;

  if (!enabled) {
    submitButton.textContent = "View Only";
  } else if (state.editingId) {
    submitButton.textContent = "Save Changes";
  } else {
    submitButton.textContent = "Add Feature";
  }
}

function openFeatureModal() {
  if (!canEdit()) return;
  featureModal.classList.remove("hidden");
  featureModal.setAttribute("aria-hidden", "false");
}

function closeFeatureModal() {
  featureModal.classList.add("hidden");
  featureModal.setAttribute("aria-hidden", "true");
}

function resetFeatureForm() {
  featureForm.reset();
  featureForm.elements.id.value = "";
  featureForm.elements.status.value = "Idea";
  state.editingId = null;
  formTitle.textContent = "New Feature";
  cancelEditButton.classList.add("hidden");
  setEditingEnabled(canEdit());
}

function populateSourceChecks(sources) {
  const selected = new Set(sources);
  featureForm.querySelectorAll('input[name="sources"]').forEach((input) => {
    input.checked = selected.has(input.value);
  });
}

function selectedSources() {
  return Array.from(featureForm.querySelectorAll('input[name="sources"]:checked')).map(
    (input) => input.value
  );
}

function renderTaggedUserOptions() {
  if (!taggedUsersOptions) return;

  if (!state.mentionableUsers.length) {
    taggedUsersOptions.innerHTML = `
      <p class="field-empty-state">No teammates are available to tag yet.</p>
    `;
    return;
  }

  taggedUsersOptions.innerHTML = state.mentionableUsers
    .map(
      (user) => `
        <label class="source-chip user-chip">
          <input type="checkbox" name="taggedUsers" value="${user.id}" />
          <span>${escapeHtml(user.name)}</span>
          <span class="user-chip-meta">${escapeHtml(user.email)}</span>
        </label>
      `
    )
    .join("");
}

function populateTaggedUsers(taggedUserIds) {
  const selectedIds = new Set((taggedUserIds || []).map((id) => Number(id)));
  featureForm.querySelectorAll('input[name="taggedUsers"]').forEach((input) => {
    input.checked = selectedIds.has(Number(input.value));
  });
}

function selectedTaggedUsers() {
  return Array.from(featureForm.querySelectorAll('input[name="taggedUsers"]:checked')).map(
    (input) => Number(input.value)
  );
}

function getFilteredFeatures() {
  return state.features.filter((feature) => {
    if (state.currentDatabaseView === "quick-wins" && !feature.quick_win) return false;
    if (state.currentDatabaseView === "by-status" && feature.status !== "In progress") {
      return false;
    }
    if (state.filters.status && feature.status !== state.filters.status) return false;
    if (state.filters.area && feature.product_area !== state.filters.area) return false;
    if (state.filters.source && !getFeatureSources(feature).includes(state.filters.source)) {
      return false;
    }
    if (state.filters.quickWin && !feature.quick_win) return false;
    return true;
  });
}

function setActiveDatabaseView(view) {
  state.currentDatabaseView = view;
  databaseViewTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.dbView === view);
  });

  if (view === "quick-wins") {
    state.filters.quickWin = true;
    filterQuickWin.checked = true;
  } else if (view === "all") {
    state.filters.quickWin = false;
    state.filters.status = "";
    filterQuickWin.checked = false;
    filterStatus.value = "";
  } else if (view === "priority-dashboard") {
    state.filters.quickWin = false;
    filterQuickWin.checked = false;
  } else if (view === "by-status") {
    state.filters.quickWin = false;
    state.filters.status = "In progress";
    filterQuickWin.checked = false;
    filterStatus.value = "In progress";
  }

  renderFeatureTable();
}

function renderStats(features) {
  const total = features.length;
  const quickWins = features.filter((feature) => feature.quick_win).length;
  const avgScore = total
    ? Math.round(
        features.reduce((sum, feature) => sum + feature.priority_score, 0) / total
      )
    : 0;

  stats.innerHTML = `
    <div class="stat">
      <span>Total Features</span>
      <strong>${total}</strong>
    </div>
    <div class="stat">
      <span>Quick Wins</span>
      <strong>${quickWins}</strong>
    </div>
    <div class="stat">
      <span>Average Score</span>
      <strong>${avgScore}</strong>
    </div>
  `;
}

function renderFilters() {
  const statuses = [...new Set(state.features.map((feature) => feature.status))].sort();
  const areas = [...new Set(state.features.map((feature) => feature.product_area))].sort();
  const sources = [
    ...new Set(
      state.features.flatMap((feature) => getFeatureSources(feature))
    ),
  ].sort();

  filterStatus.innerHTML = `<option value="">All</option>${statuses
    .map(
      (status) =>
        `<option value="${escapeHtml(status)}" ${
          state.filters.status === status ? "selected" : ""
        }>${escapeHtml(status)}</option>`
    )
    .join("")}`;

  filterArea.innerHTML = `<option value="">All</option>${areas
    .map(
      (area) =>
        `<option value="${escapeHtml(area)}" ${
          state.filters.area === area ? "selected" : ""
        }>${escapeHtml(area)}</option>`
    )
    .join("")}`;

  filterSource.innerHTML = `<option value="">All</option>${sources
    .map(
      (source) =>
        `<option value="${escapeHtml(source)}" ${
          state.filters.source === source ? "selected" : ""
        }>${escapeHtml(source)}</option>`
    )
    .join("")}`;

  filterQuickWin.checked = state.filters.quickWin;
}

function renderFeatureTable() {
  const filtered = getFilteredFeatures();

  if (!filtered.length) {
    featureTable.innerHTML = `
      <tr>
        <td colspan="12">No features match the current filters.</td>
      </tr>
    `;
    renderStats(filtered);
    return;
  }

  featureTable.innerHTML = filtered
    .map((feature) => {
      const sources = getFeatureSources(feature);
      const taggedUsers = Array.isArray(feature.tagged_users) ? feature.tagged_users : [];
      return `
        <tr>
          <td><div class="feature-title">${escapeHtml(feature.title)}</div></td>
          <td><div class="feature-meta">${escapeHtml(feature.problem_statement)}</div></td>
          <td><span class="pill status-pill">${escapeHtml(feature.status)}</span></td>
          <td>
            <div class="pill-row">
              ${sources.map((source) => `<span class="pill">${escapeHtml(source)}</span>`).join("")}
            </div>
          </td>
          <td>${escapeHtml(feature.product_area)}</td>
          <td>
            ${
              taggedUsers.length
                ? `<div class="pill-row">
                    ${taggedUsers
                      .map(
                        (user) =>
                          `<span class="pill subtle-pill">${escapeHtml(user.name)}</span>`
                      )
                      .join("")}
                  </div>`
                : `<span class="feature-meta">No tags</span>`
            }
          </td>
          <td>${feature.effort}/5</td>
          <td>${feature.urgency}/5</td>
          <td>${feature.quick_win ? "Yes" : "No"}</td>
          <td><span class="pill score-pill">${feature.priority_score}</span></td>
          <td>${formatDate(feature.updated_at)}</td>
          <td>
            ${
              canEdit()
                ? `<div class="button-row">
                    <button class="ghost" type="button" data-action="edit" data-id="${feature.id}">Edit</button>
                    <button class="ghost" type="button" data-action="delete" data-id="${feature.id}">Delete</button>
                  </div>`
                : `<span class="feature-meta">View only</span>`
            }
          </td>
        </tr>
      `;
    })
    .join("");

  renderStats(filtered);
}

function renderUsers() {
  if (!isAdmin()) return;
  userTable.innerHTML = state.users
    .map(
      (user) => `
        <tr>
          <td>${escapeHtml(user.name)}</td>
          <td>${escapeHtml(user.email)}</td>
          <td><span class="pill subtle-pill">${escapeHtml(user.role)}</span></td>
          <td>${formatDate(user.created_at)}</td>
          <td>
            ${
              state.currentUser?.id === user.id
                ? `<span class="feature-meta">Current user</span>`
                : `<button class="ghost" type="button" data-user-action="delete" data-id="${user.id}">Delete</button>`
            }
          </td>
        </tr>
      `
    )
    .join("");
}

function populateFeatureForm(feature) {
  if (!canEdit()) return;
  featureForm.elements.id.value = feature.id;
  featureForm.elements.title.value = feature.title;
  featureForm.elements.productArea.value = feature.product_area;
  featureForm.elements.status.value = feature.status;
  featureForm.elements.teamOwner.value = feature.team_owner || "";
  featureForm.elements.submittedBy.value = feature.submitted_by || "";
  featureForm.elements.problem.value = feature.problem_statement;
  featureForm.elements.customerImpact.value = feature.customer_impact;
  featureForm.elements.strategicFit.value = feature.strategic_fit;
  featureForm.elements.urgency.value = feature.urgency;
  featureForm.elements.confidence.value = feature.confidence;
  featureForm.elements.effort.value = feature.effort;
  featureForm.elements.dependencyRisk.value = feature.dependency_risk;
  featureForm.elements.dependencies.value = feature.dependencies || "";
  featureForm.elements.urgencyReason.value = feature.urgency_reason || "";
  featureForm.elements.quickWin.checked = Boolean(feature.quick_win);
  featureForm.elements.notes.value = feature.notes || "";
  populateSourceChecks(getFeatureSources(feature));
  populateTaggedUsers(feature.tagged_user_ids || []);

  state.editingId = feature.id;
  formTitle.textContent = "Edit Feature";
  cancelEditButton.classList.remove("hidden");
  setEditingEnabled(true);
  openFeatureModal();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "Request failed.");
  }
  return payload;
}

async function loadFeatures() {
  state.features = await api("/api/features");
  renderFilters();
  setActiveDatabaseView(state.currentDatabaseView);
  renderFeatureTable();
}

async function loadUsers() {
  if (!isAdmin()) return;
  state.users = await api("/api/users");
  renderUsers();
}

async function loadMentionableUsers() {
  state.mentionableUsers = await api("/api/mentionable-users", { headers: {} });
  renderTaggedUserOptions();
}

async function loadCurrentUser() {
  try {
    state.currentUser = await api("/api/me", { headers: {} });
  } catch {
    state.currentUser = null;
    setAuthView(false);
    return;
  }

  userName.textContent = state.currentUser.name;
  userRole.textContent = state.currentUser.role;
  userAdminPanel.classList.toggle("hidden", !isAdmin());
  userReadonlyPanel.classList.toggle("hidden", isAdmin());
  setEditingEnabled(canEdit());
  setAuthView(true);
  setActiveView("database");

  try {
    await loadMentionableUsers();
  } catch (error) {
    showMessage(
      feedback,
      error.message || "Logged in, but teammate tagging could not be loaded.",
      true
    );
  }

  try {
    await loadFeatures();
  } catch (error) {
    showMessage(
      feedback,
      error.message || "Logged in, but feature data could not be loaded.",
      true
    );
  }

  try {
    await loadUsers();
  } catch (error) {
    if (isAdmin()) {
      showMessage(
        userFeedback,
        error.message || "Logged in, but team access data could not be loaded.",
        true
      );
    }
  }
}

function readAuthError() {
  const url = new URL(window.location.href);
  const authError = url.searchParams.get("authError");
  if (!authError) return;

  const messages = {
    invalid_state: "Microsoft sign-in could not be verified. Please try again.",
    access_denied: "Microsoft sign-in was cancelled.",
    no_email: "Your Microsoft account did not provide an email address.",
    domain_not_allowed: "Your Microsoft account domain is not allowed.",
    not_provisioned: "Your Microsoft account is not provisioned for access.",
  };

  showMessage(loginFeedback, messages[authError] || "Microsoft sign-in failed.", true);
  url.searchParams.delete("authError");
  window.history.replaceState({}, "", url.toString());
}

async function loadAuthConfig() {
  try {
    const config = await api("/api/auth/config", { headers: {} });
    ssoPanel.classList.toggle("hidden", !config.microsoftEnabled);
    microsoftLoginButton.classList.toggle("hidden", !config.microsoftEnabled);
  } catch {
    ssoPanel.classList.add("hidden");
    microsoftLoginButton.classList.add("hidden");
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(loginFeedback);
  const data = new FormData(loginForm);

  try {
    await api("/api/login", {
      method: "POST",
      body: JSON.stringify({
        email: data.get("email"),
        password: data.get("password"),
      }),
    });
    loginForm.reset();
    await loadCurrentUser();
  } catch (error) {
    showMessage(loginFeedback, error.message, true);
  }
});

logoutButton.addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", headers: {} });
  state.currentUser = null;
  state.features = [];
  state.users = [];
  resetFeatureForm();
  closeFeatureModal();
  setAuthView(false);
});

microsoftLoginButton.addEventListener("click", () => {
  const callbackURL = window.location.pathname || "/";
  window.location.href = `/api/auth/microsoft/start?callbackURL=${encodeURIComponent(callbackURL)}`;
});

navTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    setActiveView(tab.dataset.view);
  });
});

[newFeatureButton, newFeatureInline].forEach((button) => {
  button.addEventListener("click", () => {
    if (!canEdit()) return;
    resetFeatureForm();
    clearMessage(feedback);
    openFeatureModal();
  });
});

closeModalButton.addEventListener("click", closeFeatureModal);
modalBackdrop.addEventListener("click", closeFeatureModal);

featureForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(feedback);
  if (!canEdit()) return;

  const data = new FormData(featureForm);
  const payload = {
    title: data.get("title"),
    product_area: data.get("productArea"),
    request_sources: selectedSources(),
    status: data.get("status"),
    team_owner: data.get("teamOwner"),
    submitted_by: data.get("submittedBy"),
    problem_statement: data.get("problem"),
    customer_impact: Number(data.get("customerImpact")),
    strategic_fit: Number(data.get("strategicFit")),
    urgency: Number(data.get("urgency")),
    confidence: Number(data.get("confidence")),
    effort: Number(data.get("effort")),
    dependency_risk: Number(data.get("dependencyRisk")),
    dependencies: data.get("dependencies"),
    urgency_reason: data.get("urgencyReason"),
    tagged_user_ids: selectedTaggedUsers(),
    quick_win: data.get("quickWin") === "on",
    notes: data.get("notes"),
  };

  try {
    const isEditing = Boolean(state.editingId);
    const path = isEditing ? `/api/features/${state.editingId}` : "/api/features";
    const method = isEditing ? "PUT" : "POST";
    await api(path, { method, body: JSON.stringify(payload) });
    await loadFeatures();
    resetFeatureForm();
    closeFeatureModal();
    showMessage(feedback, isEditing ? "Feature updated." : "Feature added.");
  } catch (error) {
    showMessage(feedback, error.message, true);
  }
});

cancelEditButton.addEventListener("click", () => {
  resetFeatureForm();
  closeFeatureModal();
});

featureTable.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button || !canEdit()) return;

  const id = Number(button.dataset.id);
  const feature = state.features.find((item) => item.id === id);
  if (!feature) return;

  if (button.dataset.action === "edit") {
    populateFeatureForm(feature);
    clearMessage(feedback);
    return;
  }

  if (button.dataset.action === "delete") {
    const confirmed = window.confirm(`Delete "${feature.title}"?`);
    if (!confirmed) return;

    try {
      await api(`/api/features/${id}`, { method: "DELETE", headers: {} });
      await loadFeatures();
      showMessage(feedback, "Feature deleted.");
    } catch (error) {
      showMessage(feedback, error.message, true);
    }
  }
});

filterStatus.addEventListener("change", (event) => {
  state.currentDatabaseView = "all";
  databaseViewTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.dbView === "all");
  });
  state.filters.status = event.target.value;
  renderFeatureTable();
});

filterArea.addEventListener("change", (event) => {
  state.currentDatabaseView = "all";
  databaseViewTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.dbView === "all");
  });
  state.filters.area = event.target.value;
  renderFeatureTable();
});

filterSource.addEventListener("change", (event) => {
  state.currentDatabaseView = "all";
  databaseViewTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.dbView === "all");
  });
  state.filters.source = event.target.value;
  renderFeatureTable();
});

filterQuickWin.addEventListener("change", (event) => {
  state.currentDatabaseView = "all";
  databaseViewTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.dbView === "all");
  });
  state.filters.quickWin = event.target.checked;
  renderFeatureTable();
});

databaseViewTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    setActiveDatabaseView(tab.dataset.dbView);
  });
});

userForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(userFeedback);
  if (!isAdmin()) return;

  const data = new FormData(userForm);
  try {
    await api("/api/users", {
      method: "POST",
      body: JSON.stringify({
        name: data.get("name"),
        email: data.get("email"),
        role: data.get("role"),
        password: data.get("password"),
      }),
    });
    userForm.reset();
    await loadUsers();
    showMessage(userFeedback, "User created.");
  } catch (error) {
    showMessage(userFeedback, error.message, true);
  }
});

userTable.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-user-action]");
  if (!button || !isAdmin()) return;

  const id = Number(button.dataset.id);
  const user = state.users.find((item) => item.id === id);
  if (!user) return;

  const confirmed = window.confirm(`Delete user "${user.email}"?`);
  if (!confirmed) return;

  try {
    await api(`/api/users/${id}`, { method: "DELETE", headers: {} });
    await loadUsers();
    showMessage(userFeedback, "User deleted.");
  } catch (error) {
    showMessage(userFeedback, error.message, true);
  }
});

readAuthError();
loadAuthConfig();
loadCurrentUser();
