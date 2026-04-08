/* LEGACY / ALTERNATE FRONTEND
   This script powers the minimal static chat UI (expects `#input`, `#send`, `#messages`).
   The live operator workspace served at `/` uses `app.js` + `workspace_modules.js` + `workspace-client/*` from `services/index.html` (see `app.py`). */
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const messages = document.getElementById("messages");
const inputWrap = document.querySelector(".input-wrap");

if (inputWrap && input && !inputWrap.querySelector(".input-shell")) {
  const shell = document.createElement("div");
  shell.className = "input-shell";
  inputWrap.insertBefore(shell, input);
  shell.appendChild(input);
  if (sendBtn) shell.appendChild(sendBtn);
}

function addMessage(text, cls) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.innerText = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function addTyping() {
  const div = document.createElement("div");
  div.className = "msg bot";
  div.innerText = "Thinking…";
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";
  sendBtn.disabled = true;

  const typing = addTyping();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });

    if (!res.ok) {
      throw new Error("Request failed");
    }

    const data = await res.json();
    typing.remove();
    typeResponse(data.reply || "I couldn't generate a reply.");
  } catch (error) {
    typing.remove();
    addMessage("Something went wrong. Please try again.", "bot");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function typeResponse(text) {
  const div = document.createElement("div");
  div.className = "msg bot";
  messages.appendChild(div);

  let i = 0;
  function type() {
    if (i < text.length) {
      div.innerText += text[i];
      i++;
      messages.scrollTop = messages.scrollHeight;
      setTimeout(type, 10);
    }
  }
  type();
}

sendBtn.onclick = sendMessage;

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
