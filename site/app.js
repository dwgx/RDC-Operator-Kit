"use strict";

document.documentElement.classList.remove("no-js");

// This page is a static project guide. It has no network or device-control API.
const announcement = document.getElementById("announcement");
const say = (message) => { announcement.textContent = message; };

function selectTab(tab, focus = false) {
  const list = tab.closest('[role="tablist"]');
  for (const candidate of list.querySelectorAll('[role="tab"]')) {
    const selected = candidate === tab;
    candidate.setAttribute("aria-selected", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
    document.getElementById(candidate.getAttribute("aria-controls")).hidden = !selected;
  }
  if (focus) tab.focus();
}

for (const list of document.querySelectorAll('[role="tablist"]')) {
  const tabs = Array.from(list.querySelectorAll('[role="tab"]'));
  for (const tab of tabs) {
    tab.addEventListener("click", () => selectTab(tab));
    tab.addEventListener("keydown", (event) => {
      const index = tabs.indexOf(tab);
      let next;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        selectTab(tabs[next], true);
      }
    });
  }
}

const themeButton = document.getElementById("theme-toggle");
const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
let savedTheme;
try { savedTheme = localStorage.getItem("rdc-operator-kit-theme"); } catch { /* Storage is optional. */ }
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const label = theme === "dark" ? "切换浅色主题" : "切换深色主题";
  themeButton.setAttribute("aria-label", label);
  themeButton.title = label;
}
applyTheme(savedTheme === "light" || savedTheme === "dark" ? savedTheme : (systemTheme.matches ? "dark" : "light"));
themeButton.addEventListener("click", () => {
  savedTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(savedTheme);
  try { localStorage.setItem("rdc-operator-kit-theme", savedTheme); } catch { /* Still works for this visit. */ }
});
systemTheme.addEventListener("change", (event) => {
  if (!savedTheme) applyTheme(event.matches ? "dark" : "light");
});

const copyResetTimers = new WeakMap();
for (const button of document.querySelectorAll("[data-copy]")) {
  button.addEventListener("click", async () => {
    const code = document.getElementById(button.dataset.copy);
    if (!code || button.disabled) return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    window.clearTimeout(copyResetTimers.get(button));
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = "已复制";
      say("内容已复制。网页没有执行任何命令。");
    } catch {
      try {
        const selection = window.getSelection();
        if (!selection) throw new Error("Text selection unavailable");
        const range = document.createRange();
        range.selectNodeContents(code);
        selection.removeAllRanges();
        selection.addRange(range);
        button.textContent = "已选中";
        say("剪贴板不可用，已选中文字，请按复制快捷键。");
      } catch {
        button.textContent = "复制失败";
        say("无法写入剪贴板或自动选中。请手动选择需要的文字。");
      }
    } finally {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      copyResetTimers.set(button, window.setTimeout(() => {
        button.textContent = "复制";
        copyResetTimers.delete(button);
      }, 2200));
    }
  });
}

const filterButtons = Array.from(document.querySelectorAll("[data-filter]"));
const cards = Array.from(document.querySelectorAll("[data-kind]"));
const search = document.getElementById("evidence-search");
const clearSearch = document.getElementById("evidence-clear");
const resetEvidence = document.getElementById("evidence-reset");
const evidenceResult = document.getElementById("evidence-result");
const evidenceEmpty = document.getElementById("evidence-empty");
let evidenceKind = "all";
const normalizeSearch = (value) => value.normalize("NFKC").toLowerCase().trim();
const searchableCards = cards.map((card) => ({ card, text: normalizeSearch(card.textContent) }));

function applyEvidenceFilter() {
  const query = normalizeSearch(search.value);
  const terms = query.split(/\s+/).filter(Boolean);
  let visible = 0;
  for (const { card, text } of searchableCards) {
    card.hidden = (evidenceKind !== "all" && card.dataset.kind !== evidenceKind)
      || !terms.every((term) => text.includes(term));
    if (!card.hidden) visible += 1;
  }
  for (const button of filterButtons) {
    button.setAttribute("aria-pressed", String(button.dataset.filter === evidenceKind));
  }
  clearSearch.hidden = !query;
  evidenceEmpty.hidden = visible !== 0;
  evidenceResult.textContent = query || evidenceKind !== "all"
    ? `显示 ${visible} / ${cards.length} 项证据`
    : `显示全部 ${cards.length} 项证据`;
}

for (const button of filterButtons) {
  button.addEventListener("click", () => {
    evidenceKind = button.dataset.filter;
    applyEvidenceFilter();
  });
}
search.addEventListener("input", applyEvidenceFilter);
search.addEventListener("keydown", (event) => {
  // Escape belongs to the IME while a composition is in progress.
  if (event.isComposing || event.keyCode === 229) return;
  if (event.key === "Escape") {
    event.preventDefault();
    search.value = "";
    applyEvidenceFilter();
  }
});
clearSearch.addEventListener("click", () => {
  search.value = "";
  applyEvidenceFilter();
  search.focus();
});
resetEvidence.addEventListener("click", () => {
  evidenceKind = "all";
  search.value = "";
  applyEvidenceFilter();
  search.focus();
});
applyEvidenceFilter();

document.getElementById("show-browser").addEventListener("click", () => {
  selectTab(document.getElementById("tab-browser"), true);
  document.getElementById("capabilities").scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
});

// Open inline reference sections in the single-file preview.
for (const link of document.querySelectorAll('a[href^="#reference-"]')) {
  link.addEventListener("click", () => {
    const section = document.getElementById(link.getAttribute("href").slice(1));
    const details = section?.querySelector("details");
    if (details) details.open = true;
  });
}
