// Load current settings
(async () => {
  const domains = await getDistractionDomains();
  document.getElementById("domains").value = domains.join("\n");

  const cooldown = await getCooldownSeconds();
  document.getElementById("cooldown").value = cooldown;

  await renderLogs();
})();

// Save domains
document.getElementById("save-domains").addEventListener("click", async () => {
  const text = document.getElementById("domains").value;
  const domains = text
    .split("\n")
    .map((d) => {
      let clean = d.trim().toLowerCase();
      // Strip protocol
      clean = clean.replace(/^https?:\/\//, "");
      // Strip www prefix
      clean = clean.replace(/^www\./, "");
      // Strip path, query, hash, trailing slash
      clean = clean.split(/[/?#]/)[0];
      return clean;
    })
    .filter((d) => d.length > 0);
  await setDistractionDomains(domains);
  showToast("Domains saved");
});

// Save cooldown
document.getElementById("save-cooldown").addEventListener("click", async () => {
  const value = parseInt(document.getElementById("cooldown").value, 10);
  if (isNaN(value) || value < 0) return;
  await setCooldownSeconds(value);
  showToast("Cooldown saved");
});

// Export
document.getElementById("export-btn").addEventListener("click", async () => {
  await exportAndDownload();
  showToast("Logs exported");
});

document.getElementById("export-clear-btn").addEventListener("click", async () => {
  await exportAndClear();
  showToast("Logs exported and cleared");
  await renderLogs();
});

async function renderLogs() {
  const logs = await getLogs();
  const container = document.getElementById("all-logs");

  if (logs.length === 0) {
    container.innerHTML = '<p class="empty">No logs yet.</p>';
    return;
  }

  container.innerHTML = "";
  logs.forEach((log) => {
    const time = new Date(log.timestamp).toLocaleString();
    const div = document.createElement("div");
    div.className = "log-entry";
    div.innerHTML =
      '<div class="log-task">' + escapeHtml(log.task) + "</div>" +
      '<div class="log-meta">' +
        "<span>" + time + "</span>" +
        (log.project ? "<span>" + escapeHtml(log.project) + "</span>" : "") +
        (log.duration_estimate ? "<span>" + escapeHtml(log.duration_estimate) + "</span>" : "") +
        '<span class="log-trigger">' + escapeHtml(log.triggered_by) + "</span>" +
      "</div>";
    container.appendChild(div);
  });
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 2000);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
