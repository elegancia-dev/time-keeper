(async () => {
  const logs = await getLogs();
  const todayLogs = getTodayLogs(logs);

  // Stats
  document.getElementById("distraction-count").textContent = todayLogs.length;
  document.getElementById("log-count").textContent = logs.length;

  // Recent logs (last 5)
  const container = document.getElementById("recent-logs");
  const recent = logs.slice(0, 5);

  if (recent.length === 0) return;

  container.innerHTML = "";
  recent.forEach((log) => {
    const time = new Date(log.timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    const div = document.createElement("div");
    div.className = "log-entry";
    div.innerHTML =
      '<div class="log-task">' + escapeHtml(log.task) + "</div>" +
      '<div class="log-meta">' +
        "<span>" + time + "</span>" +
        (log.project ? "<span>" + escapeHtml(log.project) + "</span>" : "") +
        '<span class="log-trigger">' + escapeHtml(log.triggered_by) + "</span>" +
      "</div>";
    container.appendChild(div);
  });
})();

document.getElementById("open-options").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
