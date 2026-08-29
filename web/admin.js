const TOKEN_KEY = "thati_admin_token";

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

function token() {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

function headers() {
  return { "X-Admin-Token": token(), "Content-Type": "application/json" };
}

async function readError(response) {
  try {
    const body = await response.json();
    return body.error || "request_failed";
  } catch (_err) {
    return "request_failed";
  }
}

function appendMeta(card, report) {
  const meta = el("p", "meta");
  setText(
    meta,
    [
      report.source_type || "text",
      report.created_at || "",
      `risk ${report.risk_level || "—"} (${report.risk_score ?? "—"})`,
    ].join(" · ")
  );
  const risk = el("span", `risk-${report.risk_level || "low"}`);
  setText(risk, report.risk_level || "");
  meta.append(" ");
  meta.append(risk);
  card.append(meta);
}

function appendBlock(card, title, body) {
  const heading = el("h3");
  setText(heading, title);
  const paragraph = el("p");
  setText(paragraph, body || "—");
  card.append(heading, paragraph);
}

function renderEvidence(card, evidence) {
  const heading = el("h3");
  setText(heading, "အထောက်အထား");
  card.append(heading);
  const list = el("ul", "evidence");
  if (!evidence || !evidence.length) {
    const empty = el("li");
    setText(empty, "မရှိပါ");
    list.append(empty);
  } else {
    evidence.forEach((item) => {
      const li = el("li");
      const quote = el("div", "quote");
      setText(quote, item.quote || "");
      const expl = el("div");
      setText(expl, item.myanmar_explanation || "");
      li.append(quote, expl);
      list.append(li);
    });
  }
  card.append(list);
}

function renderEntities(card, report) {
  const heading = el("h3");
  setText(heading, "ထုတ်ယူထားသော identifiers (masked — သီးခြား ရွေးချယ်ပါ)");
  card.append(heading);
  const box = el("div", "entities");
  const entities = report.entities || [];
  if (!entities.length) {
    const empty = el("p", "empty");
    setText(empty, "ထုတ်ယူထားသော identifier မရှိပါ။");
    card.append(empty);
    return box;
  }
  entities.forEach((item) => {
    const label = el("label");
    const input = el("input");
    input.type = "checkbox";
    input.name = `entity-${report.id}`;
    input.value = String(item.index);
    input.disabled = !item.eligible;
    const text = el("span");
    const masked = item.masked_value || "—";
    setText(
      text,
      item.eligible
        ? `${item.entity_type} · ${masked}`
        : `${item.entity_type} · မရွေးနိုင်ပါ`
    );
    label.append(input, text);
    box.append(label);
  });
  card.append(box);
  return box;
}

function selectedIndexes(box) {
  return Array.from(box.querySelectorAll("input[type=checkbox]:checked")).map((input) =>
    Number(input.value)
  );
}

function renderReport(report) {
  const card = el("article", "card report");
  card.dataset.reportId = report.id;
  const title = el("h2");
  setText(title, `Report ${report.id.slice(0, 8)}`);
  card.append(title);
  appendMeta(card, report);
  appendBlock(card, "စာအနှစ်ချုပ်", report.myanmar_summary);
  appendBlock(card, "English summary", report.english_summary);
  appendBlock(card, "သိမ်းထားသော excerpt", report.source_excerpt);
  appendBlock(card, "ပို့သူ မှတ်ချက်", report.note);
  renderEvidence(card, report.evidence);
  const entityBox = renderEntities(card, report);
  const actions = el("div", "actions");
  const approve = el("button", "btn-primary");
  approve.type = "button";
  setText(approve, "ရွေးထားသည်များကို အတည်ပြု");
  const reject = el("button", "btn-urgent");
  reject.type = "button";
  setText(reject, "ငြင်းပယ်");
  approve.addEventListener("click", () => approveReport(report, entityBox, approve, reject));
  reject.addEventListener("click", () => rejectReport(report, approve, reject));
  actions.append(approve, reject);
  card.append(actions);
  return card;
}

async function approveReport(report, entityBox, approveBtn, rejectBtn) {
  const indexes = selectedIndexes(entityBox);
  if (!indexes.length) {
    setStatus("bad", "ရွေးထားသော eligible entity မရှိပါ။ အတည်မပြုပါ။");
    return;
  }
  approveBtn.disabled = true;
  rejectBtn.disabled = true;
  try {
    const response = await fetch(`/api/admin/reports/${report.id}/approve`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        entity_indexes: indexes,
        reason: "human_reviewed",
        risk_level: report.risk_level || "high",
      }),
    });
    if (!response.ok) {
      approveBtn.disabled = false;
      rejectBtn.disabled = false;
      setStatus("bad", `အတည်ပြုမရပါ (${await readError(response)})`);
      return;
    }
    setStatus("ok", "အတည်ပြုပြီး — ရွေးထားသော identifiers ကို လူက စာရင်းသွင်းပြီးပါပြီ။");
    await loadQueue();
  } catch (_err) {
    approveBtn.disabled = false;
    rejectBtn.disabled = false;
    setStatus("bad", "အတည်ပြုမရပါ (request_failed)");
  }
}

async function rejectReport(report, approveBtn, rejectBtn) {
  approveBtn.disabled = true;
  rejectBtn.disabled = true;
  try {
    const response = await fetch(`/api/admin/reports/${report.id}/reject`, {
      method: "POST",
      headers: headers(),
    });
    if (!response.ok) {
      approveBtn.disabled = false;
      rejectBtn.disabled = false;
      setStatus("bad", `ငြင်းပယ်မရပါ (${await readError(response)})`);
      return;
    }
    setStatus("ok", "ငြင်းပယ်ပြီး — blacklist မထည့်ပါ။");
    await loadQueue();
  } catch (_err) {
    approveBtn.disabled = false;
    rejectBtn.disabled = false;
    setStatus("bad", "ငြင်းပယ်မရပါ (request_failed)");
  }
}

async function loadQueue() {
  if (!token()) {
    setStatus("bad", "Admin token ထည့်ပါ။");
    return;
  }
  setStatus("idle", "ဖွင့်နေသည်…");
  try {
    const response = await fetch("/api/admin/reports?status=pending", { headers: headers() });
    if (!response.ok) {
      const code = await readError(response);
      const copy =
        code === "unauthorized"
          ? "token မမှန်ပါ။"
          : `စာရင်းမရပါ (${code})`;
      setStatus("bad", copy);
      return;
    }
    const payload = await response.json();
    const queue = $("queue");
    while (queue.firstChild) queue.removeChild(queue.firstChild);
    const reports = payload.reports || [];
    if (!reports.length) {
      const empty = el("p", "empty");
      setText(empty, "စောင့်ဆိုင်းနေသော အချက် မရှိပါ။");
      queue.append(empty);
      setStatus("ok", "စာရင်း ဗလာဖြစ်သည်။");
      return;
    }
    reports.forEach((report) => queue.append(renderReport(report)));
    setStatus("ok", `စောင့်ဆိုင်း ${reports.length} ခု (အဟောင်းဆုံး အရင်)။`);
  } catch (_err) {
    setStatus("bad", "စာရင်းမရပါ (request_failed)");
  }
}

function init() {
  const field = $("admin-token");
  field.value = token();
  $("save-token").addEventListener("click", () => {
    sessionStorage.setItem(TOKEN_KEY, field.value);
    setStatus("ok", "Token ကို ဤ session တွင် သိမ်းပြီးပါပြီ။");
  });
  $("load-queue").addEventListener("click", () => loadQueue());
}

init();
