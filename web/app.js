const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const AUDIO_MAX_BYTES = 25 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/png", "image/jpeg"]);
const ALLOWED_AUDIO_TYPES = new Set([
  "audio/wav",
  "audio/wave",
  "audio/x-wav",
  "audio/mpeg",
  "audio/mp3",
  "audio/mp4",
  "audio/m4a",
  "audio/x-m4a",
  "audio/ogg",
  "audio/flac",
  "audio/webm",
  "video/webm",
]);

const OTP_SAMPLE =
  "မင်္ဂလာပါ KBZ ဘဏ်မှ ဖြစ်ပါတယ်။ အကောင့်ပိတ်ပါမည်။ 09-123456789 သို့ ငွေလွှဲပြီး OTP ပို့ပေးပါ။ https://kbz-secure-login.example/otp";
const JOB_SAMPLE = "အလုပ်အင်တာဗျူး အတွက် ဒီလင့်ခ်ကနေ မှတ်ပုံတင်ပါ။ OTP ပို့ပေးရန် လိုသည်။";
const LUNCH_SAMPLE = "မနက်ဖြန် ညနေ ၅ နာရီမှာ ထမင်းစားကြမယ်။ ကောင်းသောနေ့ဖြစ်ပါစေ။";

const RISK_WORDS = {
  low: "နိမ့်",
  medium: "အလယ်အလတ်",
  high: "မြင့်",
  critical: "အလွန်မြင့်",
};

const ERROR_COPY = {
  text_required: "စာထည့်ရန် လိုပါသည်။",
  text_too_long: "စာရှည်လွန်းပါသည်။",
  rate_limited: "ခဏစောင့်ပြီး ပြန်ကြိုးစားပါ။",
  provider_error: "စစ်ဆေးမှု မပြီးပါ။ ပြန်ကြိုးစားပါ။",
  provider_unavailable: "စစ်ဆေးမှု ယခု မရနိုင်ပါ။",
  invalid_request: "ပေးပို့ချက် မမှန်ပါ။",
  image_required: "စစ်ဆေးရန် PNG သို့မဟုတ် JPEG ရွေးပါ။",
  image_too_large: "ပုံသည် 10 MB ထက် ကြီးနေသည်။",
  unsupported_image_type: "PNG သို့မဟုတ် JPEG သာ လက်ခံသည်။",
  audio_required: "စစ်ဆေးရန် အသံဖိုင် ရွေးပါ။",
  audio_too_large: "အသံဖိုင်သည် 25 MB ထက် ကြီးနေသည်။",
  unsupported_audio_type: "ဤအသံအမျိုးအစားကို လက်မခံပါ။",
  conversion_failed: "အသံဖိုင် ပြောင်းမရပါ။",
  conversion_unavailable: "အသံပြောင်းရန် FFmpeg မရှိပါ။",
  analysis_not_found: "စစ်ဆေးချက် မတွေ့ပါ။ ပြန်စစ်ဆေးပါ။",
  unauthorized: "ခွင့်ပြုချက် မရှိပါ။",
  internal_error: "အတွင်းပိုင်း အမှား ဖြစ်ပါသည်။",
  request_failed: "တောင်းဆိုမှု မအောင်မြင်ပါ။",
  value_required: "တန်ဖိုး ထည့်ပါ။",
};

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

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function setStatus(kind, message) {
  const status = $("status");
  status.className = `status ${kind}`;
  setText(status, message);
}

function errorCopy(code) {
  return ERROR_COPY[code] || ERROR_COPY.request_failed;
}

async function readError(response) {
  try {
    const body = await response.json();
    return body.error || "request_failed";
  } catch (_err) {
    return "request_failed";
  }
}

let currentPanel = "panel-text";
let currentAnalysisId = null;
let abortController = null;
let selectedFile = null;
let previewUrl = null;
let selectedAudio = null;
let audioPreviewUrl = null;
let mediaRecorder = null;
let recordedChunks = [];
let inFlight = null;

function currentModePanel() {
  return currentPanel;
}

