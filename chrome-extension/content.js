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

  // --- Extraction Pipeline ---

  const JD_KEYWORDS = [
    "about the job",
    "responsibilities",
    "requirements",
    "qualifications",
    "experience",
    "preferred",
    "your role",
    "what you will do",
    "what you'll do",
    "who you are",
    "about this role",
    "the opportunity",
    "job description",
  ];

  const NOISE_PATTERNS = [
    "this ai feature is in beta",
    "show match details",
    "help me stand out",
    "suggested questions",
    "top job picks",
    "meet the hiring team",
    "people you can reach out to",
    "exclusive job seeker insights",
    "about the company",
    "trending employee content",
    "job tracker",
    "notifications",
    "messaging",
    "my network",
  ];

  const SALARY_REGEX =
    /\$[\d,]+(?:\.\d+)?(?:k|K)?(?:\s*[-–\/]\s*\$[\d,]+(?:\.\d+)?(?:k|K)?)?(?:\s*\/?\s*(?:yr|year|hr|hour|mo|month))?/;

  const LOCATION_REGEX =
    /[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}(?:\s*\d{5})?/;

  const JOB_TYPE_TERMS = ["full-time", "part-time", "contract", "internship"];
  const WORK_MODE_TERMS = ["remote", "hybrid", "on-site", "onsite"];

  function extractJobData() {
    const panel = findJobPanel();
    if (!panel) return null;

    const container = findJobContainer(panel);
    const rawPanelText = panel.innerText;
    const extracted = extractFields(container, panel);

    return { extracted, rawPanelText };
  }

  function findJobPanel() {
    const candidates = document.querySelectorAll("section, div, article");
    let best = null;
    let bestScore = 0;

    for (const node of candidates) {
      const text = node.innerText || "";
      if (text.length < 300) continue;

      const textLower = text.toLowerCase();

      let score = 0;

      const keywordMatches = JD_KEYWORDS.filter((kw) =>
        textLower.includes(kw)
      ).length;
      if (keywordMatches < 2) continue;
      score += keywordMatches * 10;

      score += Math.min(text.length / 100, 30);

      const rect = node.getBoundingClientRect();
      if (rect.top < 2000) {
        score += 10;
      }

      if (node.querySelector("h1, h2, [role='heading']")) {
        score += 5;
      }

      const childCount = node.querySelectorAll("section, article").length;
      if (childCount > 5) {
        score -= childCount * 2;
      }

      if (score > bestScore) {
        bestScore = score;
        best = node;
      }
    }

    return best;
  }

  function findJobContainer(panel) {
    let current = panel.parentElement;
    let container = panel;

    while (current && current !== document.body) {
      const hasHeading = current.querySelector(
        "h1, h2, [role='heading']"
      );
      if (hasHeading) {
        const rect = current.getBoundingClientRect();
        if (rect.height > 5000) break;
        container = current;
        break;
      }
      current = current.parentElement;
    }

    return container;
  }

  function extractFields(container, panel) {
    const fields = {};

    // --- Title ---
    const headings = container.querySelectorAll(
      "h1, h2, [role='heading']"
    );
    for (const h of headings) {
      const text = h.innerText.trim();
      if (
        text.length >= 8 &&
        text.length <= 120 &&
        !/apply|save|share|sign in|join/i.test(text)
      ) {
        const hRect = h.getBoundingClientRect();
        const panelRect = panel.getBoundingClientRect();
        if (hRect.top <= panelRect.top) {
          fields.title = text;
          break;
        }
      }
    }

    // --- Company ---
    if (fields.title) {
      const titleEl = [...headings].find(
        (h) => h.innerText.trim() === fields.title
      );
      if (titleEl) {
        const parent = titleEl.parentElement;
        if (parent) {
          for (const el of parent.children) {
            if (el === titleEl) continue;
            const text = el.innerText.trim();
            if (
              text.length >= 2 &&
              text.length <= 100 &&
              text !== fields.title &&
              !LOCATION_REGEX.test(text) &&
              !SALARY_REGEX.test(text) &&
              !/apply|save|share|sign in|follow/i.test(text) &&
              !JOB_TYPE_TERMS.some((t) => text.toLowerCase() === t) &&
              !WORK_MODE_TERMS.some((t) => text.toLowerCase() === t)
            ) {
              fields.company = text;
              break;
            }
          }
        }
      }
    }

    // --- Description ---
    fields.description = panel.innerText.trim() || null;

    // --- Location ---
    const containerText = container.innerText;
    const locationMatch = containerText.match(LOCATION_REGEX);
    if (locationMatch) {
      fields.location = locationMatch[0];
    }

    // --- Salary ---
    const salaryMatch = containerText.match(SALARY_REGEX);
    if (salaryMatch) {
      fields.salary = salaryMatch[0];
    }

    // --- Job Type ---
    const containerLower = containerText.toLowerCase();
    for (const term of JOB_TYPE_TERMS) {
      if (containerLower.includes(term)) {
        fields.jobType = term.charAt(0).toUpperCase() + term.slice(1);
        break;
      }
    }

    // --- Work Mode ---
    for (const term of WORK_MODE_TERMS) {
      if (containerLower.includes(term)) {
        const raw = term.charAt(0).toUpperCase() + term.slice(1);
        fields.workMode = raw === "Onsite" ? "On-site" : raw;
        break;
      }
    }

    return fields;
  }
})();
