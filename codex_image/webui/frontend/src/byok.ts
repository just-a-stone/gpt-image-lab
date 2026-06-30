import { getLegacyBridge } from "./state";

const BYOK_STORAGE_KEY = "ilab_byok_creds";
const DEFAULT_BYOK_BASE_URL = "https://image.feiyang.click/v1";

export interface ByokCreds {
  apiKey: string;
  baseUrl: string;
  imageModel: string;
  enabled: boolean;
}

export function getByokCreds(): ByokCreds | null {
  try {
    const raw = localStorage.getItem(BYOK_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    return {
      apiKey: String(parsed.apiKey || ""),
      baseUrl: String(parsed.baseUrl || ""),
      imageModel: String(parsed.imageModel || ""),
      enabled: Boolean(parsed.enabled),
    };
  } catch {
    return null;
  }
}

export function isByokActive(): boolean {
  const creds = getByokCreds();
  return Boolean(creds && creds.apiKey.trim());
}

export function saveByokCreds(creds: ByokCreds): void {
  localStorage.setItem(BYOK_STORAGE_KEY, JSON.stringify(creds));
}

export function clearByokCreds(): void {
  localStorage.removeItem(BYOK_STORAGE_KEY);
}

export function appendByokToForm(form: FormData): boolean {
  if (!isByokActive()) return false;
  const creds = getByokCreds();
  if (!creds) return false;
  form.append("byok_api_key", creds.apiKey.trim());
  const baseUrl = creds.baseUrl.trim() || DEFAULT_BYOK_BASE_URL;
  form.append("byok_base_url", baseUrl);
  if (creds.imageModel.trim()) form.append("byok_image_model", creds.imageModel.trim());
  return true;
}

function refreshRunButton(): void {
  const bridge = getLegacyBridge();
  const els = bridge.els;
  if (!els?.runButton) return;
  const available = Boolean(bridge.state.authAvailable) || isByokActive();
  els.runButton.disabled = !available;
}

function updateByokIndicator(): void {
  const button = document.getElementById("byokToggleButton");
  if (!button) return;
  button.classList.toggle("active", isByokActive());
  button.textContent = isByokActive() ? "🔑 自带Key · 已启用" : "🔑 自带Key";
}

function bindByokPopover(): void {
  const popover = document.getElementById("byokPopover");
  const keyInput = document.getElementById("byokApiKeyInput") as HTMLInputElement | null;
  const baseUrlInput = document.getElementById("byokBaseUrlInput") as HTMLInputElement | null;
  const modelInput = document.getElementById("byokImageModelInput") as HTMLInputElement | null;
  const enabledToggle = document.getElementById("byokEnabledToggle") as HTMLInputElement | null;
  const saveButton = document.getElementById("byokSaveButton");
  const clearButton = document.getElementById("byokClearButton");
  const closeButton = document.getElementById("byokCloseButton");
  if (!popover || !keyInput || !baseUrlInput || !modelInput || !enabledToggle || !saveButton || !clearButton || !closeButton) return;

  const creds = getByokCreds();
  keyInput.value = creds?.apiKey || "";
  baseUrlInput.value = creds?.baseUrl || DEFAULT_BYOK_BASE_URL;
  modelInput.value = creds?.imageModel || "";
  enabledToggle.checked = true;
  enabledToggle.disabled = true;

  const persist = (): void => {
    saveByokCreds({
      apiKey: keyInput.value.trim(),
      baseUrl: baseUrlInput.value.trim(),
      imageModel: modelInput.value.trim(),
      enabled: true,
    });
    updateByokIndicator();
    refreshRunButton();
    getLegacyBridge().methods.updateRequestPreview?.();
  };

  saveButton.addEventListener("click", persist);
  clearButton.addEventListener("click", (): void => {
    clearByokCreds();
    keyInput.value = "";
    baseUrlInput.value = "";
    modelInput.value = "";
    enabledToggle.checked = true;
    updateByokIndicator();
    refreshRunButton();
    getLegacyBridge().methods.updateRequestPreview?.();
  });
  closeButton.addEventListener("click", (): void => popover.classList.add("hidden"));
}

function injectByokUi(): void {
  const switcher = document.querySelector(".auth-source-switcher");
  if (!switcher) return;
  if (document.getElementById("byokToggleButton")) return;

  const button = document.createElement("button");
  button.id = "byokToggleButton";
  button.type = "button";
  button.className = "auth-source-button byok-toggle-button";
  button.textContent = "🔑 自带Key";
  button.title = "使用自己的 API Key（浏览器本地保存）";
  button.addEventListener("click", (): void => {
    const popover = document.getElementById("byokPopover");
    if (popover) popover.classList.toggle("hidden");
  });
  switcher.appendChild(button);

  const popover = document.createElement("div");
  popover.id = "byokPopover";
  popover.className = "byok-popover hidden";
  popover.setAttribute("role", "dialog");
  popover.innerHTML = `
    <div class="byok-popover-title">自带 API Key（仅保存在本浏览器）</div>
    <label class="byok-field">
      <span>API Key</span>
      <input id="byokApiKeyInput" type="password" autocomplete="off" placeholder="sk-..." />
    </label>
    <label class="byok-field">
      <span>Base URL</span>
      <input id="byokBaseUrlInput" type="text" autocomplete="off" placeholder="https://image.feiyang.click/v1" />
    </label>
    <label class="byok-field">
      <span>图像模型</span>
      <input id="byokImageModelInput" type="text" autocomplete="off" placeholder="gpt-image-2" />
    </label>
    <label class="byok-checkbox">
      <input id="byokEnabledToggle" type="checkbox" checked disabled />
      <span>启用 BYOK（始终开启）</span>
    </label>
    <div class="byok-popover-actions">
      <button id="byokSaveButton" type="button" class="primary-button">保存</button>
      <button id="byokClearButton" type="button" class="ghost-button">清除</button>
      <button id="byokCloseButton" type="button" class="ghost-button">关闭</button>
    </div>
  `;
  document.body.appendChild(popover);

  bindByokPopover();
  updateByokIndicator();
}

export function initByokFeature(): void {
  injectByokUi();
  Object.assign(getLegacyBridge().methods, {
    isByokActive,
    appendByokToForm,
    refreshByokRunButton: refreshRunButton,
  });
  refreshRunButton();
}