function failWithoutInput(code, inlineSetter) {
  setStatus("bad", errorCopy(code));
  if (inlineSetter) inlineSetter(errorCopy(code));
  renderError(code);
}

function analyzeEnabled() {
  if (abortController) return false;
  if (currentPanel === "panel-text") return Boolean($("message").value.trim());
  if (currentPanel === "panel-image") return Boolean(selectedFile);
  if (currentPanel === "panel-audio") return Boolean(selectedAudio);
  return false;
}

function syncAnalyzeButton() {
  $("analyze").disabled = !analyzeEnabled();
}

function showReportForm(visible) {
  $("report-form").classList.toggle("is-hidden", !visible);
  if (!visible) {
    $("report-note").value = "";
    $("report-confirm").checked = false;
    $("submit-report").disabled = true;
    setText($("report-status"), "");
    $("report-status").className = "status idle";
  }
}

function renderEmpty() {
  const root = $("result");
  clearNode(root);
  currentAnalysisId = null;
  showReportForm(false);
  const card = el("div", "card empty-state");
  const title = el("h2");
  setText(title, "စစ်ဆေးရန် စာတစ်စောင် ရွေးပါ");
  const body = el("p");
  setText(body, "ရလဒ်သည် ဤနေရာတွင် ပေါ်ပါမည်။ အောက်ပါ ဥပမာများကို နှိပ်၍ စမ်းနိုင်သည်။");
  const chips = el("div", "chip-row");
  [
    ["OTP SMS", OTP_SAMPLE],
    ["အလုပ် ချတ်", JOB_SAMPLE],
    ["ထမင်းစား", LUNCH_SAMPLE],
  ].forEach(([label, sample]) => {
    const chip = el("button", "chip example");
    chip.type = "button";
    setText(chip, label);
    chip.addEventListener("click", () => {
      switchTab("panel-text");
      $("message").value = sample;
      syncAnalyzeButton();
      $("message").focus();
    });
    chips.append(chip);
  });
  card.append(title, body, chips);
  root.append(card);
}

function renderLoading() {
  const root = $("result");
  clearNode(root);
  showReportForm(false);
  const card = el("div", "card loading-card");
  const title = el("h2");
  setText(title, "စစ်ဆေးနေသည်…");
  const bar = el("div", "progress");
  const fill = el("span", "progress-fill");
  bar.append(fill);
  card.append(title, bar);
  root.append(card);
}

function renderError(code) {
  const root = $("result");
  clearNode(root);
  showReportForm(false);
  const card = el("div", "card");
  const title = el("h2");
  setText(title, "မရပါ");
  const body = el("p");
  setText(body, errorCopy(code));
  const retry = el("button", "btn-primary");
  retry.type = "button";
  setText(retry, "ပြန်ကြိုးစားရန်");
  retry.addEventListener("click", () => startAnalyze());
  card.append(title, body, retry);
  root.append(card);
}

function canShowScore(assessment) {
  const evidence = assessment && assessment.evidence ? assessment.evidence : [];
  const uncertainty = assessment && String(assessment.uncertainty || "").trim();
  return evidence.length > 0 && Boolean(uncertainty);
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
    renderEmpty();
    return;
  }
  const assessment = payload.assessment;
  currentAnalysisId = payload.analysis_id;
  showReportForm(true);

  const header = el("div", "card status-strip");
  const riskRow = el("p");
  const level = assessment.risk_level || "low";
  const riskWord = el("span", `risk-${level}`);
  setText(riskWord, `${RISK_WORDS[level] || level} (${level})`);
  riskRow.append(riskWord);
  header.append(riskRow);
  if (canShowScore(assessment)) {
    const score = el("p", "score-line");
    setText(score, `ညွှန်းကိန်း ${assessment.risk_score} — ဖြစ်နိုင်ခြေ မဟုတ်`);
    header.append(score);
  } else {
    const withheld = el("p", "meta");
    setText(withheld, "ညွှန်းကိန်းကို အထောက်အထားနှင့် မသေချာချက် မပြည့်မချင်း မပြပါ။");
    header.append(withheld);
  }
  if (payload.known_blacklist_matches && payload.known_blacklist_matches.length) {
    payload.known_blacklist_matches.forEach((hit) => {
      const chip = el("p", "lime-chip");
      setText(
        chip,
        `လူက အတည်ပြုထားသော စာရင်းနှင့် တူ · ${hit.entity_type} · ${hit.masked_display_value || ""}`
      );
      header.append(chip);
    });
  }
  root.append(header);

  if (payload.source_type === "voice" || payload.transcript) {
    appendBlock(root, "စာသားမှတ်တမ်း", payload.transcript || assessment.extracted_text);
  }
  appendBlock(root, "မြန်မာ အနှစ်ချုပ်", assessment.myanmar_summary);
  appendBlock(root, "English summary", assessment.english_summary, "card mute-card");
  appendBlock(root, "မသေချာချက်", assessment.uncertainty || "—");

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
  setText(entityTitle, "ထုတ်ယူထားသော identifiers");
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
  (assessment.myanmar_safe_actions || []).forEach((step) => {
    const action = el("div", "safe-action");
    const mark = el("span", "safe-mark");
    setText(mark, "•");
    const text = el("p");
    setText(text, step);
    action.append(mark, text);
    actionsCard.append(action);
  });
  root.append(actionsCard);
}

