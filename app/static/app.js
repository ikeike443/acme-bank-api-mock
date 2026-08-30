const state = {
  token: null,
  accountId: null,
  account: null,
};

const $ = (selector) => document.querySelector(selector);
const yen = new Intl.NumberFormat("ja-JP", {
  style: "currency",
  currency: "JPY",
  maximumFractionDigits: 0,
});

function setMessage(selector, message, type = "error") {
  const element = $(selector);
  element.textContent = message;
  element.className = `message ${type}`;
  element.hidden = false;
}

function clearMessage(selector) {
  const element = $(selector);
  element.hidden = true;
  element.textContent = "";
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  if (options.body) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "処理に失敗しました。");
  }
  return body;
}

function renderAccount(account) {
  state.account = account;
  $("#account-name").textContent = account.owner_name;
  $("#account-balance").textContent = yen.format(account.balance);
  $("#account-status").textContent = account.is_frozen ? "凍結中" : "利用可能";
  $("#account-status").classList.toggle("status-warning", account.is_frozen);
  $("#daily-limit").textContent = yen.format(account.daily_limit);
}

async function loadAccount() {
  const account = await api(`/accounts/${state.accountId}`);
  renderAccount(account);
}

function showDashboard() {
  $("#login-panel").hidden = true;
  $("#dashboard").hidden = false;
}

function showLogin() {
  $("#login-panel").hidden = false;
  $("#dashboard").hidden = true;
}

function updateStepUpVisibility() {
  const amount = Number($("#amount").value || 0);
  $("#step-up-area").hidden = amount < 500000;
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage("#login-error");
  const button = event.currentTarget.querySelector("button");
  button.disabled = true;
  try {
    const body = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        account_id: Number($("#account-id").value),
        pin: $("#pin").value,
      }),
    });
    state.token = body.token;
    state.accountId = body.account_id;
    await loadAccount();
    showDashboard();
  } catch (error) {
    setMessage("#login-error", error.message);
  } finally {
    button.disabled = false;
  }
});

$("#amount").addEventListener("input", updateStepUpVisibility);

$("#request-code-button").addEventListener("click", async () => {
  const button = $("#request-code-button");
  button.disabled = true;
  try {
    const body = await api("/auth/step-up", {
      method: "POST",
      body: JSON.stringify({ account_id: state.accountId }),
    });
    $("#step-up-code").value = body.code;
    $("#step-up-hint").textContent = `コードを発行しました（${body.expires_in_minutes}分有効）`;
  } catch (error) {
    setMessage("#transfer-message", error.message);
  } finally {
    button.disabled = false;
  }
});

$("#transfer-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage("#transfer-message");
  const button = $("#transfer-button");
  button.disabled = true;
  try {
    const transfer = await api("/transfers", {
      method: "POST",
      body: JSON.stringify({
        source_account_id: state.accountId,
        destination_account_id: Number($("#destination-id").value),
        amount: Number($("#amount").value),
        step_up_code: $("#step-up-code").value || null,
      }),
    });
    await loadAccount();
    setMessage("#transfer-message", `${yen.format(transfer.amount)}の送金が完了しました。`, "success");
    $("#transfer-form").reset();
    $("#destination-id").value = "2";
    $("#step-up-area").hidden = true;
  } catch (error) {
    setMessage("#transfer-message", error.message);
  } finally {
    button.disabled = false;
  }
});

$("#logout-button").addEventListener("click", () => {
  state.token = null;
  state.accountId = null;
  state.account = null;
  $("#login-form").reset();
  $("#account-id").value = "1";
  $("#pin").value = "1234";
  clearMessage("#login-error");
  showLogin();
});
