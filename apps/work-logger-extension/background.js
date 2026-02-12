importScripts("storage.js");

// Track tabs that are temporarily allowed to pass through
const allowedTabs = new Set();

// Cache distraction domains in memory for synchronous access
let cachedDomains = null;

async function loadDomains() {
  cachedDomains = await getDistractionDomains();
  return cachedDomains;
}

// Load domains on startup
loadDomains();

// Reload cache whenever storage changes
chrome.storage.onChanged.addListener((changes) => {
  if (changes.distraction_domains) {
    cachedDomains = changes.distraction_domains.newValue;
  }
});

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

// Handle "allow-once" messages from intercept page
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "allow-once" && sender.tab) {
    allowedTabs.add(sender.tab.id);
    sendResponse({ ok: true });
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
      await addDistractionDomain(domain);
      chrome.action.setBadgeText({ text: "+", tabId: tab.id });
      chrome.action.setBadgeBackgroundColor({
        color: "#4CAF50",
        tabId: tab.id,
      });
      setTimeout(() => {
        chrome.action.setBadgeText({ text: "", tabId: tab.id });
      }, 2000);
    }
  }
});