function setBusy(busy) {
  $("analyze").hidden = busy;
  $("cancel-analyze").hidden = !busy;
  $("message").disabled = busy;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.disabled = busy;
  });
  if (!busy) syncAnalyzeButton();
}

function cancelAnalyze() {
  if (abortController) abortController.abort();
}

async function startAnalyze() {
  if (currentPanel === "panel-text") return analyzeText();
  if (currentPanel === "panel-image") return analyzeImage();
  if (currentPanel === "panel-audio") return analyzeAudio();
}

async function analyzeText() {
  const text = $("message").value;
  if (!text.trim()) {
    setStatus("bad", errorCopy("text_required"));
    renderError("text_required");
    return;
  }
  abortController = new AbortController();
  setBusy(true);
  setStatus("idle", "စစ်ဆေးနေသည်…");
  renderLoading();
  try {
    inFlight = fetch("/api/analyze/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: abortController.signal,
    });
    const response = await inFlight;
    if (!response.ok) {
      const code = await readError(response);
      setStatus("bad", errorCopy(code));
      renderError(code);
      return;
    }
    const payload = await response.json();
    if (!payload || !payload.assessment) {
      setStatus("bad", errorCopy("request_failed"));
      renderError("request_failed");
      return;
    }
    renderResult(payload);
    setStatus("ok", "စာသား စစ်ဆေးပြီးပါပြီ။");
  } catch (err) {
    if (err && err.name === "AbortError") {
      setStatus("idle", "ပယ်ဖျက်ပြီး။");
      renderEmpty();
      return;
    }
    setStatus("bad", errorCopy("request_failed"));
    renderError("request_failed");
  } finally {
    abortController = null;
    inFlight = null;
    setBusy(false);
  }
}

function switchTab(panelId) {
  currentPanel = panelId;
  document.querySelectorAll(".tab[data-panel]").forEach((tab) => {
    const on = tab.getAttribute("data-panel") === panelId;
    tab.classList.toggle("is-active", on);
    tab.setAttribute("aria-selected", on ? "true" : "false");
    tab.tabIndex = on ? 0 : -1;
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    const on = panel.id === panelId;
    panel.hidden = !on;
    panel.classList.toggle("is-hidden", !on);
  });
  syncAnalyzeButton();
}

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
  setImageError("");
  syncAnalyzeButton();
}

function validateImageFile(file) {
  if (!file) return "image_required";
  const type = file.type === "image/jpg" ? "image/jpeg" : file.type;
  if (!ALLOWED_TYPES.has(type)) return "unsupported_image_type";
  if (file.size > IMAGE_MAX_BYTES) return "image_too_large";
  return "";
}

function acceptImageFile(file) {
  const error = validateImageFile(file);
  if (error) {
    clearImage();
    setImageError(errorCopy(error));
    return;
  }
  selectedFile = file;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  $("image-preview").src = previewUrl;
  setText($("image-meta"), `${file.name} · ${file.type} · ${file.size} bytes`);
  $("image-preview-wrap").classList.remove("is-hidden");
  setImageError("");
  syncAnalyzeButton();
}

