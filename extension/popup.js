"use strict";

const course = document.querySelector("#course");
const button = document.querySelector("#update");
const status = document.querySelector("#status");
let activeUrl = null;

browser.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
  if (!tab || !tab.url || !tab.url.startsWith("https://")) {
    course.textContent = "Open an HTTPS ILIAS course page first.";
    return;
  }
  activeUrl = tab.url;
  course.textContent = new URL(activeUrl).hostname;
  button.disabled = false;
});

button.addEventListener("click", async () => {
  button.disabled = true;
  button.textContent = "Updating...";
  status.textContent = "PFERD is checking the course. You may close this popup.";

  const result = await browser.runtime.sendMessage({
    action: "update",
    url: activeUrl
  });

  button.disabled = false;
  button.textContent = "Update again";
  status.textContent = result.ok
    ? `Updated ${result.profile}.\n${result.summary || "No changes reported."}`
    : result.error;
});
