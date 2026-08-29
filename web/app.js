const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/png", "image/jpeg"]);

function $(id) {
  return document.getElementById(id);
}

function el(tag, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

function setText(node, value) {
  node.textContent = value == null ? "" : String(value);
}

function setStatus(kind, message) {
  const status = $("status");
  status.className = `status ${kind}`;
  setText(status, message);
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function appendBlock(parent, title, body, className) {
  const card = el("div", className || "card");
  const heading = el("h3");
  setText(heading, title);
  const paragraph = el("p");
  setText(paragraph, body || "—");
  card.append(heading, paragraph);
  parent.append(card);
}

function renderResult(payload) {
  const root = $("result");
  clearNode(root);
  if (!payload || !payload.assessment) {
    return;
  }
  const assessment = payload.assessment;
  const header = el("div", "card");
  const risk = el("p");
  const riskWord = el("span", `risk-${assessment.risk_level || "low"}`);
  setText(riskWord, assessment.risk_level || "—");
  const score = el("span");
  setText(
    score,
    ` ညွှန်းကိန်း ${assessment.risk_score ?? "—"} · ဖြစ်နိုင်ခြေ မဟုတ်`
  );
  risk.append(riskWord, score);
  header.append(risk);
  if (payload.known_blacklist_matches && payload.known_blacklist_matches.length) {
    const chip = el("p", "lime-chip");
    setText(chip, "လူက အတည်ပြုထားသော စာရင်းနှင့် တူ");
    header.append(chip);
  }
  root.append(header);
  appendBlock(root, "မြန်မာ အနှစ်ချုပ်", assessment.myanmar_summary);
  appendBlock(root, "English summary", assessment.english_summary, "card mute-card");
  appendBlock(root, "မသေချာချက်", assessment.uncertainty);

  const evidenceCard = el("div", "card");
  const evidenceTitle = el("h3");
  setText(evidenceTitle, "အထောက်အထား");
  evidenceCard.append(evidenceTitle);
  const list = el("ul", "evidence");
  const items = assessment.evidence || [];
  if (!items.length) {
    const empty = el("li");
    setText(empty, "မရှိပါ");
    list.append(empty);
  } else {
    items.forEach((item) => {
      const li = el("li");
      const quote = el("div", "quote");
      setText(quote, item.quote || "");
      const expl = el("div");
      setText(expl, item.myanmar_explanation || "");
      li.append(quote, expl);
      list.append(li);
    });
  }
  evidenceCard.append(list);
  root.append(evidenceCard);

  const entityCard = el("div", "card");
  const entityTitle = el("h3");
  setText(entityTitle, "Identifiers");
  entityCard.append(entityTitle);
  const chips = el("div", "chip-row");
  (assessment.entities || []).forEach((item) => {
    const chip = el("span", "chip");
    setText(chip, `${item.type} · ${item.exact_value}`);
    chips.append(chip);
  });
  if (!chips.firstChild) {
    const empty = el("p", "empty");
    setText(empty, "မတွေ့ပါ");
    entityCard.append(empty);
  } else {
    entityCard.append(chips);
  }
  root.append(entityCard);

  const actionsCard = el("div", "card");
  const actionsTitle = el("h3");
  setText(actionsTitle, "ဘေးကင်းသော နောက်တစ်ဆင့်");
  actionsCard.append(actionsTitle);
  const actions = el("ul", "evidence");
  (assessment.myanmar_safe_actions || []).forEach((step) => {
    const li = el("li");
    setText(li, step);
    actions.append(li);
  });
  actionsCard.append(actions);
  root.append(actionsCard);
}

async function readError(response) {
  try {
    const body = await response.json();
    return body.error || "request_failed";
  } catch (_err) {
    return "request_failed";
  }
}

let selectedFile = null;
let previewUrl = null;
let inFlight = null;

function setImageError(message) {
  const node = $("image-error");
  node.className = message ? "status bad" : "status idle";
  setText(node, message || "");
}

function clearImage() {
  selectedFile = null;
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }
  $("image-input").value = "";
  $("image-preview").removeAttribute("src");
  $("image-preview-wrap").classList.add("is-hidden");
  $("analyze-image").disabled = true;
  setImageError("");
}

function validateImageFile(file) {
  if (!file) {
    return "image_required";
  }
  const type = file.type === "image/jpg" ? "image/jpeg" : file.type;
  if (!ALLOWED_TYPES.has(type)) {
    return "unsupported_image_type";
  }
  if (file.size > IMAGE_MAX_BYTES) {
    return "image_too_large";
  }
  return "";
}

function acceptImageFile(file) {
  const error = validateImageFile(file);
  if (error) {
    clearImage();
    setImageError(
      error === "image_too_large"
        ? "10 MB ထက် ကြီးသော ဖိုင် မရပါ။"
        : "PNG သို့မဟုတ် JPEG သာ လက်ခံသည်။"
    );
    return;
  }
  selectedFile = file;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  $("image-preview").src = previewUrl;
  setText($("image-meta"), `${file.name} · ${file.type} · ${file.size} bytes`);
  $("image-preview-wrap").classList.remove("is-hidden");
  $("analyze-image").disabled = false;
  setImageError("");
}

function switchTab(panelId) {
  document.querySelectorAll(".tab[data-panel]").forEach((tab) => {
    const on = tab.getAttribute("data-panel") === panelId;
    tab.classList.toggle("is-active", on);
    tab.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    const on = panel.id === panelId;
    panel.hidden = !on;
    panel.classList.toggle("is-hidden", !on);
  });
}

async function analyzeText() {
  const text = $("message").value;
  if (!text.trim()) {
    setStatus("bad", "စာထည့်ပါ။");
    return;
  }
  setStatus("idle", "စစ်ဆေးနေသည်…");
  $("analyze-text").disabled = true;
  try {
    inFlight = fetch("/api/analyze/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const response = await inFlight;
    if (!response.ok) {
      setStatus("bad", `မရပါ (${await readError(response)})`);
      clearNode($("result"));
      return;
    }
    const payload = await response.json();
    renderResult(payload);
    setStatus("ok", "စာသား စစ်ဆေးပြီးပါပြီ။");
  } catch (_err) {
    setStatus("bad", "ချိတ်ဆက်မရပါ။");
  } finally {
    $("analyze-text").disabled = false;
    inFlight = null;
  }
}

async function analyzeImage() {
  const error = validateImageFile(selectedFile);
  if (error) {
    setImageError("စစ်ဆေးရန် မှန်ကန်သော PNG/JPEG ရွေးပါ။");
    return;
  }
  setStatus("idle", "စစ်ဆေးနေသည်…");
  $("analyze-image").disabled = true;
  const body = new FormData();
  body.append("file", selectedFile, selectedFile.name);
  try {
    inFlight = fetch("/api/analyze/image", { method: "POST", body });
    const response = await inFlight;
    if (!response.ok) {
      setStatus("bad", `မရပါ (${await readError(response)})`);
      clearNode($("result"));
      return;
    }
    const payload = await response.json();
    renderResult(payload);
    setStatus("ok", "မျက်နှာပြင်ပုံ စစ်ဆေးပြီးပါပြီ။");
  } catch (_err) {
    setStatus("bad", "ချိတ်ဆက်မရပါ။");
  } finally {
    $("analyze-image").disabled = !selectedFile;
    inFlight = null;
  }
}

function initTabs() {
  document.querySelectorAll(".tab[data-panel]").forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.getAttribute("data-panel")));
  });
}

function initImageUpload() {
  const zone = $("dropzone");
  const input = $("image-input");
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (file) acceptImageFile(file);
  });
  ["dragenter", "dragover"].forEach((name) => {
    zone.addEventListener(name, (event) => {
      event.preventDefault();
      zone.classList.add("is-drag");
    });
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("is-drag"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("is-drag");
    const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    if (file) acceptImageFile(file);
  });
  $("remove-image").addEventListener("click", () => clearImage());
}

function init() {
  initTabs();
  initImageUpload();
  $("analyze-text").addEventListener("click", () => analyzeText());
  $("analyze-image").addEventListener("click", () => analyzeImage());
}

init();