async function analyzeImage() {
  const error = validateImageFile(selectedFile);
  if (error) {
    failWithoutInput(error, setImageError);
    return;
  }
  abortController = new AbortController();
  setBusy(true);
  setStatus("idle", "စစ်ဆေးနေသည်…");
  renderLoading();
  const body = new FormData();
  body.append("file", selectedFile, selectedFile.name);
  try {
    inFlight = fetch("/api/analyze/image", {
      method: "POST",
      body,
      signal: abortController.signal,
    });
    const response = await inFlight;
    if (!response.ok) {
      const code = await readError(response);
      setStatus("bad", errorCopy(code));
      renderError(code);
      return;
    }
    const payload = await response.json();
    if (!payload || !payload.assessment) {
      setStatus("bad", errorCopy("request_failed"));
      renderError("request_failed");
      return;
    }
    renderResult(payload);
    setStatus("ok", "မျက်နှာပြင်ပုံ စစ်ဆေးပြီးပါပြီ။");
  } catch (err) {
    if (err && err.name === "AbortError") {
      setStatus("idle", "ပယ်ဖျက်ပြီး။");
      renderEmpty();
      return;
    }
    setStatus("bad", errorCopy("request_failed"));
    renderError("request_failed");
  } finally {
    abortController = null;
    inFlight = null;
    setBusy(false);
  }
}

function initImageUpload() {
  const zone = $("dropzone");
  const input = $("image-input");
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

function setAudioError(message) {
  const node = $("audio-error");
  node.className = message ? "status bad" : "status idle";
  setText(node, message || "");
}

function setMicError(message) {
  const node = $("mic-error");
  node.className = message ? "status bad" : "status idle";
  setText(node, message || "");
}

function clearAudio() {
  selectedAudio = null;
  if (audioPreviewUrl) {
    URL.revokeObjectURL(audioPreviewUrl);
    audioPreviewUrl = null;
  }
  $("audio-input").value = "";
  $("audio-playback").removeAttribute("src");
  $("audio-preview-wrap").classList.add("is-hidden");
  setAudioError("");
  syncAnalyzeButton();
}

function validateAudioFile(file) {
  if (!file) return "audio_required";
  const type = (file.type || "").split(";")[0];
  const name = (file.name || "").toLowerCase();
  const extOk = [".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"].some((ext) => name.endsWith(ext));
  if (type && !ALLOWED_AUDIO_TYPES.has(type) && !extOk) return "unsupported_audio_type";
  if (!type && !extOk) return "unsupported_audio_type";
  if (file.size > AUDIO_MAX_BYTES) return "audio_too_large";
  return "";
}

function acceptAudioFile(file) {
  const error = validateAudioFile(file);
  if (error) {
    clearAudio();
    setAudioError(errorCopy(error));
    return;
  }
  selectedAudio = file;
  if (audioPreviewUrl) URL.revokeObjectURL(audioPreviewUrl);
  audioPreviewUrl = URL.createObjectURL(file);
  $("audio-playback").src = audioPreviewUrl;
  setText($("audio-meta"), `${file.name} · ${file.type || "audio"} · ${file.size} bytes`);
  $("audio-preview-wrap").classList.remove("is-hidden");
  setAudioError("");
  syncAnalyzeButton();
}

function explainMicError(err) {
  const name = err && err.name ? err.name : "";
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "မိုက်ခရိုဖုန်း ခွင့်ပြုချက် ငြင်းလိုက်သည်။ ဘရောက်ဇာ ဆက်တင်တွင် ခွင့်ပြုပြီး ပြန်ကြိုးစားပါ။";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "မိုက်ခရိုဖုန်း မတွေ့ပါ။ ကိရိယာ ချိတ်ပြီး ပြန်ကြိုးစားပါ။";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return "မိုက်ခရိုဖုန်းကို အခြားအက်ပ်က သုံးနေသည်။ ပိတ်ပြီး ပြန်ကြိုးစားပါ။";
  }
  if (name === "SecurityError") {
    return "ဤစာမျက်နှာသည် မိုက်ခရိုဖုန်း သုံးခွင့် မရှိပါ (HTTPS လိုအပ်နိုင်သည်)။";
  }
  return "မိုက်ခရိုဖုန်း ဖွင့်မရပါ။ ဖိုင်တင်၍ စစ်ဆေးနိုင်သည်။";
}

