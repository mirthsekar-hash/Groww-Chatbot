/**
 * Phase 3 — chat client (vanilla JS).
 * XSS-safe: user text is set via textContent only.
 */

(function () {
  const MAX_CHARS = 500;
  const TIMEOUT_MS = 120000;

  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const messagesEl = document.getElementById("messages");
  const charCount = document.getElementById("char-count");
  const chips = document.querySelectorAll(".chip");
  const welcomeEl = document.getElementById("welcome");

  function hideWelcome() {
    if (welcomeEl) welcomeEl.hidden = true;
  }

  function updateCharCount() {
    const n = input.value.length;
    charCount.textContent = `${n} / ${MAX_CHARS}`;
  }

  input.addEventListener("input", updateCharCount);
  updateCharCount();

  function setBusy(busy) {
    sendBtn.disabled = busy;
    input.disabled = busy;
    chips.forEach((c) => {
      c.disabled = busy;
    });
    if (!busy) input.focus();
  }

  function appendMessage(role, text, extraClass) {
    const div = document.createElement("div");
    div.className = `msg msg-${role}${extraClass ? ` ${extraClass}` : ""}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed) return;

    hideWelcome();
    appendMessage("user", trimmed);

    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), TIMEOUT_MS);

    setBusy(true);
    appendMessage("system", "Thinking…");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed.slice(0, MAX_CHARS) }),
        signal: controller.signal,
      });

      messagesEl.removeChild(messagesEl.lastChild);

      if (!res.ok) {
        const errText =
          res.status === 503
            ? "The assistant is temporarily unavailable. Try again shortly."
            : `Something went wrong (${res.status}).`;
        appendMessage("assistant", errText, "msg-error");
        return;
      }

      const data = await res.json();
      const reply = typeof data.reply === "string" ? data.reply : "";
      appendMessage("assistant", reply || "(Empty response)");
    } catch (e) {
      if (messagesEl.lastChild && messagesEl.lastChild.textContent === "Thinking…") {
        messagesEl.removeChild(messagesEl.lastChild);
      }
      const msg =
        e.name === "AbortError"
          ? "That took too long. Please try again."
          : "Network error. Check your connection and try again.";
      appendMessage("assistant", msg, "msg-error");
    } finally {
      clearTimeout(tid);
      setBusy(false);
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.slice(0, MAX_CHARS);
    input.value = "";
    updateCharCount();
    sendMessage(text);
  });

  chips.forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-query") || "";
      if (input.disabled) return;
      input.value = q.slice(0, MAX_CHARS);
      updateCharCount();
      sendMessage(q);
    });
  });
})();
