const DEFAULT_URL = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("backend-url");
  const saveBtn = document.getElementById("save-btn");
  const status = document.getElementById("status");

  chrome.storage.local.get("backendUrl", (result) => {
    input.value = result.backendUrl || DEFAULT_URL;
  });

  saveBtn.addEventListener("click", () => {
    const url = input.value.trim() || DEFAULT_URL;
    chrome.storage.local.set({ backendUrl: url }, () => {
      status.textContent = "Saved!";
      setTimeout(() => { status.textContent = ""; }, 2000);
    });
  });
});