function pickRecorderMime() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg"];
  if (!window.MediaRecorder || !MediaRecorder.isTypeSupported) return "audio/webm";
  return candidates.find((item) => MediaRecorder.isTypeSupported(item)) || "";
}

function initRecorder() {
  const supported = !!(
    navigator.mediaDevices &&
    navigator.mediaDevices.getUserMedia &&
    window.MediaRecorder
  );
  $("recorder").classList.remove("is-hidden");
  const startBtn = $("record-start");
  const stopBtn = $("record-stop");
  if (!supported) {
    startBtn.disabled = true;
    stopBtn.disabled = true;
    setMicError(
      "မိုက်ခရိုဖုန်း သုံးရန် HTTPS (သို့မဟုတ် localhost) လိုအပ်သည်။ M4A/WAV စသည့် ဖိုင်ကို တင်၍ စစ်ဆေးနိုင်သည်။"
    );
    return;
  }
  startBtn.addEventListener("click", async () => {
    setMicError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordedChunks = [];
      const mime = pickRecorderMime();
      mediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      mediaRecorder.addEventListener("dataavailable", (event) => {
        if (event.data && event.data.size) recordedChunks.push(event.data);
      });
      mediaRecorder.addEventListener("stop", () => {
        stream.getTracks().forEach((track) => track.stop());
        const type =
          mediaRecorder && mediaRecorder.mimeType ? mediaRecorder.mimeType.split(";")[0] : "audio/webm";
        const blob = new Blob(recordedChunks, { type: type || "audio/webm" });
        const file = new File([blob], "recording.webm", { type: blob.type || "audio/webm" });
        acceptAudioFile(file);
        startBtn.disabled = false;
        stopBtn.disabled = true;
      });
      mediaRecorder.start();
      startBtn.disabled = true;
      stopBtn.disabled = false;
    } catch (err) {
      setMicError(explainMicError(err));
    }
  });
  stopBtn.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  });
}

function initAudioUpload() {
  const zone = $("audio-dropzone");
  const input = $("audio-input");
  zone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (file) acceptAudioFile(file);
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
    if (file) acceptAudioFile(file);
  });
  $("remove-audio").addEventListener("click", () => clearAudio());
}

async function analyzeAudio() {
  const error = validateAudioFile(selectedAudio);
  if (error) {
    failWithoutInput(error, setAudioError);
    return;
  }
  abortController = new AbortController();
  setBusy(true);
  setStatus("idle", "စစ်ဆေးနေသည်…");
  renderLoading();
  const body = new FormData();
  body.append("file", selectedAudio, selectedAudio.name);
  try {
    inFlight = fetch("/api/analyze/audio", {
      method: "POST",
      body,
      signal: abortController.signal,
    });
    const response = await inFlight;
    if (!response.ok) {
      const code = await readError(response);
      setStatus("bad", errorCopy(code));
      renderError(code);
      return;
    }
    const payload = await response.json();
    if (!payload || !payload.assessment) {
      setStatus("bad", errorCopy("request_failed"));
      renderError("request_failed");
      return;
    }
    renderResult(payload);
    setStatus("ok", "အသံ စစ်ဆေးပြီးပါပြီ။");
  } catch (err) {
    if (err && err.name === "AbortError") {
      setStatus("idle", "ပယ်ဖျက်ပြီး။");
      renderEmpty();
      return;
    }
    setStatus("bad", errorCopy("request_failed"));
    renderError("request_failed");
  } finally {
    abortController = null;
    inFlight = null;
    setBusy(false);
  }
}

function initAudio() {
  initAudioUpload();
  initRecorder();
}

