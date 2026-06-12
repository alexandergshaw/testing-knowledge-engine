const form = document.getElementById("schedule-form");
const descriptionInput = document.getElementById("description");
const weeksInput = document.getElementById("weeks");
const generateButton = document.getElementById("generate");
const resultSection = document.getElementById("result");
const subjectHeading = document.getElementById("result-subject");
const confidenceBadge = document.getElementById("result-confidence");
const weekList = document.getElementById("week-list");
const citationsBox = document.getElementById("citations");
const status = document.getElementById("status");

function showStatus(message, kind) {
  status.textContent = message;
  status.className = `status ${kind || ""}`;
  status.hidden = false;
}

function hideStatus() {
  status.hidden = true;
}

function renderSchedule(data) {
  subjectHeading.textContent = `${data.subject} — weekly schedule`;
  confidenceBadge.textContent = `confidence: ${data.confidence}`;
  confidenceBadge.className = `confidence ${data.confidence}`;

  weekList.replaceChildren();
  data.weeks.forEach((week) => {
    const item = document.createElement("li");

    const number = document.createElement("span");
    number.className = "week-num";
    number.textContent = `Week ${week.week}`;
    item.appendChild(number);

    const topics = document.createElement("span");
    topics.className = "week-topics";
    week.topics.forEach((topic, index) => {
      if (index > 0) topics.appendChild(document.createTextNode("; "));
      const isExtra = /\((continued)\)$|^Midterm review|^Review and final/.test(topic);
      const node = document.createElement(isExtra ? "span" : "strong");
      if (isExtra) node.className = "extra";
      node.textContent = topic;
      topics.appendChild(node);
    });
    item.appendChild(topics);
    weekList.appendChild(item);
  });

  citationsBox.replaceChildren();
  if (data.citations.length) {
    const heading = document.createElement("strong");
    heading.textContent = "Built from:";
    citationsBox.appendChild(heading);
    data.citations.forEach((citation) => {
      const row = document.createElement("div");
      const link = document.createElement("a");
      link.href = citation.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = citation.title;
      row.appendChild(link);
      const source = document.createElement("span");
      source.className = "src";
      source.textContent = ` — ${citation.source}`;
      row.appendChild(source);
      citationsBox.appendChild(row);
    });
  }

  resultSection.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const description = descriptionInput.value.trim();
  const weeks = Number(weeksInput.value);
  if (!description) return;

  generateButton.disabled = true;
  resultSection.hidden = true;
  showStatus("Researching published curricula", "loading");

  try {
    const response = await fetch("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description, weeks }),
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      showStatus(data.error || "Something went wrong.", "error");
    } else {
      hideStatus();
      renderSchedule(data);
    }
  } catch (error) {
    showStatus("Network error — is the server running?", "error");
  } finally {
    generateButton.disabled = false;
  }
});

descriptionInput.focus();
