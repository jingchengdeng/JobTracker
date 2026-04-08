chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type !== "SAVE_EXTRACTION") return;

  const { backendUrl, payload } = msg;

  fetch(`${backendUrl}/api/extension/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((res) => {
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      return res.json();
    })
    .then((data) => sendResponse({ success: true, data }))
    .catch((err) => sendResponse({ success: false, error: err.message }));

  return true; // keep message channel open for async sendResponse
});
