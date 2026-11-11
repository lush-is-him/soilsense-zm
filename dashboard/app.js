// SoilSense ZM dashboard: login, fields with GPS, readings, checks, lab results, advice.
// Plain JavaScript, no libraries, so it loads quickly on a phone (NFR4).

"use strict";

const GPS_MAX_M = 30;
const CROPS = ["maize", "soybean", "sunflower", "millet", "groundnut"];
const $app = document.getElementById("app");

// ----- storage (may be unavailable in private windows) -----

const store = {
  get(key) { try { return sessionStorage.getItem(key); } catch (e) { return null; } },
  set(key, value) { try { sessionStorage.setItem(key, value); } catch (e) { /* ignore */ } },
  remove(key) { try { sessionStorage.removeItem(key); } catch (e) { /* ignore */ } },
};

// ----- helpers -----

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(message, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = isError ? "toast error" : "toast";
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 4000);
}

function lang() { return document.getElementById("lang").value; }

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = store.get("token");
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && path !== "/auth/login") {
    store.remove("token");
    location.hash = "#/login";
    throw new Error("Please log in again");
  }
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && body.detail;
    const text = Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail;
    throw new Error(text || `Request failed (${response.status})`);
  }
  return body;
}

const post = (path, data) => api(path, { method: "POST", body: JSON.stringify(data) });

function formData(form) {
  const data = {};
  for (const [key, value] of new FormData(form).entries()) {
    if (value === "") continue;
    const input = form.elements[key];
    data[key] = input && input.type === "number" ? Number(value) : value;
  }
  form.querySelectorAll("input[type=checkbox]").forEach((box) => { data[box.name] = box.checked; });
  return data;
}

function onSubmit(id, handler) {
  const form = document.getElementById(id);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    if (button) button.disabled = true;
    try { await handler(formData(form), form); } catch (error) { toast(error.message, true); }
    finally { if (button) button.disabled = false; }
  });
}

function unreviewedMark(item) {
  return item && item.reviewed === false ? '<span class="unreviewed">not reviewed</span>' : "";
}

function say(item) { return item ? `${esc(item.text)}${unreviewedMark(item)}` : ""; }

// ----- views -----






// ----- advice text (from /i18n, so it follows the language switch) -----

let STRINGS = {};
async function loadStrings(code) {
  try { STRINGS = await api(`/i18n/${code}`); } catch (error) { STRINGS = {}; }
}

// Translated text with the "not reviewed" marker. Placeholders like {crop} are filled from params.
function t(key, params = {}) {
  const item = STRINGS[key];
  if (!item) return esc(key);
  const filled = item.text.replace(/\{(\w+)\}/g, (_, name) => (name in params ? params[name] : `{${name}}`));
  return `${esc(filled)}${unreviewedMark(item)}`;
}
const tPlain = (key) => (STRINGS[key] ? STRINGS[key].text : key);
const cropName = (crop) => tPlain(`crop.${crop}`);

function range(r, unit) {
  if (!r) return "";
  return `${r.low === r.high ? esc(r.low) : `${esc(r.low)}–${esc(r.high)}`} ${esc(unit || r.unit)}`;
}

function extras(perLima) {
  if (!perLima) return "";
  const parts = [];
  if (perLima.household) {
    parts.push(perLima.household.map((h) => `${t("ui.about")} ${esc(h.low === h.high ? h.low : `${h.low}–${h.high}`)} × ${esc(h.container)}`).join(` ${t("ui.or")} `));
  }
  if (perLima.cost) parts.push(`${t("ui.cost")}: ${esc(perLima.cost.currency)} ${esc(perLima.cost.low)}–${esc(perLima.cost.high)} <small>(${esc(perLima.cost.place || "")} ${esc(perLima.cost.date || "")})</small>`);
  return parts.length ? `<br><small>${parts.join(" · ")}</small>` : "";
}

