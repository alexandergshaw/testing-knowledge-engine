const form = document.getElementById("schedule-form");
const copilotBuildButton = document.getElementById("copilot-build");
const copilotPanel = document.getElementById("copilot-panel");
const copilotText = document.getElementById("copilot-text");
const copilotCopyButton = document.getElementById("copilot-copy");

let lastSchedule = null;
let lastDescription = "";
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

// Stitch the schedule into a Copilot prompt that scaffolds a week-by-week
// student project repository. Plain templating — no AI on this side.
function buildCopilotPrompt(data, description) {
  const scheduleLines = data.weeks
    .map((week) => `- Week ${week.week}: ${week.topics.join("; ")}`)
    .join("\n");

  const reviewNote = data.weeks.some((week) =>
    week.topics.some((topic) => /^(Midterm review|Review and final)/.test(topic))
  )
    ? "- Review/assessment weeks become checkpoint milestones: students integrate prior weeks' work and complete a short self-assessment quiz instead of starting new material.\n"
    : "";

  return `Create a complete week-by-week educational project repository for a college course on ${data.subject}.

## Course description
${description}

## Weekly topic schedule (${data.weeks.length} weeks)
${scheduleLines}

## What to generate
- One folder per week named like \`week-01-<topic-slug>\`, each containing:
  - \`README.md\` with the week's learning objectives, a plain-English explanation of the topic(s), and step-by-step exercises that build on previous weeks
  - Starter code with clearly marked \`TODO\` sections for students to complete
  - Automated tests students can run to verify their work before moving on
- A top-level \`README.md\` with the course overview, the full schedule as a table, environment setup instructions, and grading/checkpoint guidance
- One capstone project thread that evolves across the term: each week's exercises add a feature to the same application, so by the final week students have built one complete project that exercises every topic above
${reviewNote}- Choose the most appropriate language and tooling for ${data.subject}, keep dependencies minimal, and make everything runnable with one setup command
- Write for students seeing these topics for the first time: explain why each topic matters before showing how, and keep each week's workload roughly equal

Generate the full directory structure and file contents.`;
}

copilotBuildButton.addEventListener("click", () => {
  if (!lastSchedule) return;
  copilotText.value = buildCopilotPrompt(lastSchedule, lastDescription);
  copilotPanel.hidden = false;
  copilotText.scrollIntoView({ behavior: "smooth", block: "nearest" });
});

copilotCopyButton.addEventListener("click", async () => {
  copilotText.select();
  try {
    await navigator.clipboard.writeText(copilotText.value);
  } catch (error) {
    document.execCommand("copy"); // fallback for non-secure contexts
  }
  copilotCopyButton.textContent = "Copied!";
  setTimeout(() => {
    copilotCopyButton.textContent = "Copy";
  }, 1500);
});

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
      lastSchedule = data;
      lastDescription = description;
      copilotPanel.hidden = true;
      renderSchedule(data);
    }
  } catch (error) {
    showStatus("Network error — is the server running?", "error");
  } finally {
    generateButton.disabled = false;
  }
});

descriptionInput.focus();
