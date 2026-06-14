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
    if (week.kind && week.kind !== "instruction") item.classList.add(`kind-${week.kind}`);

    const number = document.createElement("span");
    number.className = "week-num";
    number.textContent = week.dates ? `Week ${week.week} · ${week.dates}` : `Week ${week.week}`;
    item.appendChild(number);

    const main = document.createElement("span");
    main.className = "week-main";

    const topics = document.createElement("div");
    topics.className = "week-topics";
    week.topics.forEach((topic, index) => {
      if (index > 0) topics.appendChild(document.createTextNode("; "));
      const isExtra = /\((continued)\)$|^Midterm review|^Review and final|^Review$|^Exam$/.test(topic);
      const node = document.createElement(isExtra ? "span" : "strong");
      if (isExtra) node.className = "extra";
      node.textContent = topic;
      topics.appendChild(node);
    });
    main.appendChild(topics);

    if (week.assignment) {
      const assignment = document.createElement("div");
      assignment.className = "week-assignment";
      const label = week.kind === "exam" ? "Assessment" : "Assignment";
      assignment.textContent = `${label}: ${week.assignment}`;
      main.appendChild(assignment);
    }

    item.appendChild(main);
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

// Serialize the rendered schedule to CSV — the shape /api/v1/copilot-prompt
// parses (and the same shape an external caller would send).
function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function scheduleToCsv(data) {
  const header = "Week,Dates,Topics,Assignment";
  const rows = data.weeks.map((week) =>
    [week.week, week.dates || "", (week.topics || []).join("; "), week.assignment || ""]
      .map(csvCell)
      .join(",")
  );
  return [header, ...rows].join("\n");
}