function timingText(timing) {
  return { ok: t("lime.timing_ok"), uncertain: t("lime.timing_uncertain"), too_late: t("lime.too_late"), any_time: t("lime.any_time") }[timing] || "";
}

function fertItem(item, labelKey) {
  if (!item) return "";
  if (item.none) return `<li><strong>${t(labelKey)}:</strong> ${t("fert.none")}</li>`;
  const amount = item.rate_kg_ha != null
    ? ` — ${esc(Array.isArray(item.rate_kg_ha) && item.rate_kg_ha[0] !== item.rate_kg_ha[1] ? item.rate_kg_ha.join("–") : [].concat(item.rate_kg_ha)[0])} kg/ha${item.per_lima ? ` (${range(item.per_lima)} ${t("ui.per_lima")})` : ""}${extras(item.per_lima)}`
    : ` — ${t("rate.open")}`;
  return `<li><strong>${t(labelKey)}:</strong> ${esc(item.product)}${amount}</li>`;
}

function planA(a, crop) {
  if (!a) return "";
  if (a.status !== "ok") return a.note ? `<p>${t(a.note, { crop })}</p>` : `<p>${esc(a.status.replace(/_/g, " "))}</p>`;
  const lime = a.lime || {};
  let limeHtml;
  if (lime.status === "not_needed") limeHtml = t("lime.not_needed");
  else if (lime.rate_t_ha) {
    limeHtml = `${lime.status === "optional" ? `${t("ui.optional")}: ` : ""}${esc(lime.rate_t_ha[0])}–${esc(lime.rate_t_ha[1])} t/ha
      (${range(lime.per_lima)} ${t("ui.per_lima")}), ${esc((lime.products || []).join(" / "))}. ${timingText(lime.timing)}${extras(lime.per_lima)}`;
  } else limeHtml = t("ui.needs_texture");
  const f = a.fertiliser || {};
  return `<ul>
      <li><strong>${t("ui.lime")}:</strong> ${limeHtml}</li>
      ${fertItem(f.basal, "ui.basal")}${fertItem(f.top_dress, "ui.top_dress")}
      <li><strong>${t("ui.manure")}:</strong> ${range(a.manure)} ${t("ui.per_lima")}${extras(a.manure)}</li>
    </ul>`;
}

function planB(b, crop) {
  if (!b) return "";
  if (b.status === "blocked") return `<p>${t("plan.b_blocked")}</p>`;
  if (b.status === "lab_test_recommended") return `<p>${t("ui.lab_test")}</p>`;
  if (b.status !== "ok") return `<p>${t("plan.b_not_applicable", { crop })}</p>`;
  const line = (item) => {
    if (item.item === "lime") {
      if (item.status === "not_needed") return `<li><strong>${t("ui.lime")}:</strong> ${t("lime.not_needed")}</li>`;
      const station = item.g_per_station ? ` (${esc(item.g_per_station.join("–"))} g ${t("ui.per_station")})` : "";
      return `<li><strong>${t("ui.lime")}:</strong> ${range(item.per_lima)} ${t("ui.per_lima")}${station}. ${timingText(item.timing)}${extras(item.per_lima)}</li>`;
    }
    if (item.item === "fertiliser") return fertItem(item, "ui.fertiliser");
    if (item.item === "manure") return `<li><strong>${t("ui.manure")}:</strong> ${range(item.per_lima)} ${t("ui.per_lima")}</li>`;
    if (item.item === "seed") return `<li><strong>${t("ui.seed")}:</strong> ${t("plan.b_seed")}</li>`;
    return `<li>${esc(item.item)}: ${t("rate.open")}</li>`;
  };
  return `${b.note ? `<p>${t(b.note)}</p>` : ""}<ol>${b.items.map(line).join("")}</ol>
    ${b.left_out.length ? `<p class="muted">${t("ui.left_out")}: ${b.left_out.map((x) => t(`ui.${x}`)).join(", ")}</p>` : ""}`;
}

