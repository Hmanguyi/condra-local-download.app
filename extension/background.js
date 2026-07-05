const BRIDGE_URL = "http://127.0.0.1:8765/chat";

async function sendToCompanionApp(message, options = {}) {
  const response = await fetch(BRIDGE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      reset: Boolean(options.reset),
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "The local companion app returned an error.");
  }

  return payload.reply;
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type !== "OPENAI_CHAT") {
    return false;
  }

  sendToCompanionApp(request.message, { reset: request.reset })
    .then((reply) => sendResponse({ ok: true, reply }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));

  return true;
});
