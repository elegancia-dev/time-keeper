// Load current settings
(async () => {
  const settings = await getSettings();
  document.getElementById("domains").value = (settings.domains || []).join("\n");
  document.getElementById("cooldown").value = settings.cooldown_seconds || 30;

  await renderLogs();
})();

// Save domains
document.getElementById("save-domains").addEventListener("click", async () => {
  const text = document.getElementById("domains").value;
  const domains = text
    .split("\n")
    .map((d) => {
      let clean = d.trim().toLowerCase();
      clean = clean.replace(/^https?:\/\//, "");
      clean = clean.replace(/^www\./, "");
      clean = clean.split(/[/?#]/)[0];
      return clean;
    })
    .filter((d) => d.length > 0);
  await saveSettings({ domains });
  showToast("Domains saved");
});

// Save cooldown
document.getElementById("save-cooldown").addEventListener("click", async () => {
  const value = parseInt(document.getElementById("cooldown").value, 10);
  if (isNaN(value) || value < 0) return;
  await saveSettings({ cooldown_seconds: value });
  showToast("Cooldown saved");
});

async function renderLogs() {
  const logs = await getLogs(100);
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
      '<div class="log-task">' + escapeHtml(log.task || "") + "</div>" +
      '<div class="log-meta">' +
        "<span>" + time + "</span>" +
        (log.project ? "<span>" + escapeHtml(log.project) + "</span>" : "") +
        (log.duration_estimate ? "<span>" + escapeHtml(log.duration_estimate) + "</span>" : "") +
        '<span class="log-trigger">' + escapeHtml(log.triggered_by || "") + "</span>" +
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
