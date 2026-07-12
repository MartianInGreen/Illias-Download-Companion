"use strict";

const course = document.querySelector("#course");
const button = document.querySelector("#update");
const status = document.querySelector("#status");
const details = document.querySelector("#details");
const files = document.querySelector("#files");
const added = document.querySelector("#added");
const lastUpdate = document.querySelector("#last-update");
const runStatus = document.querySelector("#run-status");
const started = document.querySelector("#started");
const duration = document.querySelector("#duration");
let activeUrl = null;
let activeTitle = null;
let statusTimer = null;

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "Never";
}

function formatDuration(start, finish = new Date().toISOString()) {
  if (!start) return "-";
  const seconds = Math.max(0, Math.round((new Date(finish) - new Date(start)) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

function showCourseState(state) {
  details.hidden = false;
  files.textContent = state?.file_count ?? "Not downloaded";
  added.textContent = formatDate(state?.added);
  lastUpdate.textContent = formatDate(state?.last_crawled);
  if (state?.last_status === "failed") {
    status.className = "error";
    status.textContent = `Last update failed:\n${state.last_error}`;
  }
}

function showResult(result) {
  details.hidden = false;
  status.className = "";
  if (result.running) {
    runStatus.textContent = result.sameCourse === false ? "Another course is updating" : "Updating";
    started.textContent = formatDate(result.startedAt);
    duration.textContent = formatDuration(result.startedAt);
    status.textContent = `PFERD is running for ${result.title}. You may close this popup.`;
    button.disabled = true;
    button.textContent = "Update running...";
    return;
  }
  started.textContent = formatDate(result.startedAt || result.course?.last_attempt);
  duration.textContent = formatDuration(result.startedAt, result.finishedAt);
  if (result.course) showCourseState(result.course);
  const failed = !result.ok || result.course?.last_status === "failed";
  runStatus.textContent = failed ? "Failed" : result.course ? "Up to date" : "Not downloaded";
  if (failed) {
    status.className = "error";
    status.textContent = `Last update failed:\n${result.error || result.course?.last_error}`;
  }
}

async function refreshStatus() {
  if (!activeUrl) return;
  const result = await browser.runtime.sendMessage({ action: "status", url: activeUrl });
  if (result.ok || result.running || result.course) {
    showResult(result);
  } else {
    status.className = "error";
    status.textContent = result.error;
  }
  button.disabled = Boolean(result.running);
  if (!result.running && button.textContent === "Update running...") {
    button.textContent = "Update again";
  }
  if (result.running) {
    clearTimeout(statusTimer);
    statusTimer = setTimeout(refreshStatus, 1000);
  }
}

browser.tabs.query({ active: true, currentWindow: true }).then(async ([tab]) => {
  if (!tab || !tab.url || !tab.url.startsWith("https://")) {
    course.textContent = "Open an HTTPS ILIAS course page first.";
    return;
  }
  activeUrl = tab.url;
  activeTitle = tab.title || "ILIAS course";
  course.textContent = activeTitle;
  await refreshStatus();
  button.disabled = false;
  if (statusTimer) button.disabled = true;
});

button.addEventListener("click", async () => {
  button.disabled = true;
  button.textContent = "Updating...";
  status.textContent = "PFERD is checking the course. You may close this popup.";
  status.className = "";

  const result = await browser.runtime.sendMessage({
    action: "update",
    url: activeUrl,
    title: activeTitle
  });

  button.disabled = false;
  button.textContent = "Update again";
  if (result.ok) {
    showResult(result);
    status.textContent = `Updated ${result.profile}.\n${result.course.file_count} files saved.\n${result.summary || "No changes reported."}`;
  } else {
    showResult(result);
    status.className = "error";
    status.textContent = `Update failed. PFERD is not left running.\n${result.error}`;
  }
});

window.addEventListener("unload", () => clearTimeout(statusTimer));