// Plain names for the rules shown under "Why this advice" (the rule id stays in the API).
const RULE_NAMES = {
  "BAND-01": "Soil pH band", "PLAN-A": "Full plan (Plan A)", "PLAN-B": "Cheaper plan (Plan B)",
  "PLAN-C-ORDER": "Crops that suit this soil (Plan C)", "PRICE-INPUTS": "Input prices",
  "LIME-PRODUCTS": "Lime products", "LIME-TARGET": "Target pH after liming", "LIME-TRIGGER": "When lime is needed",
  "LIME-RATES": "Lime amount", "LIME-MAX": "Maximum lime per season", "LIME-TEXTURE-REQUIRED": "Soil texture for lime amount",
  "LIME-LEAD-TIME": "When to apply lime", "LIME-RESIDUAL": "Lime from earlier seasons", "LIME-PARTIAL": "Lime at planting stations",
  "MEAS-LIMA": "Lima conversion", "MEAS-HOUSEHOLD": "Household measures", "TEX-GROUPS": "Soil texture groups",
  "REF-01": "Reading quality", "REF-02": "Too acid to fix in one season", "REF-03": "Waterlogged soil",
  "REF-04": "pH too high for this crop", "REF-05": "Lime timing", "REF-06": "Fertiliser rate available", "REF-07": "Very sandy soil",
};
function ruleName(id) {
  if (RULE_NAMES[id]) return RULE_NAMES[id];
  if (id.startsWith("CROP-")) return `Needs of ${cropName(id.slice(5).toLowerCase())}`;
  if (id.startsWith("MSG-")) return "Farmer reminder";
  return id;
}
function ruleSource(r) {
  if (r.source_type === "expert_opinion" || r.reviewer_alias) return "Agronomist advice";
  if (r.source_type === "derived") return "Safety check built into the system";
  if (r.source_type === "proposed") return "System design (to be confirmed)";
  return "Published guidance";
}

function whyRows(rules) {
  const rows = new Map();
  rules.forEach((r) => {
    const key = `${ruleName(r.id)}|${ruleSource(r)}`;
    rows.set(key, (rows.get(key) || 0) + 1);
  });
  return [...rows].map(([key, n]) => {
    const [name, source] = key.split("|");
    return `<tr><td>${esc(name)}${n > 1 ? ` (${n})` : ""}</td><td>${esc(source)}</td></tr>`;
  }).join("");
}

// Plain-language summary first (what the farmer should do), details on tap.
function adviceSummary(a, crop) {
  const lime = (a.plan_a && a.plan_a.lime) || {};
  const refusals = a.refusals || [];
  if (a.trust_level === "none") return [t("sum.unusable"), t("sum.unusable_sub")];
  if (refusals.includes("REF-02")) return [t("sum.too_acid"), a.refusal_text.map(say).join(" ")];
  if (refusals.includes("REF-04")) return [t("sum.too_high", { crop: capital(crop) }), t("sum.too_high_sub")];
  if (a.method_sensitive) return [t("sum.method"), ""];
  if (a.plan_a && a.plan_a.status !== "ok") return [a.plan_a.note ? t(a.plan_a.note, { crop }) : esc(a.plan_a.status), ""];
  if (lime.status === "not_needed") return [t("sum.fine", { crop }), t("sum.fine_sub")];
  if (lime.status === "optional") return [t("sum.optional", { crop }), t("sum.fine_sub")];
  if (lime.timing === "too_late") return [t("sum.acid_late", { crop }), t("sum.acid_late_sub")];
  return [t("sum.acid", { crop }), a.refusal_text.map(say).join(" ")];
}

