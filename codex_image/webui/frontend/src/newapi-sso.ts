import { getLegacyBridge } from "./state";

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
    if (data?.ok) {
      const username = String(data.username || localStorage.getItem(NEWAPI_USERNAME_KEY) || "");
      persistActive(true, username);
    } else {
      persistActive(false, "");
    }
  } catch {
    persistActive(false, "");
  }
  updateIndicator();
  refreshRunButton();
}

async function triggerLogin(): Promise<void> {
  try {
    const resp = await fetch("/api/newapi/login", { method: "POST", credentials: "include" });
    if (resp.ok) {
      const data = await resp.json();
      persistActive(true, String(data.username || ""));
      updateIndicator();
      refreshRunButton();
      getLegacyBridge().methods.updateRequestPreview?.();
      return;
    }
  } catch {
    // fall through to redirect
  }
  // Session cookie not shared yet: send the user to new-api to log in first.
  const base = document.documentElement.getAttribute("data-newapi-base-url");
  if (base) {
    const returnUrl = window.location.origin + window.location.pathname;
    window.open(`${base}/login?redirect=${encodeURIComponent(returnUrl)}`, "_blank", "noopener");
  }
}

async function triggerLogout(): Promise<void> {
  try {
    await fetch("/api/newapi/logout", { method: "DELETE", credentials: "include" });
  } catch {
    // ignore
  }
  persistActive(false, "");
  updateIndicator();
  refreshRunButton();
  getLegacyBridge().methods.updateRequestPreview?.();
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
