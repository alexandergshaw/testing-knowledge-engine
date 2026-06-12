const chat = document.getElementById("chat");
const form = document.getElementById("ask-form");
const input = document.getElementById("question");
const sendButton = document.getElementById("send");

function addMessage(className, node) {
  const message = document.createElement("div");
  message.className = `message ${className}`;
  if (typeof node === "string") {
    message.textContent = node;
  } else {
    message.appendChild(node);
  }
  chat.appendChild(message);
  chat.scrollTop = chat.scrollHeight;
  return message;
}

// Render answer text, converting [n] markers into superscript citation links.
function renderAnswer(data) {
  const container = document.createDocumentFragment();

  data.answer.split("\n\n").forEach((paragraphText) => {
    const paragraph = document.createElement("p");
    const parts = paragraphText.split(/(\[\d+\])/g);
    parts.forEach((part) => {
      const marker = part.match(/^\[(\d+)\]$/);
      const citation = marker && data.citations[Number(marker[1]) - 1];
      if (citation) {
        const sup = document.createElement("sup");
        const link = document.createElement("a");
        link.href = citation.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.title = `${citation.title} — ${citation.source}`;
        link.textContent = `[${marker[1]}]`;
        sup.appendChild(link);
        paragraph.appendChild(sup);
      } else if (part) {
        paragraph.appendChild(document.createTextNode(part));
      }
    });
    container.appendChild(paragraph);
  });

  if (data.citations.length) {
    const citations = document.createElement("div");
    citations.className = "citations";
    data.citations.forEach((citation, index) => {
      const row = document.createElement("div");
      const link = document.createElement("a");
      link.href = citation.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = `[${index + 1}] ${citation.title}`;
      row.appendChild(link);
      const source = document.createElement("span");
      source.className = "src";
      source.textContent = ` — ${citation.source}`;
      row.appendChild(source);
      citations.appendChild(row);
    });
    container.appendChild(citations);
  }

  if (data.confidence && data.confidence !== "none") {
    const badge = document.createElement("span");
    badge.className = `confidence ${data.confidence}`;
    badge.textContent = `confidence: ${data.confidence}`;
    container.appendChild(badge);
  }

  return container;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  addMessage("question", question);
  input.value = "";
  sendButton.disabled = true;
  const loading = addMessage("answer loading", "Researching sources");

  try {
    const response = await fetch(`/api/ask?q=${encodeURIComponent(question)}`);
    const data = await response.json();
    loading.remove();
    if (!response.ok || data.error) {
      addMessage("answer", data.error || "Something went wrong.");
    } else {
      addMessage("answer", renderAnswer(data));
    }
  } catch (error) {
    loading.remove();
    addMessage("answer", "Network error — is the server running?");
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
});

input.focus();
