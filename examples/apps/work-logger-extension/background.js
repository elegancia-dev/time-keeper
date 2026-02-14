importScripts("storage.js");

// Track tabs that are temporarily allowed to pass through
const allowedTabs = new Set();

// Cache distraction domains in memory for synchronous access
let cachedDomains = null;

async function loadDomains() {
  try {
    const resp = await sendNativeMessage({ action: "get_settings" });
    cachedDomains = resp.domains;
    await setCachedDomains(cachedDomains);
  } catch (e) {
    // Fall back to local cache if native host isn't available
    cachedDomains = await getCachedDomains();
  }
  return cachedDomains;
}

// Load domains on startup
loadDomains();

// Monitor tab navigations — use onBeforeNavigate for earliest interception
chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (details.frameId !== 0) return;

  if (
    !details.url.startsWith("http://") &&
    !details.url.startsWith("https://")
  )
    return;

  // Check if this tab has a one-time pass
  if (allowedTabs.has(details.tabId)) {
    allowedTabs.delete(details.tabId);
    return;
  }

  // Use cached domains to avoid async delay; fall back to storage read
  const domains = cachedDomains ?? (await loadDomains());
  if (!domains) return;

  if (isDistractionUrl(details.url, domains)) {
    const domain = extractDomain(details.url);
    const interceptUrl =
      chrome.runtime.getURL("intercept.html") +
      "?url=" +
      encodeURIComponent(details.url) +
      "&domain=" +
      encodeURIComponent(domain);
    chrome.tabs.update(details.tabId, { url: interceptUrl });
  }
});

// Handle messages from extension pages
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "allow-once" && sender.tab) {
    allowedTabs.add(sender.tab.id);
    sendResponse({ ok: true });
    return false;
  }

  // Relay native messaging calls from extension pages
  if (message.type === "native" && message.payload) {
    (async () => {
      try {
        const response = await sendNativeMessage(message.payload);
        if (message.payload.action === "save_settings") {
          loadDomains();
        }
        sendResponse(response);
      } catch (err) {
        sendResponse({ ok: false, error: err.message });
      }
    })();
    return true; // keep sendResponse channel open for async
  }
});

// Context menu: "Add to distraction list"
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "add-distraction",
    title: "Add to distraction list",
    contexts: ["page"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "add-distraction" && tab?.url) {
    const domain = extractDomain(tab.url);
    if (domain) {
      try {
        const settings = await sendNativeMessage({ action: "get_settings" });
        const domains = settings.domains || [];
        if (!domains.includes(domain)) {
          domains.push(domain);
          await sendNativeMessage({ action: "save_settings", domains });
          await loadDomains();
        }
        chrome.action.setBadgeText({ text: "+", tabId: tab.id });
        chrome.action.setBadgeBackgroundColor({
          color: "#4CAF50",
          tabId: tab.id,
        });
        setTimeout(() => {
          chrome.action.setBadgeText({ text: "", tabId: tab.id });
        }, 2000);
      } catch (e) {
        console.error("Failed to add domain:", e);
      }
    }
  }
});