// The Copilot prompt is built by the deterministic /api/v1/copilot-prompt
// endpoint — one source of truth shared with external API callers.
copilotBuildButton.addEventListener("click", async () => {
  if (!lastSchedule) return;
  copilotBuildButton.disabled = true;
  const label = copilotBuildButton.textContent;
  copilotBuildButton.textContent = "Building…";
  try {
    const response = await fetch("/api/v1/copilot-prompt", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        schedule: scheduleToCsv(lastSchedule),
        // subject + description give the endpoint extra language-inference signal.
        fileName: `${lastSchedule.subject || ""} ${lastDescription || ""}`.trim().slice(0, 250),
      }),
    });
    const data = await response.json();
    copilotText.value =
      !response.ok || data.error ? `Error: ${errorMessage(data)}` : data.prompt;
  } catch (error) {
    copilotText.value = "Network error — is the server running?";
  } finally {
    copilotBuildButton.disabled = false;
    copilotBuildButton.textContent = label;
    copilotPanel.hidden = false;
    copilotText.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
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

  // Optional controls — only sent when set, so the request stays minimal.
  const body = { description, weeks };
  const startDate = document.getElementById("start-date").value;
  const tests = Number(document.getElementById("tests").value) || 0;
  const term = document.getElementById("term").value.trim();
  if (startDate) body.startDate = startDate;
  if (tests > 0) body.tests = tests;
  if (term) body.term = term;

  try {
    const response = await fetch("/api/v1/schedule", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
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

// --- Module lecture generator ------------------------------------------------
const lectureForm = document.getElementById("lecture-form");
const lectureTitle = document.getElementById("lecture-title");
const lectureObjectives = document.getElementById("lecture-objectives");
const lectureButton = document.getElementById("lecture-generate");
const lectureStatus = document.getElementById("lecture-status");

function showLectureStatus(message, kind) {
  lectureStatus.textContent = message;
  lectureStatus.className = `status ${kind || ""}`;
  lectureStatus.hidden = false;
}

lectureForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const objectives = lectureObjectives.value.trim();
  if (!objectives) return;

  lectureButton.disabled = true;
  showLectureStatus("Researching sources and building slides", "loading");

  try {
    const response = await fetch("/api/v1/lecture", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ objectives, title: lectureTitle.value.trim() }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      showLectureStatus(errorMessage(data), "error");
      return;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "module-lecture.pptx";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showLectureStatus(
      "Done — module-lecture.pptx downloaded (one explanation + example slides per objective).",
      ""
    );
  } catch (error) {
    showLectureStatus("Network error — is the server running?", "error");
  } finally {
    lectureButton.disabled = false;
  }
});

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
const consoleFields = document.getElementById("console-fields");
const consoleRawLabel = document.getElementById("console-raw-label");
const consoleRaw = document.getElementById("console-raw");

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

// Build one typed input per request-schema property — date pickers for
// `format: date`, number inputs for integers (with min/max), textareas for long
// strings — so every endpoint gets proper controls straight from the OpenAPI doc.
function buildField(name, schema, required, example) {
  const wrap = document.createElement("div");
  wrap.className = "cfield";

  const label = document.createElement("label");
  label.htmlFor = `cf-${name}`;
  label.textContent = name;
  if (required) {
    const star = document.createElement("span");
    star.className = "req";
    star.textContent = " *";
    label.appendChild(star);
  }
  if (schema.description) label.title = schema.description;
  wrap.appendChild(label);

  // Optional fields default empty ("sensible empty defaults"); required ones
  // prefill from the example so the default call works.
  const prefill = required && example != null ? example : "";
  const numeric = schema.type === "integer" || schema.type === "number";
  let input;
  if (numeric) {
    input = document.createElement("input");
    input.type = "number";
    if (schema.minimum != null) input.min = schema.minimum;
    if (schema.maximum != null) input.max = schema.maximum;
    if (prefill !== "") input.value = prefill;
  } else if (schema.format === "date") {
    input = document.createElement("input");
    input.type = "date";
    if (prefill) input.value = prefill;
  } else if (typeof prefill === "string" && prefill.length > 60) {
    input = document.createElement("textarea");
    input.rows = 4;
    input.value = prefill;
  } else {
    input = document.createElement("input");
    input.type = "text";
    if (prefill) input.value = prefill;
  }
  input.id = `cf-${name}`;
  input.dataset.field = name;
  input.dataset.numeric = numeric ? "1" : "";
  if (schema.description) input.placeholder = schema.description.slice(0, 64);
  wrap.appendChild(input);
  return wrap;
}

function renderConsoleFields(op) {
  consoleFields.replaceChildren();
  const schema = op.json && op.json.schema;
  if (!(op.method === "POST" && schema)) return;
  const required = new Set(schema.required || []);
  const example = op.json.example || {};
  // Required fields first (the API serializes properties alphabetically).
  const entries = Object.entries(schema.properties || {}).sort(
    ([a], [b]) => Number(required.has(b)) - Number(required.has(a))
  );
  entries.forEach(([name, propSchema]) => {
    if (propSchema.format === "binary") return; // file fields use the upload control
    consoleFields.appendChild(buildField(name, propSchema, required.has(name), example[name]));
  });
}

function bodyFromFields() {
  const body = {};
  consoleFields.querySelectorAll("[data-field]").forEach((input) => {
    const value = input.value.trim();
    if (value === "") return; // omit empties: keeps optionals out, lets the API validate required
    body[input.dataset.field] = input.dataset.numeric ? Number(value) : value;
  });
  return body;
}

// The body that will actually be sent — the raw textarea when in raw mode,
// otherwise the typed fields serialized to JSON.
function consoleBodyJson() {
  return consoleRaw.checked ? consoleBody.value : JSON.stringify(bodyFromFields(), null, 2);
}

function applyRawMode(wantsJson) {
  const raw = wantsJson && consoleRaw.checked;
  consoleFields.hidden = !wantsJson || raw;
  consoleBody.hidden = !raw;
  consoleBodyLabel.hidden = !raw;
  if (raw) consoleBody.value = JSON.stringify(bodyFromFields(), null, 2); // seed from fields
}

function syncConsoleForm() {
  const op = currentOp();
  if (!op) return;
  const wantsJson = op.method === "POST" && Boolean(op.json);
  renderConsoleFields(op);
  consoleRawLabel.hidden = !wantsJson;
  consoleFileRow.hidden = !op.multipart;
  applyRawMode(wantsJson);
}

consoleEndpoint.addEventListener("change", syncConsoleForm);
consoleRaw.addEventListener("change", () => {
  const op = currentOp();
  if (op) applyRawMode(op.method === "POST" && Boolean(op.json));
});

function buildCurl(op) {
  const parts = [`curl -X ${op.method} ${window.location.origin}${op.path}`];
  const key = getApiKey();
  if (key) parts.push(`-H "X-API-Key: ${key}"`);
  if (op.method === "POST" && op.json) {
    parts.push(`-H "Content-Type: application/json"`);
    parts.push(`-d '${consoleBodyJson().replace(/\s+/g, " ").trim()}'`);
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
    init.body = consoleBodyJson();
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
    const disposition = response.headers.get("Content-Disposition") || "";
    const isBinary =
      /zip|presentation|officedocument|octet-stream/.test(type) || /attachment/.test(disposition);
    if (isBinary) {
      const blob = await response.blob();
      const match = /filename="?([^"]+)"?/.exec(disposition);
      const filename = match ? match[1] : "download";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      consoleResponse.value = `binary ${type || "file"} — ${blob.size.toLocaleString()} bytes (downloaded as ${filename})`;
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

// --- Generated artifacts -----------------------------------------------------
const artifactsRefresh = document.getElementById("artifacts-refresh");
const artifactsStatus = document.getElementById("artifacts-status");
const artifactList = document.getElementById("artifact-list");

function showArtifactsStatus(message, kind) {
  artifactsStatus.textContent = message;
  artifactsStatus.className = `status ${kind || ""}`;
  artifactsStatus.hidden = !message;
}

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderArtifacts(items) {
  artifactList.innerHTML = "";
  for (const item of items) {
    const li = document.createElement("li");
    li.className = "artifact-item";

    const link = document.createElement("a");
    link.href = item.downloadUrl || item.url;
    link.textContent = item.name;
    link.target = "_blank";
    link.rel = "noopener";
    li.appendChild(link);

    const meta = document.createElement("div");
    meta.className = "artifact-meta";
    const md = item.metadata || {};
    const label = md.title || md.filename || md.kind || "";
    const when = item.uploadedAt ? new Date(item.uploadedAt).toLocaleString() : "";
    meta.textContent = [label, formatBytes(item.size), when].filter(Boolean).join(" · ");
    li.appendChild(meta);

    artifactList.appendChild(li);
  }
}

async function loadArtifacts() {
  showArtifactsStatus("Loading artifacts", "loading");
  try {
    const response = await fetch("/api/v1/artifacts", { headers: authHeaders() });
    if (response.status === 401) {
      renderArtifacts([]);
      showArtifactsStatus("Enter your API key above, then Refresh.", "");
      return;
    }
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      showArtifactsStatus(errorMessage(data) || `Request failed (${response.status})`, "error");
      return;
    }
    const data = await response.json();
    renderArtifacts(data.artifacts || []);
    if (!data.enabled) {
      showArtifactsStatus("Artifact storage isn't enabled on this deployment.", "");
    } else if (!(data.artifacts || []).length) {
      showArtifactsStatus("No artifacts generated yet.", "");
    } else {
      showArtifactsStatus("", "");
    }
  } catch (error) {
    showArtifactsStatus("Network error — is the server running?", "error");
  }
}

artifactsRefresh.addEventListener("click", loadArtifacts);
loadArtifacts();
