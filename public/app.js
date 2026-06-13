// --- API key + shared request helpers ---------------------------------------
const API_KEY_STORE = "courseEngineApiKey";

function getApiKey() {
  const field = document.getElementById("api-key");
  return ((field && field.value) || localStorage.getItem(API_KEY_STORE) || "").trim();
}

// Attach the API key header when one is set; pass through any base headers.
function authHeaders(base) {
  const headers = { ...(base || {}) };
  const key = getApiKey();
  if (key) headers["X-API-Key"] = key;
  return headers;
}

// Errors use {error: {code, message}}; tolerate older flat shapes too.
function errorMessage(data) {
  if (data && data.error) return data.error.message || data.error;
  return "Something went wrong.";
}

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

// --- Course materials upload -------------------------------------------------
const materialsForm = document.getElementById("materials-form");
const materialsInput = document.getElementById("project-zip");
const materialsButton = document.getElementById("materials-generate");
const materialsStatus = document.getElementById("materials-status");

function showMaterialsStatus(message, kind) {
  materialsStatus.textContent = message;
  materialsStatus.className = `status ${kind || ""}`;
  materialsStatus.hidden = false;
}

materialsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = materialsInput.files[0];
  if (!file) return;

  materialsButton.disabled = true;
  showMaterialsStatus("Extracting topics and building materials", "loading");

  try {
    const body = new FormData();
    body.append("project", file);
    const response = await fetch("/api/v1/materials", {
      method: "POST",
      headers: authHeaders(),
      body,
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      showMaterialsStatus(errorMessage(data), "error");
      return;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "course-materials.zip";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showMaterialsStatus(
      "Done — course-materials.zip downloaded (PPTX lectures, Word LMS intros and assignments, rubric.csv).",
      ""
    );
  } catch (error) {
    showMaterialsStatus("Network error — is the server running?", "error");
  } finally {
    materialsButton.disabled = false;
  }
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
    const response = await fetch("/api/v1/schedule", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ description, weeks }),
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      showStatus(errorMessage(data), "error");
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

// --- API console -------------------------------------------------------------
const apiKeyField = document.getElementById("api-key");
apiKeyField.value = localStorage.getItem(API_KEY_STORE) || "";
apiKeyField.addEventListener("change", () =>
  localStorage.setItem(API_KEY_STORE, apiKeyField.value.trim())
);

const consoleEndpoint = document.getElementById("console-endpoint");
const consoleBody = document.getElementById("console-body");
const consoleBodyLabel = document.getElementById("console-body-label");
const consoleFileRow = document.getElementById("console-file-row");
const consoleFile = document.getElementById("console-file");
const consoleSend = document.getElementById("console-send");
const consoleOutput = document.getElementById("console-output");
const consoleStatusEl = document.getElementById("console-status");
const consoleTiming = document.getElementById("console-timing");
const consoleCurl = document.getElementById("console-curl");
const consoleResponse = document.getElementById("console-response");

let consoleOps = [];

// Build the endpoint list from the live OpenAPI spec so the console always
// matches the deployed API.
async function loadOpenApi() {
  try {
    const spec = await (await fetch("/api/v1/openapi.json")).json();
    consoleOps = [];
    Object.entries(spec.paths).forEach(([path, methods]) => {
      Object.entries(methods).forEach(([method, op]) => {
        const content = (op.requestBody && op.requestBody.content) || {};
        consoleOps.push({
          method: method.toUpperCase(),
          path,
          json: content["application/json"] || null,
          multipart: Boolean(content["multipart/form-data"]),
        });
      });
    });
    consoleEndpoint.replaceChildren();
    consoleOps.forEach((op, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = `${op.method} ${op.path}`;
      consoleEndpoint.appendChild(option);
    });
    syncConsoleForm();
  } catch (error) {
    consoleEndpoint.replaceChildren(
      new Option("Could not load /api/v1/openapi.json")
    );
  }
}

function currentOp() {
  return consoleOps[Number(consoleEndpoint.value)] || null;
}

function syncConsoleForm() {
  const op = currentOp();
  if (!op) return;
  const wantsJson = op.method === "POST" && op.json;
  consoleBody.hidden = !wantsJson;
  consoleBodyLabel.hidden = !wantsJson;
  consoleFileRow.hidden = !op.multipart;
  if (wantsJson) {
    consoleBody.value = op.json.example
      ? JSON.stringify(op.json.example, null, 2)
      : "{}";
  }
}

consoleEndpoint.addEventListener("change", syncConsoleForm);

function buildCurl(op) {
  const parts = [`curl -X ${op.method} ${window.location.origin}${op.path}`];
  const key = getApiKey();
  if (key) parts.push(`-H "X-API-Key: ${key}"`);
  if (op.method === "POST" && op.json) {
    parts.push(`-H "Content-Type: application/json"`);
    parts.push(`-d '${consoleBody.value.replace(/\s+/g, " ").trim()}'`);
  } else if (op.multipart) {
    parts.push(`-F "project=@your-project.zip"`);
  }
  return parts.join(" \\\n  ");
}

consoleSend.addEventListener("click", async () => {
  const op = currentOp();
  if (!op) return;

  consoleSend.disabled = true;
  consoleOutput.hidden = false;
  consoleStatusEl.textContent = "Sending…";
  consoleStatusEl.className = "";
  consoleTiming.textContent = "";
  consoleResponse.value = "";
  consoleCurl.value = buildCurl(op);

  const init = { method: op.method, headers: authHeaders() };
  if (op.method === "POST" && op.json) {
    init.headers = authHeaders({ "Content-Type": "application/json" });
    init.body = consoleBody.value;
  } else if (op.multipart) {
    const file = consoleFile.files[0];
    if (!file) {
      consoleStatusEl.textContent = "Choose a .zip file first.";
      consoleStatusEl.className = "err";
      consoleSend.disabled = false;
      return;
    }
    const fd = new FormData();
    fd.append("project", file);
    init.body = fd;
  }

  const started = performance.now();
  try {
    const response = await fetch(op.path, init);
    consoleStatusEl.textContent = `HTTP ${response.status} ${response.statusText}`;
    consoleStatusEl.className = response.ok ? "ok" : "err";
    consoleTiming.textContent = `${Math.round(performance.now() - started)} ms`;

    const type = response.headers.get("Content-Type") || "";
    if (type.includes("application/zip")) {
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "course-materials.zip";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      consoleResponse.value = `binary application/zip — ${blob.size.toLocaleString()} bytes (downloaded as course-materials.zip)`;
    } else {
      const text = await response.text();
      try {
        consoleResponse.value = JSON.stringify(JSON.parse(text), null, 2);
      } catch (error) {
        consoleResponse.value = text;
      }
    }
  } catch (error) {
    consoleStatusEl.textContent = "Network error — is the server running?";
    consoleStatusEl.className = "err";
  } finally {
    consoleSend.disabled = false;
  }
});

loadOpenApi();
