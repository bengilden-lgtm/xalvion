const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const messages = document.getElementById("messages");

function addMessage(text, cls) {
    const div = document.createElement("div");
    div.className = "msg " + cls;
    div.innerText = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";

    const typing = document.createElement("div");
    typing.className = "msg bot";
    typing.innerText = "…";
    messages.appendChild(typing);

    const res = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message: text})
    });

    const data = await res.json();
    typing.remove();

    typeResponse(data.reply);
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
            setTimeout(type, 12);
        }
    }
    type();
}

sendBtn.onclick = sendMessage;

input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
});