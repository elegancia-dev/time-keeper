/**
 * Storage abstraction layer.
 *
 * Logs, projects, and settings are stored in SQLite via the native messaging host.
 * The domain cache for fast interception stays in chrome.storage.local.
 */

const HOST_NAME = "com.timekeeper.work_logger";

// --- Native messaging helpers ---

function sendNativeMessage(message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendNativeMessage(HOST_NAME, message, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    } catch (err) {
      reject(err);
    }
  });
}

/**
 * For pages that can't call sendNativeMessage directly (popup, options, intercept),
 * relay through the background service worker.
 */
function sendViaBackground(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: "native", payload: message }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}

// --- Log functions ---

async function addLog(entry) {
  return sendViaBackground({
    action: "add_log",
    task: entry.task,
    project: entry.project,
    duration_estimate: entry.duration_estimate,
    triggered_by: entry.triggered_by,
    triggered_url: entry.triggered_url,
  });
}

async function getLogs(limit, since) {
  const msg = { action: "get_logs" };
  if (limit) msg.limit = limit;
  if (since) msg.since = since;
  const resp = await sendViaBackground(msg);
  return resp?.logs ?? [];
}

async function clearLogs() {
  // No longer supported — logs live in SQLite now and persist
  return;
}

// --- Project functions ---

async function getProjects() {
  const resp = await sendViaBackground({ action: "get_projects" });
  return resp?.projects ?? [];
}

// --- Settings functions ---

async function getSettings() {
  const resp = await sendViaBackground({ action: "get_settings" });
  return resp ?? { domains: [], cooldown_seconds: 30 };
}

async function saveSettings(settings) {
  return sendViaBackground({ action: "save_settings", ...settings });
}

async function getDistractionDomains() {
  const settings = await getSettings();
  return settings.domains;
}

async function getCooldownSeconds() {
  const settings = await getSettings();
  return settings.cooldown_seconds;
}

// --- Domain cache in chrome.storage.local (for fast background interception) ---

async function getCachedDomains() {
  const { cached_domains } = await chrome.storage.local.get("cached_domains");
  return cached_domains ?? null;
}

async function setCachedDomains(domains) {
  return chrome.storage.local.set({ cached_domains: domains });
}

// --- URL utility functions ---

function isDistractionUrl(url, domains) {
  try {
    const hostname = new URL(url).hostname.toLowerCase().replace(/^www\./, "");
    return domains.some(
      (domain) => hostname === domain || hostname.endsWith("." + domain)
    );
  } catch {
    return false;
  }
}

function extractDomain(url) {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return null;
  }
}

function getTodayLogs(logs) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return logs.filter((log) => new Date(log.timestamp) >= today);
}

function generateId() {
  return crypto.randomUUID();
}
