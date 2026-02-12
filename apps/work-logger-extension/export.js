async function exportLogs() {
  const logs = await getLogs();
  const exported = {
    source: "work-logger-extension",
    exported_at: new Date().toISOString(),
    entries: logs.map((log) => ({
      id: log.id,
      timestamp: log.timestamp,
      task: log.task,
      project: log.project || null,
      duration_estimate: log.duration_estimate || null,
      triggered_by: log.triggered_by,
      triggered_url: log.triggered_url,
    })),
  };
  return exported;
}

function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function exportAndDownload() {
  const data = await exportLogs();
  const date = new Date().toISOString().split("T")[0];
  downloadJson(data, `work-logger-export-${date}.json`);
}

async function exportAndClear() {
  await exportAndDownload();
  await clearLogs();
}
