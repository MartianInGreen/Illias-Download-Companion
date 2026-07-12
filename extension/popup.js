"use strict";

const course = document.querySelector("#course");
const button = document.querySelector("#update");
const status = document.querySelector("#status");
const details = document.querySelector("#details");
const files = document.querySelector("#files");
const added = document.querySelector("#added");
const lastUpdate = document.querySelector("#last-update");
let activeUrl = null;
let activeTitle = null;

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "Never";
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

browser.tabs.query({ active: true, currentWindow: true }).then(async ([tab]) => {
  if (!tab || !tab.url || !tab.url.startsWith("https://")) {
    course.textContent = "Open an HTTPS ILIAS course page first.";
    return;
  }
  activeUrl = tab.url;
  activeTitle = tab.title || "ILIAS course";
  course.textContent = activeTitle;
  const result = await browser.runtime.sendMessage({ action: "status", url: activeUrl });
  if (result.ok) {
    showCourseState(result.course);
  } else {
    status.className = "error";
    status.textContent = result.error;
  }
  button.disabled = false;
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
    showCourseState(result.course);
    status.textContent = `Updated ${result.profile}.\n${result.course.file_count} files saved.\n${result.summary || "No changes reported."}`;
  } else {
    status.className = "error";
    status.textContent = `Update failed. PFERD is not left running.\n${result.error}`;
  }
});
