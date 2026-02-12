const DEFAULT_DOMAINS = [
  "instagram.com",
  "reddit.com",
  "twitter.com",
  "x.com",
  "facebook.com",
  "tiktok.com",
  "youtube.com",
];

const DEFAULT_COOLDOWN = 30;

async function getStorage(keys) {
  return chrome.storage.local.get(keys);
}

async function setStorage(data) {
  return chrome.storage.local.set(data);
}

async function getDistractionDomains() {
  const { distraction_domains } = await getStorage("distraction_domains");
  return distraction_domains ?? DEFAULT_DOMAINS;
}

async function setDistractionDomains(domains) {
  return setStorage({ distraction_domains: domains });
}

async function addDistractionDomain(domain) {
  const domains = await getDistractionDomains();
  const normalized = domain.toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").split(/[/?#]/)[0];
  if (!domains.includes(normalized)) {
    domains.push(normalized);
    await setDistractionDomains(domains);
  }
  return domains;
}

async function removeDistractionDomain(domain) {
  const domains = await getDistractionDomains();
  const filtered = domains.filter((d) => d !== domain);
  await setDistractionDomains(filtered);
  return filtered;
}

async function getCooldownSeconds() {
  const { cooldown_seconds } = await getStorage("cooldown_seconds");
  return cooldown_seconds ?? DEFAULT_COOLDOWN;
}

async function setCooldownSeconds(seconds) {
  return setStorage({ cooldown_seconds: seconds });
}

async function getLogs() {
  const { logs } = await getStorage("logs");
  return logs ?? [];
}

async function addLog(entry) {
  const logs = await getLogs();
  logs.unshift(entry);
  await setStorage({ logs });

  // Update projects list
  if (entry.project) {
    const projects = await getProjects();
    if (!projects.includes(entry.project)) {
      projects.push(entry.project);
      await setStorage({ projects });
    }
  }

  return logs;
}

async function clearLogs() {
  return setStorage({ logs: [] });
}

async function getProjects() {
  const { projects } = await getStorage("projects");
  return projects ?? [];
}

function generateId() {
  return crypto.randomUUID();
}

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