function sureText(a) {
  const trust = a.trust || { level: a.trust_level, reasons: [] };
  if (trust.level === "high") return t("sum.sure_high");
  if (trust.level === "moderate") return t("sum.sure_moderate");
  const reasons = (trust.reasons || []).join(" ").toLowerCase();
  if (reasons.includes("disagree")) return t("sum.sure_low_map");
  if (reasons.includes("manual") || reasons.includes("gps") || reasons.includes("no map")) return t("sum.sure_low_place");
  return t("sum.sure_low");
}

function planOneLiners(a, crop) {
  const lime = (a.plan_a && a.plan_a.lime) || {};
  let oneA;
  if (!a.plan_a || a.plan_a.status !== "ok") oneA = a.plan_a && a.plan_a.note ? t(a.plan_a.note, { crop }) : "";
  else oneA = t(lime.status === "not_needed" ? "sum.a_fine" : lime.status === "optional" ? "sum.a_optional" : "sum.a_lime");
  const b = a.plan_b || {};
  let oneB;
  if (b.status === "ok" && b.mode === "budget") {
    const names = b.items.map((i) => tPlain(`ui.${i.item}`).toLowerCase());
    oneB = t("sum.b_budget", { items: names.length > 1 ? `${names.slice(0, -1).join(", ")} ${tPlain("sum.and")} ${names[names.length - 1]}` : names[0] });
  } else if (b.status === "ok") oneB = t("sum.b_order");
  else if (b.status === "blocked") oneB = t("plan.b_blocked");
  else if (b.status === "lab_test_recommended") oneB = t("ui.lab_test");
  else oneB = t("plan.b_not_applicable", { crop });
  const crops = (a.plan_c && a.plan_c.crops) || [];
  const oneC = crops.length ? t("sum.c_crops", { crops: crops.map(cropName).join(", ") }) : t("plan.c_none");
  return [oneA, oneB, oneC];
}

function checksBanner(a) {
  const c = a.checks;
  if (!c || c.status === "ok") return c && c.confirmed_by_repeat ? `<p class="notice info">${t("check.repeat_agrees")}</p>` : "";
  const lab = c.status === "confirm_lab";
  return `<div class="card notice ${lab ? "info" : "stop"} checks">
    <h2>${t(lab ? "check.title_lab" : "check.title_probe")}</h2>
    <ul>${c.reasons.map((r) => `<li>${t(r)}</li>`).join("")}</ul>
    ${lab ? `<p>${t("check.lab_why")}</p>` : ""}
  </div>`;
}

const capital = (word) => (word ? word.charAt(0).toUpperCase() + word.slice(1) : "");

