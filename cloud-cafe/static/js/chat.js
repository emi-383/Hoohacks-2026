// chat.js — Mochi chatbot
// Handles sending messages to /api/chat and rendering replies.
// Works alongside index.html's toggleChat() and onBotMessage().

let chatHistory = []; // full conversation kept in memory for Gemini context

// ── Send a message ─────────────────────────────────────────────
async function sendMessage() {
  const input   = document.getElementById("user-input");
  const message = input.value.trim();
  if (!message) return;

  appendMessage("user", message);
  input.value = "";

  // show typing indicator while waiting for reply
  const typing = showTyping();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message,
        history: chatHistory
      })
    });

    const data = await response.json();

    // remove typing indicator then show reply
    typing.remove();
    appendMessage("bot", data.reply);

    // update conversation history for next message
    // Gemini expects role: "user"/"model" with parts array
    chatHistory.push({ role: "user",  parts: [message] });
    chatHistory.push({ role: "model", parts: [data.reply] });

    // tell index.html to update the bubble preview
    if (typeof onBotMessage === "function") {
      onBotMessage(data.reply);
    }

  } catch (err) {
    typing.remove();
    appendMessage("bot", "i seem to be a little lost right now, try again in a moment");
  }
}

// ── Append a message bubble to the chat window ────────────────
function appendMessage(sender, text) {
  const chatWindow = document.getElementById("chat-window");
  const div        = document.createElement("div");
  div.className    = `message ${sender}`;
  div.innerText    = text;
  chatWindow.appendChild(div);
  // scroll to bottom
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

// ── Show typing indicator ─────────────────────────────────────
// Three bouncing dots while waiting for Gemini response.
// Returns the element so caller can remove it when reply arrives.
function showTyping() {
  const chatWindow = document.getElementById("chat-window");
  const div        = document.createElement("div");
  div.className    = "typing";
  div.innerHTML    = "<span></span><span></span><span></span>";
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return div;
}

// ── Enter key handler ─────────────────────────────────────────
function handleKeyPress(e) {
  if (e.key === "Enter") sendMessage();
}