function initTabs() {
  const tabs = Array.from(document.querySelectorAll(".tab[data-panel]"));
  tabs.forEach((tab, index) => {
    tab.tabIndex = tab.classList.contains("is-active") ? 0 : -1;
    tab.addEventListener("click", () => {
      switchTab(tab.getAttribute("data-panel"));
      tabs.forEach((item, i) => {
        item.tabIndex = i === index ? 0 : -1;
      });
    });
    tab.addEventListener("keydown", (event) => {
      const current = tabs.indexOf(tab);
      let next = current;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (current + 1) % tabs.length;
      else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (current - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = tabs.length - 1;
      else return;
      event.preventDefault();
      switchTab(tabs[next].getAttribute("data-panel"));
      tabs.forEach((item, i) => {
        item.tabIndex = i === next ? 0 : -1;
      });
      tabs[next].focus();
    });
  });
}

async function loadMode() {
  try {
    const response = await fetch("/health");
    const body = await response.json();
    const mode = body.mode === "live" ? "live" : "mock";
    const badge = $("mode-badge");
    badge.classList.toggle("is-live", mode === "live");
    setText(badge, mode);
  } catch (_err) {
    setText($("mode-badge"), "mock");
    $("mode-badge").classList.remove("is-live");
    setStatus("bad", "mode မဖတ်နိုင်ပါ။ mock အဖြစ် ဆက်လုပ်ပါမည်။");
  }
}

function initReport() {
  $("report-confirm").addEventListener("change", () => {
    $("submit-report").disabled = !$("report-confirm").checked || !currentAnalysisId;
  });
  $("report-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentAnalysisId || !$("report-confirm").checked) {
      $("report-status").className = "status bad";
      setText(
        $("report-status"),
        currentAnalysisId ? "အတည်ပြု အကွက်ကို အရင် နှိပ်ပါ။" : errorCopy("analysis_not_found")
      );
      return;
    }
    $("submit-report").disabled = true;
    try {
      const response = await fetch("/api/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          analysis_id: currentAnalysisId,
          note: $("report-note").value,
        }),
      });
      const status = $("report-status");
      if (!response.ok) {
        status.className = "status bad";
        setText(status, errorCopy(await readError(response)));
        $("submit-report").disabled = false;
        return;
      }
      status.className = "status ok";
      setText(status, "ပေးပို့ပြီးပါပြီ။ လူက သုံးသပ်မှသာ စာရင်းသွင်းပါမည်။");
    } catch (_err) {
      $("report-status").className = "status bad";
      setText($("report-status"), errorCopy("request_failed"));
      $("submit-report").disabled = false;
    }
  });
}

function initBlacklist() {
  $("blacklist-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = $("check-value").value;
    const entityType = $("check-type").value;
    const out = $("check-result");
    if (!value.trim()) {
      out.className = "status bad";
      setText(out, errorCopy("value_required"));
      return;
    }
    const params = new URLSearchParams({ entity_type: entityType, value });
    try {
      const response = await fetch(`/api/blacklist/check?${params.toString()}`);
      const body = await response.json();
      if (!response.ok) {
        out.className = "status bad";
        setText(out, errorCopy(body.error || "request_failed"));
        return;
      }
      if (body.matched) {
        out.className = "status ok";
        setText(
          out,
          `လူက အတည်ပြုထားသော စာရင်းနှင့် တူ · ${body.entity_type} · ${body.masked_display_value || ""}`
        );
      } else {
        out.className = "status idle";
        setText(out, "စာရင်းတွင် မတွေ့ပါ။");
      }
    } catch (_err) {
      out.className = "status bad";
      setText(out, errorCopy("request_failed"));
    }
  });
}

function init() {
  loadMode();
  renderEmpty();
  initTabs();
  initImageUpload();
  initAudio();
  initReport();
  initBlacklist();
  $("analyze").addEventListener("click", () => startAnalyze());
  $("cancel-analyze").addEventListener("click", () => cancelAnalyze());
  $("message").addEventListener("input", () => syncAnalyzeButton());
  $("message").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!$("analyze").disabled) startAnalyze();
    }
  });
  syncAnalyzeButton();
}

init();