async function viewAdvice(recId, target = $app) {
  const code = lang();
  const [a] = await Promise.all([api(`/advice/${recId}?lang=${code}`), loadStrings(code)]);
  const trust = a.trust || { level: a.trust_level, reasons: [] };
  const crop = cropName(a.crop);
  const [headline, sub] = adviceSummary(a, crop);
  const [oneA, oneB, oneC] = planOneLiners(a, crop);
  const used = JSON.stringify(a);
  const rules = a.fired_rules.filter((r) =>
    !(r.id === "PRICE-INPUTS" && !used.includes('"cost":{')) && !(r.id === "MEAS-HOUSEHOLD" && !used.includes('"household":[')));
  const planCard = (cls, letter, title, one, body, open) => `
    <details class="plan-card ${cls}"${open ? " open" : ""}>
      <summary><span class="plan-letter">${letter}</span>
        <span class="plan-text"><strong>${title}</strong><span>${one}</span></span></summary>
      <div class="plan-body">${body}</div>
    </details>`;
  target.innerHTML = `
    ${target === $app ? `<p><a href="javascript:history.back()">← Back</a></p>` : ""}
    ${a.checks && a.checks.status === "check_probe" ? checksBanner(a) : ""}
    <div class="card summary ${esc(trust.level)}">
      <p class="muted">${esc(capital(crop))} · pH ${esc(a.ph_input)} (${esc(a.ph_method_input)}) · ${esc(a.as_of_date)}</p>
      <h1 class="headline">${headline}</h1>
      ${sub ? `<p class="subline">${sub}</p>` : ""}
      <div class="sure"><span class="badge ${esc(trust.level)}">${esc(tPlain(`ui.trust.${trust.level}`))}</span>
        <span>${t("sum.sure")} ${sureText(a)}</span></div>
      ${a.borderline ? `<p class="notice info">${t("borderline")}</p>` : ""}
    </div>
    ${a.checks && a.checks.status === "check_probe" ? "" : checksBanner(a)}
    ${a.method_sensitive ? `<div class="card"><h2>${t("ui.depends_method")}</h2>
      <table><tr><th>pH</th><th>Band</th><th>${t("ui.lime")} t/ha</th><th>Plan C</th></tr>
      ${a.alternatives.map((x) => `<tr><td>${esc(x.ph_in_rule_scale)}</td><td>${esc(x.band)}</td>
        <td>${x.lime_rate_t_ha ? esc(x.lime_rate_t_ha.join("–")) : esc(x.refusals.join(" ") || "–")}</td>
        <td>${esc(x.plan_c.map(cropName).join(", "))}</td></tr>`).join("")}</table></div>` : ""}
    ${a.trust_level !== "none" ? `
      <h2 class="choose">${t("sum.choose")} <small class="muted">${t("sum.tap")}</small></h2>
      ${planCard("a", "A", t("ui.plan_a", { crop }), oneA, planA(a.plan_a, crop), false)}
      ${planCard("b", "B", t("ui.plan_b"), oneB, planB(a.plan_b, crop), false)}
      ${planCard("c", "C", t("ui.plan_c"), oneC,
        a.plan_c && a.plan_c.crops.length ? `<p>${a.plan_c.crops.map((c) => esc(capital(cropName(c)))).join(", ")}</p>` : `<p>${t("plan.c_none")}</p>`, false)}` : ""}
    <div class="card"><h2>${t("ui.remember")}</h2><ul>${a.messages.map((m) => `<li>${say(m)}</li>`).join("")}</ul></div>
    <div class="card help-card"><h2>Not sure about this result?</h2>
      <div class="actions"><button class="secondary help-btn" data-kind="lab">Request a lab test</button>
        <button class="secondary help-btn" data-kind="visit">Ask an officer to visit</button></div></div>
    ${(typeof me === "function" && me().role === "farmer") ? "" : `<button class="secondary sms-btn">${tPlain("ui.send_sms")}</button>`}
    <details class="card tech"><summary>${t("sum.details")}</summary>
      <p class="muted">${esc((trust.reasons || []).join("; "))}${a.texture && a.texture.value ? ` · texture ${esc(a.texture.value)} (${esc(a.texture.source)})` : ""}</p>
      <h3>${t("ui.why")}</h3>
      <table><tr><th>What was checked</th><th>Based on</th></tr>${whyRows(rules)}</table>
      ${a.unreviewed ? `<p class="muted">${t("ui.unconfirmed_rules")}</p>` : ""}
    </details>`;
  target.querySelectorAll(".help-btn").forEach((button) => button.addEventListener("click", async () => {
    const kind = button.dataset.kind;
    try {
      await post("/referrals", { field_id: a.field_id, kind, reading_id: a.reading_id || null,
        reason: kind === "lab" ? "Confirm this reading with a lab test" : "Please come and test this field" });
      toast(kind === "lab" ? "Lab test requested. An officer will contact you about the sample." : "Visit requested.");
    } catch (error) { toast(error.message, true); }
  }));
  const sms = target.querySelector(".sms-btn");
  if (sms) sms.addEventListener("click", async () => {
    try {
      const r = await post(`/advice/${recId}/sms`, {});
      toast(r.status === "sent" ? `SMS sent: ${r.message}`
        : r.status === "stubbed" ? `SMS not sent (no SMS account set up on this server). The message would be: ${r.message}`
        : `SMS failed (${r.status}). Message: ${r.message}`, r.status !== "sent" && r.status !== "stubbed");
    }
    catch (error) { toast(error.message, true); }
  });
}

