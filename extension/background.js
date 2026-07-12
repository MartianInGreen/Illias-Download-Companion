"use strict";

const HOST_NAME = "io.github.ilias_download_companion";
let currentRun = null;

function setBadge(text, color) {
  browser.browserAction.setBadgeText({ text });
  browser.browserAction.setBadgeBackgroundColor({ color });
}

async function updateCourse(url) {
  if (currentRun) {
    return { ok: false, error: "An update is already running." };
  }

  setBadge("...", "#355070");
  currentRun = browser.runtime.sendNativeMessage(HOST_NAME, {
    action: "update",
    url
  });

  try {
    const result = await currentRun;
    setBadge(result.ok ? "OK" : "!", result.ok ? "#2a9d8f" : "#b42318");
    return result;
  } catch (error) {
    setBadge("!", "#b42318");
    return {
      ok: false,
      error: `Could not contact the local companion: ${error.message}`
    };
  } finally {
    currentRun = null;
    setTimeout(() => browser.browserAction.setBadgeText({ text: "" }), 10000);
  }
}

browser.runtime.onMessage.addListener((message) => {
  if (message.action === "update") {
    return updateCourse(message.url);
  }
  return undefined;
});
