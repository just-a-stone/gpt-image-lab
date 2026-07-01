import { getLegacyBridge } from "./state";
import { translate } from "./i18n";

const bridge = getLegacyBridge();
const state = bridge.state;
const els = bridge.els;

function setStatus(msg: string, kind: string): void {
  const fn = getLegacyBridge().methods.setStatus;
  if (typeof fn === "function") fn(msg, kind);
}

function renderTasks(): void {
  const fn = getLegacyBridge().methods.renderTasks;
  if (typeof fn === "function") fn();
}

function taskOutputUrls(task: any): string[] {
  const fn = getLegacyBridge().methods.taskOutputUrls;
  if (typeof fn === "function") return fn(task) || [];
  return Array.isArray(task?.output_urls) ? task.output_urls : [];
}

function closePromptPopover(): void {
  const fn = getLegacyBridge().methods.closePromptPopover;
  if (typeof fn === "function") fn();
}

function openConfirmPopover(...args: any[]): void {
  const fn = getLegacyBridge().methods.openConfirmPopover as ((...a: any[]) => void) | undefined;
  if (typeof fn === "function") fn(...args);
}

interface ShareInfo {
  shared: boolean;
  share_id?: string;
  shared_at?: string;
  show_prompt?: boolean;
  share_note?: string;
}

async function fetchShareStatus(taskId: string): Promise<ShareInfo> {
  const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/share`);
  if (!res.ok) return { shared: false };
  return await res.json().catch(() => ({ shared: false }));
}

async function shareTask(taskId: string, showPrompt: boolean, shareNote: string): Promise<boolean> {
  const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ show_prompt: showPrompt, share_note: shareNote }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || translate("share.createFailed"));
  }
  return true;
}

async function unshareTask(taskId: string): Promise<void> {
  const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/share`, { method: "DELETE" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || translate("share.revokeFailed"));
  }
}

async function openShareDialog(button: HTMLElement, taskId: string): Promise<void> {
  const task = state.tasks.find((item: any) => String(item.task_id) === String(taskId));
  if (!task) return;
  if (task.status && !["completed", "partial_failed"].includes(task.status)) {
    setStatus(translate("share.onlyCompleted"), "error");
    return;
  }
  if (taskOutputUrls(task).length === 0) {
    setStatus(translate("share.noOutput"), "error");
    return;
  }

  closePromptPopover();

  let shareInfo: ShareInfo;
  try {
    shareInfo = await fetchShareStatus(taskId);
  } catch {
    setStatus(translate("share.statusFailed"), "error");
    return;
  }

  if (shareInfo.shared) {
    openConfirmPopover(button, {
      title: translate("share.revokeTitle"),
      message: translate("share.revokeMessage"),
      confirmText: translate("share.revokeConfirm"),
      onConfirm: async () => {
        try {
          await unshareTask(taskId);
          task.shared_at = null;
          renderTasks();
          setStatus(translate("share.revoked"), "ok");
        } catch (err) {
          setStatus(err instanceof Error ? err.message : translate("share.revokeFailed"), "error");
        }
      },
    });
    return;
  }

  const promptText = task.prompt || "";
  const showPromptDefault = true;
  const dialog = document.createElement("div");
  dialog.className = "share-dialog-overlay";
  dialog.innerHTML = "";

  const card = document.createElement("div");
  card.className = "share-dialog-card";

  const title = document.createElement("div");
  title.className = "share-dialog-title";
  title.textContent = translate("share.dialogTitle");
  card.appendChild(title);

  const desc = document.createElement("div");
  desc.className = "share-dialog-desc";
  desc.textContent = translate("share.dialogDesc");
  card.appendChild(desc);

  const promptSection = document.createElement("div");
  promptSection.className = "share-dialog-section";
  const promptLabel = document.createElement("label");
  promptLabel.className = "share-dialog-checkbox-row";
  const promptCheckbox = document.createElement("input");
  promptCheckbox.type = "checkbox";
  promptCheckbox.checked = showPromptDefault;
  promptCheckbox.id = "share-show-prompt";
  promptLabel.appendChild(promptCheckbox);
  const promptLabelText = document.createElement("span");
  promptLabelText.textContent = translate("share.showPrompt");
  promptLabel.appendChild(promptLabelText);
  promptSection.appendChild(promptLabel);

  const promptPreview = document.createElement("div");
  promptPreview.className = "share-dialog-prompt-preview";
  promptPreview.textContent = promptText;
  promptSection.appendChild(promptPreview);
  card.appendChild(promptSection);

  const noteSection = document.createElement("div");
  noteSection.className = "share-dialog-section";
  const noteLabel = document.createElement("label");
  noteLabel.className = "share-dialog-note-label";
  noteLabel.htmlFor = "share-note-input";
  noteLabel.textContent = translate("share.noteLabel");
  noteSection.appendChild(noteLabel);
  const noteInput = document.createElement("input");
  noteInput.type = "text";
  noteInput.className = "share-dialog-note-input";
  noteInput.id = "share-note-input";
  noteInput.placeholder = translate("share.notePlaceholder");
  noteInput.maxLength = 500;
  noteSection.appendChild(noteInput);
  card.appendChild(noteSection);

  const warning = document.createElement("div");
  warning.className = "share-dialog-warning";
  warning.textContent = translate("share.warning");
  card.appendChild(warning);

  const actions = document.createElement("div");
  actions.className = "share-dialog-actions";
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "ghost-button";
  cancelBtn.textContent = translate("action.cancel");
  cancelBtn.addEventListener("click", () => dialog.remove());
  actions.appendChild(cancelBtn);
  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button";
  confirmBtn.className = "primary-button";
  confirmBtn.textContent = translate("share.confirm");
  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    try {
      await shareTask(taskId, promptCheckbox.checked, noteInput.value.trim());
        task.shared_at = new Date().toISOString();
        renderTasks();
        dialog.remove();
        setStatus(translate("share.shared"), "ok");
    } catch (err) {
      confirmBtn.disabled = false;
      setStatus(err instanceof Error ? err.message : translate("share.createFailed"), "error");
    }
  });
  actions.appendChild(confirmBtn);
  card.appendChild(actions);

  dialog.appendChild(card);
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.remove();
  });

  document.body.appendChild(dialog);
}

export function initShareFeature(): void {
  Object.assign(getLegacyBridge().methods, {
    openShareDialog,
  });
}