// ----- live probe page (the bridge runs: python -m bridge.bridge live --field N) -----

let liveTimer = null;
async function viewLive(fieldId) {
  const [field, history, devices] = await Promise.all([
    api(`/fields/${fieldId}`), api(`/fields/${fieldId}/history`), api("/devices"), loadStrings(lang())]);
  const device = (devices[0] || {}).device_id || "probe-1";
  try { await post(`/devices/${device}/active-field`, { field_id: Number(fieldId) }); } catch (error) { /* bridge can still use --field */ }
  let lastSeen = history.readings.length ? history.readings[0].reading_id : 0;
  const startedAt = new Date().toISOString();
  let lastLiveTs = "";
  $app.innerHTML = `
    <p><a href="#/field/${esc(fieldId)}">← ${esc(field.name)}</a></p>
    <h1>Live reading: ${esc(field.name)}</h1>
    <div class="card">
      <div class="row">
        <div><label for="live-crop">Crop the farmer wants to grow</label>
          <select id="live-crop">${CROPS.map((c) => `<option value="${c}">${esc(cropName(c))}</option>`).join("")}</select></div>
      </div>
      <div class="live-box">
        <div class="live-ph" id="live-ph">–</div>
        <div id="live-state" class="muted">Waiting for the probe. Put it in the sample.<br>
          (The probe program must be running: double-click START DEMO on the laptop.)</div>
        <div id="live-temp" class="muted"></div>
      </div>
    </div>
    <div id="live-advice"></div>`;
  const $ph = document.getElementById("live-ph"), $state = document.getElementById("live-state");
  const $temp = document.getElementById("live-temp"), $advice = document.getElementById("live-advice");
  let busy = false;
  async function tick() {
    if (!location.hash.startsWith(`#/live/${fieldId}`)) { clearInterval(liveTimer); liveTimer = null; return; }
    if (busy) return;
    busy = true;
    try {
      const live = await api(`/devices/${device}/live`);
      if (live.ts && live.ts !== lastLiveTs && live.ts > startedAt && (live.field_id == null || String(live.field_id) === String(fieldId))) {
        lastLiveTs = live.ts;
        $ph.textContent = live.ph != null ? `pH ${Number(live.ph).toFixed(2)}` : "–";
        $ph.classList.toggle("settling", !live.settled);
        $state.textContent = live.settled ? "Steady. Saving the reading…" : "Probe in the sample: settling…";
        $temp.textContent = live.temp_c != null ? `Sample temperature ${Number(live.temp_c).toFixed(1)} °C (pH corrected for it)` : "";
      }
      const h = await api(`/fields/${fieldId}/history`);
      const newest = h.readings[0];
      if (newest && newest.reading_id > lastSeen) {
        lastSeen = newest.reading_id;
        if (newest.quality_status === "accepted") {
          $ph.textContent = `pH ${Number(newest.ph_water).toFixed(2)}`;
          $ph.classList.remove("settling");
          $state.textContent = "Reading saved. Advice below. Rinse the probe and put it in the next sample.";
          const advice = await post("/advice", { field_id: Number(fieldId), reading_id: newest.reading_id,
            crop: document.getElementById("live-crop").value, lang: lang() });
          await viewAdvice(advice.rec_id, $advice);
        } else {
          $state.textContent = `Reading rejected: ${(newest.quality_reasons || []).join("; ")}`;
        }
      }
    } catch (error) { $state.textContent = error.message; }
    finally { busy = false; }
  }
  if (liveTimer) clearInterval(liveTimer);
  liveTimer = setInterval(tick, 1500);
  tick();
}

