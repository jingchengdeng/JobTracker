(function () {
  "use strict";

  const BACKEND_URL_DEFAULT = "http://localhost:8000";
  const JOB_VIEW_PATTERN = /\/jobs\/view\//;
  const URL_POLL_INTERVAL = 500;

  let lastUrl = location.href;
  let saveButton = null;

  // --- URL polling for SPA navigation ---
  setInterval(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      onUrlChange();
    }
  }, URL_POLL_INTERVAL);

  // Also run on initial load
  onUrlChange();

  function onUrlChange() {
    if (JOB_VIEW_PATTERN.test(location.href)) {
      waitForContentThenInject();
    } else {
      removeButton();
    }
  }

  function waitForContentThenInject() {
    let attempts = 0;
    const maxAttempts = 10;
    const interval = 500;

    const check = () => {
      attempts++;
      const mainContent = document.querySelector("main");
      const hasContent =
        mainContent && mainContent.innerText.length > 200;

      if (hasContent) {
        injectButton();
      } else if (attempts < maxAttempts) {
        setTimeout(check, interval);
      }
    };

    check();
  }

  function injectButton() {
    removeButton();

    saveButton = document.createElement("button");
    saveButton.id = "jobtracker-save-btn";
    saveButton.textContent = "Save to JobTracker";
    saveButton.addEventListener("click", onSaveClick);
    document.body.appendChild(saveButton);
  }

  function removeButton() {
    if (saveButton) {
      saveButton.remove();
      saveButton = null;
    }
  }

  function setButtonState(state, text) {
    if (!saveButton) return;
    saveButton.className = "";
    if (state) saveButton.classList.add(state);
    saveButton.textContent = text || "Save to JobTracker";
  }

  async function getBackendUrl() {
    return new Promise((resolve) => {
      chrome.storage.local.get("backendUrl", (result) => {
        resolve(result.backendUrl || BACKEND_URL_DEFAULT);
      });
    });
  }

  async function onSaveClick() {
    setButtonState("loading", "Extracting...");

    try {
      const result = extractJobData();

      if (!result) {
        setButtonState("error", "No job data found");
        setTimeout(() => setButtonState(null, "Save to JobTracker"), 3000);
        return;
      }

      setButtonState("loading", "Saving...");

      const backendUrl = await getBackendUrl();
      const response = await fetch(`${backendUrl}/api/extension/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: location.href,
          extracted: result.extracted,
          rawPanelText: result.rawPanelText,
          timestamp: new Date().toISOString().replace(/[:.]/g, "-"),
        }),
      });

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const data = await response.json();
      setButtonState("success", "Saved!");
      console.log("[JobTracker] Saved:", data.filename);
      setTimeout(() => setButtonState(null, "Save to JobTracker"), 3000);
    } catch (err) {
      console.error("[JobTracker] Error:", err);
      const msg =
        err.message === "Failed to fetch"
          ? "Cannot reach backend"
          : "Save failed";
      setButtonState("error", msg);
      setTimeout(() => setButtonState(null, "Save to JobTracker"), 3000);
    }
  }

  // Placeholder — implemented in Task 5
  function extractJobData() {
    return null;
  }
})();
