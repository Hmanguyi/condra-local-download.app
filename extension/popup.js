const messageInput = document.getElementById("message");
const responseBox = document.getElementById("response");
const sendButton = document.getElementById("send");

sendButton.addEventListener("click", async () => {
  const message = messageInput.value.trim();
  if (!message) {
    return;
  }

  responseBox.textContent = "Thinking...";
  chrome.runtime.sendMessage({ type: "OPENAI_CHAT", message }, (response) => {
    if (!response || !response.ok) {
      responseBox.textContent = response?.error || "Could not reach the companion app.";
      return;
    }

    responseBox.textContent = response.reply;
  });
});