async function viewProbe() {
  const devices = await api("/devices");
  const ago = (iso) => (iso ? (Date.now() - new Date(iso).getTime()) / 1000 : Infinity);
  const when = (sqlDate) => {
    if (!sqlDate) return "";
    const d = new Date(sqlDate.replace(" ", "T") + "Z");
    return d.toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  };
  const today = (sqlDate) => sqlDate && new Date(sqlDate.replace(" ", "T") + "Z").toDateString() === new Date().toDateString();
  $app.innerHTML = `
    <h1>Probe</h1>
    ${devices.map((d) => {
      const c = d.latest_calibration;
      const connected = ago(d.last_seen) < 20;
      const calState = !c ? ["rejected", "Not calibrated", "Calibrate before measuring."]
        : !c.accepted ? ["rejected", "Last calibration failed", "Calibrate again with fresh buffers."]
        : today(c.date) ? ["accepted", "Calibrated today", "Ready to measure."]
        : ["low", "Calibrated, but not today", "Calibrate again before measuring today."];
      return `
      <div class="card">
        <h2>${esc(d.label)}</h2>
        <div class="status-row">
          <span class="dot ${connected ? "on" : "off"}"></span>
          <div><strong>${connected ? "Connected" : "Not connected"}</strong><br>
            <small class="muted">${connected ? "The probe program is running and talking to the Arduino."
              : "Plug in the Arduino and double-click START DEMO on the laptop."}</small></div>
        </div>
        <div class="status-row">
          <span class="badge ${calState[0]}">${calState[1]}</span>
          <div><small class="muted">${calState[2]}${c ? ` Last: ${esc(when(c.date))}, slope ${esc(c.slope_pct)}% (must be 95–105%), ${esc(c.temp_c)} °C.` : ""}</small></div>
        </div>
      </div>`;
    }).join("")}
    <div class="card">
      <h2>How to calibrate (once a day)</h2>
      <ol>
        <li>Have the pH 7.00 and pH 4.00 buffers and clean water ready, in the room where you will measure.</li>
        <li>Double-click <strong>START DEMO</strong> and answer <strong>Y</strong> when it asks to calibrate.</li>
        <li>Follow the black window: pH 7.00 first, rinse, then pH 4.00.</li>
        <li>When it says <strong>Calibration ACCEPTED</strong>, this page shows “Calibrated today”.</li>
      </ol>
    </div>
    <details class="card">
      <summary>Enter a calibration by hand (advanced)</summary>
      <p class="muted">Only if the probe program cannot be used: type the electrode millivolts it showed.</p>
      <form id="cal-form">
        <label for="cal-device">Probe</label>
        <select id="cal-device" name="device_id">${devices.map((d) => `<option value="${esc(d.device_id)}">${esc(d.label)}</option>`).join("")}</select>
        <div class="row">
          <div><label for="mv_ph7">mV in pH 7.00</label><input id="mv_ph7" name="mv_ph7" type="number" step="0.1" required></div>
          <div><label for="mv_ph4">mV in pH 4.00</label><input id="mv_ph4" name="mv_ph4" type="number" step="0.1" required></div>
          <div><label for="cal-temp">Buffer °C</label><input id="cal-temp" name="temp_c" type="number" step="0.1" required></div>
        </div>
        <button type="submit">Save calibration</button>
      </form>
    </details>`;
  onSubmit("cal-form", async (d) => {
    const r = await post(`/devices/${encodeURIComponent(d.device_id)}/calibrations`,
      { mv_ph7: d.mv_ph7, mv_ph4: d.mv_ph4, temp_c: d.temp_c });
    toast(r.accepted ? `Calibration accepted (slope ${r.slope_pct}%)` : `Rejected: ${r.reasons.join("; ")}`, !r.accepted);
    await viewProbe();
  });
  // refresh the status every 5 s while this page is open
  clearTimeout(window.probeTimer);
  window.probeTimer = setTimeout(() => { if (location.hash.startsWith("#/probe")) viewProbe().catch(() => {}); }, 5000);
}


