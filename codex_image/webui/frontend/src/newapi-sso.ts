import { getLegacyBridge } from "./state";
import { clearByokCreds, clearSession, getByokCreds, saveByokFromNewapi, syncSession } from "./byok";

const NEWAPI_ACTIVE_KEY = "ilab_newapi_active";
const NEWAPI_USERNAME_KEY = "ilab_newapi_username";

let newapiEnabled = false;
let newapiActive = false;
let newapiUsername = "";

export function isNewapiEnabled(): boolean {
  return newapiEnabled;
}

export function isNewapiActive(): boolean {
  return newapiActive;
}

export function getNewapiUsername(): string {
  return newapiUsername;
}

function persistActive(active: boolean, username: string): void {
  newapiActive = active;
  newapiUsername = username;
  if (active) {
    localStorage.setItem(NEWAPI_ACTIVE_KEY, "1");
    localStorage.setItem(NEWAPI_USERNAME_KEY, username);
  } else {
    localStorage.removeItem(NEWAPI_ACTIVE_KEY);
    localStorage.removeItem(NEWAPI_USERNAME_KEY);
  }
}

function refreshRunButton(): void {
  const bridge = getLegacyBridge();
  const els = bridge.els;
  if (!els?.runButton) return;
  const byokActive = Boolean(bridge.methods.isByokActive?.());
  const available = Boolean(bridge.state.authAvailable) || byokActive || newapiActive;
  els.runButton.disabled = !available;
}

function updateIndicator(): void {
  const button = document.getElementById("newapiToggleButton");
  if (!button) return;
  button.classList.toggle("active", newapiActive);
  if (newapiActive) {
    button.textContent = newapiUsername ? `🪄 ${newapiUsername}` : "🪄 new-api 已登录";
    button.title = "已通过 new-api 登录（点击退出）";
  } else {
    button.textContent = "🪄 new-api 登录";
    button.title = "使用已登录的 new-api 账号一键出图";
  }
}

function renderStatusIndicator(): void {
  if (!newapiActive) return; // when inactive, leave auth-source in charge of the detail/dot
  const els = getLegacyBridge().els;
  const text = newapiUsername ? `🪄 new-api · ${newapiUsername}` : "🪄 new-api · 已登录";
  if (els?.authSourceDetail) {
    els.authSourceDetail.textContent = text;
    els.authSourceDetail.title = text;
  }
  if (els?.apiStatus) {
    els.apiStatus.className = "status-dot ok";
  }
}

export async function refreshNewapiStatus(): Promise<void> {
  if (!newapiEnabled) {
    newapiActive = false;
    updateIndicator();
    refreshRunButton();
    return;
  }
  try {
    const resp = await fetch("/api/newapi/status", { credentials: "include" });
    if (!resp.ok) {
      persistActive(false, "");
      updateIndicator();
      refreshRunButton();
      return;
    }
    const data = await resp.json();
    if (data?.ok && data.username) {
      const creds = getByokCreds();
      const stored = localStorage.getItem(NEWAPI_USERNAME_KEY);
      if (!creds || (creds.authSource === "newapi" && (!creds.apiKey || stored !== data.username))) {
        persistActive(false, data.username);
        await triggerLogin(true);
      } else {
        persistActive(true, data.username);
      }
    } else {
      persistActive(false, "");
    }
  } catch {
    persistActive(false, "");
  }
  updateIndicator();
  renderStatusIndicator();
  refreshRunButton();
}

async function triggerLogin(silent = false): Promise<void> {
  try {
    const resp = await fetch("/api/newapi/login", { method: "POST", credentials: "include" });
    if (resp.ok) {
      const data = await resp.json();
      const username = String(data.username || "");
      if (data.byok) {
        saveByokFromNewapi(data.byok.api_key, data.byok.base_url, data.byok.image_model);
        void syncSession();
      }
      persistActive(true, username);
      updateIndicator();
      renderStatusIndicator();
      refreshRunButton();
      getLegacyBridge().methods.updateRequestPreview?.();
      getLegacyBridge().methods.setStatus?.(username ? `已通过 new-api 登录：${username}` : "已通过 new-api 登录", "ok");
      return;
    }
  } catch {
    // fall through
  }
  if (silent) {
    persistActive(false, "");
    return;
  }
  const base = document.documentElement.getAttribute("data-newapi-base-url");
  if (base) {
    const returnUrl = window.location.origin + window.location.pathname;
    window.open(`${base}/sign-in?redirect=${encodeURIComponent(returnUrl)}`, "_blank", "noopener");
  }
}

async function triggerLogout(): Promise<void> {
  try {
    await fetch("/api/newapi/logout", { method: "DELETE", credentials: "include" });
  } catch {
    // ignore
  }
  const creds = getByokCreds();
  if (creds?.authSource === "newapi") {
    clearByokCreds();
    void clearSession();
  }
  persistActive(false, "");
  updateIndicator();
  refreshRunButton();
  getLegacyBridge().methods.updateRequestPreview?.();
  void getLegacyBridge().methods.refreshHealth?.();
}

function injectButton(): void {
  const switcher = document.querySelector(".auth-source-switcher");
  if (!switcher) return;
  if (document.getElementById("newapiToggleButton")) return;

  const button = document.createElement("button");
  button.id = "newapiToggleButton";
  button.type = "button";
  button.className = "auth-source-button newapi-toggle-button";
  button.textContent = "🪄 new-api 登录";
  button.title = "使用已登录的 new-api 账号一键出图";
  button.addEventListener("click", (): void => {
    if (newapiActive) {
      void triggerLogout();
    } else {
      void triggerLogin();
    }
  });
  switcher.appendChild(button);
  updateIndicator();
}

export async function initNewapiSsoFeature(): Promise<void> {
  injectButton();
  // Restore from localStorage for a snappy first paint before the network check.
  if (localStorage.getItem(NEWAPI_ACTIVE_KEY) === "1") {
    newapiActive = true;
    newapiUsername = localStorage.getItem(NEWAPI_USERNAME_KEY) || "";
    updateIndicator();
    refreshRunButton();
  }
  try {
    const resp = await fetch("/api/health");
    if (resp.ok) {
      const data = await resp.json();
      newapiEnabled = Boolean(data?.newapi_enabled);
      if (data?.newapi_base_url) {
        document.documentElement.setAttribute("data-newapi-base-url", String(data.newapi_base_url));
      }
    }
  } catch {
    newapiEnabled = false;
  }
  const button = document.getElementById("newapiToggleButton");
  if (button) {
    button.style.display = newapiEnabled ? "" : "none";
  }
  await refreshNewapiStatus();
  Object.assign(getLegacyBridge().methods, { isNewapiActive, refreshNewapiStatus });
}
