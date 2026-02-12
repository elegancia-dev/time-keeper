const params = new URLSearchParams(window.location.search);
const originalUrl = params.get("url");
const domain = params.get("domain");

// Populate domain name
document.getElementById("domain-name").textContent = domain;
document.getElementById("continue-domain").textContent = domain;

// Populate projects dropdown
(async () => {
  const projects = await getProjects();
  const select = document.getElementById("project-select");
  projects.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    select.appendChild(opt);
  });
})();

// Duration selection
let selectedDuration = "30m";
document.querySelectorAll(".duration-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".duration-btn").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    selectedDuration = btn.dataset.value;
  });
});

// Form submission
document.getElementById("log-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const task = document.getElementById("task").value.trim();
  if (!task) return;

  const projectSelect = document.getElementById("project-select").value;
  const projectCustom = document.getElementById("project-custom").value.trim();
  const project = projectCustom || projectSelect;

  const entry = {
    id: generateId(),
    timestamp: new Date().toISOString(),
    task,
    project: project || null,
    duration_estimate: selectedDuration,
    triggered_by: domain,
    triggered_url: originalUrl,
  };

  await addLog(entry);

  // Switch to cooldown phase
  document.getElementById("log-phase").classList.add("hidden");
  document.getElementById("cooldown-phase").classList.remove("hidden");

  startCooldown();
});

async function startCooldown() {
  const totalSeconds = await getCooldownSeconds();
  let remaining = totalSeconds;

  const countdownEl = document.getElementById("countdown");
  const progressEl = document.getElementById("timer-progress");
  const continueBtn = document.getElementById("continue-btn");

  countdownEl.textContent = remaining;

  const interval = setInterval(() => {
    remaining--;
    countdownEl.textContent = remaining;
    const pct = ((totalSeconds - remaining) / totalSeconds) * 100;
    progressEl.style.width = (100 - pct) + "%";

    if (remaining <= 0) {
      clearInterval(interval);
      continueBtn.classList.remove("hidden");
    }
  }, 1000);
}

// "Go back to work" closes the tab or goes back
document.getElementById("back-to-work").addEventListener("click", () => {
  if (window.history.length > 1) {
    window.history.back();
  } else {
    window.close();
  }
});

// "Continue to site" navigates to original URL — bypass interception via direct assignment
document.getElementById("continue-btn").addEventListener("click", () => {
  // Send message to background to allow this navigation
  chrome.runtime.sendMessage({ type: "allow-once", url: originalUrl }, () => {
    window.location.href = originalUrl;
  });
});
