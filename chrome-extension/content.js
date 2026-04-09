(function () {
  "use strict";

  const BACKEND_URL_DEFAULT = "http://localhost:3000";
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
    return chrome.runtime.sendMessage({ type: "GET_BACKEND_URL" });
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
      const payload = {
        url: location.href,
        extracted: result.extracted,
        rawPanelText: result.rawPanelText,
        timestamp: new Date().toISOString().replace(/[:.]/g, "-"),
      };

      const resp = await chrome.runtime.sendMessage({
        type: "SAVE_EXTRACTION",
        backendUrl,
        payload,
      });

      if (!resp || !resp.success) {
        throw new Error(resp?.error || "Background script error");
      }

      setButtonState("success", "Saved!");
      console.log("[JobTracker] Saved:", resp.data.filename);
      setTimeout(() => setButtonState(null, "Save to JobTracker"), 3000);
    } catch (err) {
      console.error("[JobTracker] Error:", err);
      const msg =
        err.message === "Failed to fetch" || err.message.includes("Failed to fetch")
          ? "Cannot reach backend"
          : "Save failed";
      setButtonState("error", msg);
      setTimeout(() => setButtonState(null, "Save to JobTracker"), 3000);
    }
  }

  // --- Raw Data Collection ---
  // Collects raw text from specific DOM selectors for each field.
  // No client-side extraction — LLM handles parsing later.
  // Each selector is documented in docs/linkedin-extraction-patterns.md

  const FIELD_SELECTORS = [
    // Company
    { field: "company", selector: '[data-view-name="job-details-about-company-name-link"]' },
    { field: "company", selector: '[data-view-name="job-details-about-company-module"]' },
    // Title (two button variants)
    { field: "title", selector: 'button[aria-label^="Easy Apply to"]', attr: "aria-label" },
    { field: "title", selector: 'button[aria-label^="Apply to"]', attr: "aria-label" },
    // Top card (location, salary, workMode, jobType)
    { field: "top_card", selector: '.t-14.artdeco-card' },
    // Job description
    { field: "description", selector: '.jobs-description-content' },
  ];

  function extractJobData() {
    const rawSections = [];

    for (const { field, selector, attr } of FIELD_SELECTORS) {
      const el = document.querySelector(selector);
      if (!el) continue;
      const text = attr
        ? el.getAttribute(attr)?.trim()
        : el.innerText?.trim();
      if (!text) continue;
      rawSections.push(`[field: ${field}]\n[selector: ${selector}]\n${text}`);
    }

    if (rawSections.length === 0) return null;

    const rawPanelText = rawSections.join("\n\n---\n\n");
    return { extracted: {}, rawPanelText };
  }
})();
