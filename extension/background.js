"use strict";

const HOST_NAME = "io.github.ilias_download_companion";
let currentRun = null;
let lastRun = null;

function setBadge(text, color) {
  browser.browserAction.setBadgeText({ text });
  browser.browserAction.setBadgeBackgroundColor({ color });
}

function setToolbar(title, badge, color) {
  browser.browserAction.setTitle({ title });
  setBadge(badge, color);
}

function notify(result, title) {
  const success = result.ok;
  const files = result.course?.file_count;
  browser.notifications.create({
    type: "basic",
    title: success ? "ILIAS course updated" : "ILIAS update failed",
    message: success
      ? `${title}: ${files ?? 0} files saved.`
      : `${title}: ${result.error || "Unknown PFERD error"}`
  }).catch(() => {
    // Notification failures must not hide or change the update result.
  });
}

async function updateCourse(url, title) {
  if (currentRun) {
    return {
      ok: false,
      running: true,
      error: `An update for ${currentRun.title} is already running.`,
      startedAt: currentRun.startedAt
    };
  }

  const startedAt = new Date().toISOString();
  setToolbar(`Updating ${title} with PFERD`, "RUN", "#355070");
  const promise = browser.runtime.sendNativeMessage(HOST_NAME, {
    action: "update",
    url,
    title
  });
  currentRun = { url, title, startedAt, promise };

  try {
    const result = await promise;
    const finishedAt = new Date().toISOString();
    lastRun = { ...result, url, title, startedAt, finishedAt, running: false };
    setToolbar(
      result.ok
        ? `${title} updated: ${result.course?.file_count ?? 0} files saved`
        : `${title} update failed: ${result.error}`,
      result.ok ? "OK" : "!",
      result.ok ? "#2a9d8f" : "#b42318"
    );
    notify(result, title);
    return lastRun;
  } catch (error) {
    const result = {
      ok: false,
      error: `Could not contact the local companion: ${error.message}`
    };
    lastRun = {
      ...result,
      url,
      title,
      startedAt,
      finishedAt: new Date().toISOString(),
      running: false
    };
    setToolbar(`${title} update failed: ${result.error}`, "!", "#b42318");
    notify(result, title);
    return lastRun;
  } finally {
    currentRun = null;
  }
}

async function getStatus(message) {
  if (currentRun) {
    return {
      ok: true,
      running: true,
      title: currentRun.title,
      startedAt: currentRun.startedAt,
      sameCourse: currentRun.url === message.url
    };
  }
  if (lastRun?.url === message.url) {
    return lastRun;
  }
  try {
    return await browser.runtime.sendNativeMessage(HOST_NAME, message);
  } catch (error) {
    return {
      ok: false,
      error: `Could not contact the local companion: ${error.message}`
    };
  }
}

browser.runtime.onMessage.addListener((message) => {
  if (message.action === "update") {
    return updateCourse(message.url, message.title);
  }
  if (message.action === "status") {
    return getStatus(message);
  }
  return undefined;
});
