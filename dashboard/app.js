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

function viewLogin() {
  document.getElementById("topbar").hidden = true;
  $app.innerHTML = `
    <div class="card">
      <h1>SoilSense ZM</h1>
      <p class="muted">Soil and crop advice for Kafue District. Log in to continue.</p>
      <form id="login-form">
        <label for="username">Username</label>
        <input id="username" name="username" autocomplete="username" required>
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required>
        <button type="submit">Log in</button>
      </form>
    </div>`;
  onSubmit("login-form", async (data) => {
    const result = await post("/auth/login", data);
    store.set("token", result.token);
    store.set("user", JSON.stringify(result.user));
    location.hash = "#/home";
  });
}

async function viewHome() {
  const [devices, recent] = await Promise.all([api("/devices"), api("/advice?limit=5").catch(() => []), loadStrings(lang())]);
  const d = devices[0] || {};
  const c = d.latest_calibration;
  const connected = d.last_seen && (Date.now() - new Date(d.last_seen).getTime()) / 1000 < 20;
  const calToday = c && c.accepted && new Date(c.date.replace(" ", "T") + "Z").toDateString() === new Date().toDateString();
  let user = "operator";
  try { user = JSON.parse(store.get("user")).username || user; } catch (error) { /* keep default */ }
  $app.innerHTML = `
    <h1>Hello, ${esc(user)}</h1>
    <a class="probe-strip ${connected && calToday ? "ok" : "warn"}" href="#/probe">
      <span class="dot ${connected ? "on" : "off"}"></span>
      <span>Probe: <strong>${connected ? "connected" : "not connected"}</strong>
        · ${calToday ? "calibrated today" : c && c.accepted ? "not calibrated today" : "not calibrated"}</span>
      <span class="go">›</span></a>
    <div class="tiles">
      <a class="tile primary" href="#/fields"><span class="tile-icon" aria-hidden="true">🌱</span><strong>Measure soil</strong><span>Choose a farmer’s field, then use the probe</span></a>
      <a class="tile" href="#/fields"><span class="tile-icon" aria-hidden="true">👥</span><strong>Farmers</strong><span>Register farmers and their fields</span></a>
      <a class="tile" href="#/probe"><span class="tile-icon" aria-hidden="true">🔬</span><strong>Probe</strong><span>Connection and daily calibration</span></a>
      <a class="tile" href="#/help"><span class="tile-icon" aria-hidden="true">🧺</span><strong>How to sample</strong><span>Taking a good soil sample</span></a>
    </div>
    ${recent.length ? `<div class="card"><h2>Latest advice</h2><ul class="field-list">${recent.map((r) => `
      <li><a class="field-link" href="#/advice/${r.rec_id}"><span><strong>${esc(r.farmer)}</strong> · ${esc(r.field)}<br>
        <small class="muted">${esc(capital(cropName(r.crop)))} · ${esc(r.as_of_date)}</small></span>
        <span class="badge ${esc(r.trust_level)}">${esc(r.trust_level)}</span></a></li>`).join("")}</ul></div>` : ""}`;
}

async function viewFields() {
  const farmers = await api("/farmers");
  const detailed = await Promise.all(farmers.map((f) => api(`/farmers/${f.farmer_id}`)));
  const LANG_NAMES = { en: "English", ny: "Nyanja", toi: "Tonga" };
  $app.innerHTML = `
    <h1>Farmers</h1>
    <p class="muted">You are the operator (extension worker). Each farmer below owns one or more fields;
      open a field to measure its soil and give advice.</p>
    ${detailed.length ? detailed.map((f) => `
      <div class="card farmer">
        <div class="farmer-head">
          <h2>${esc(f.alias)}</h2>
          <small>Advice in ${esc(LANG_NAMES[f.preferred_language] || f.preferred_language)}
            · ${f.sms_consent ? "SMS allowed" : "no SMS"}</small>
        </div>
        <h3>Fields (${f.fields.length})</h3>
        ${f.fields.length ? `<ul class="field-list">${f.fields.map((fl) => `
          <li><a class="field-link" href="#/field/${fl.field_id}"><strong>${esc(fl.name)}</strong>
            <small>${esc(fl.location_source === "gps" ? `GPS ±${fl.gps_accuracy_m} m` : "manual pin")}</small></a></li>`).join("")}</ul>`
          : '<p class="muted">No fields yet.</p>'}
        <a class="button secondary-btn" href="#/new-field/${f.farmer_id}">+ Add a field for ${esc(f.alias)}</a>
      </div>`).join("") : '<div class="card"><p class="muted">No farmers yet. Register one below.</p></div>'}
    <details class="card">
      <summary>Register a farmer</summary>
      <form id="farmer-form">
        <label for="alias">Alias (no real names needed)</label>
        <input id="alias" name="alias" required maxlength="60">
        <label for="preferred_language">Preferred language</label>
        <select id="preferred_language" name="preferred_language">
          <option value="en">English</option><option value="ny">Nyanja</option><option value="toi">Tonga</option>
        </select>
        <label class="check"><input type="checkbox" name="sms_consent" id="sms_consent">
          Farmer agrees to receive an SMS (number deleted after the demonstration)</label>
        <label for="phone">Phone (only with consent)</label>
        <input id="phone" name="phone" type="tel" placeholder="+260...">
        <button type="submit">Register farmer</button>
      </form>
    </details>`;
  onSubmit("farmer-form", async (data) => {
    if (!data.sms_consent) delete data.phone;
    await post("/farmers", data);
    toast("Farmer registered");
    await viewFields();
  });
}

function viewNewField(farmerId) {
  $app.innerHTML = `
    <h1>Register a field</h1>
    <div class="card">
      <form id="field-form">
        <label for="name">Field name</label>
        <input id="name" name="name" required maxlength="60">
        <p class="muted">Stand in the middle of the field and get a GPS fix. It must be ${GPS_MAX_M} m or better.</p>
        <div class="actions">
          <button type="button" id="gps-btn">Get GPS fix</button>
          <button type="button" class="secondary" id="manual-btn">Drop a manual pin instead</button>
        </div>
        <p id="gps-status" class="muted"></p>
        <div class="row">
          <div><label for="lat">Latitude</label><input id="lat" name="lat" type="number" step="any" required readonly></div>
          <div><label for="lon">Longitude</label><input id="lon" name="lon" type="number" step="any" required readonly></div>
        </div>
        <input type="hidden" name="gps_accuracy_m" id="gps_accuracy_m">
        <input type="hidden" name="location_source" id="location_source" value="gps">
        <label for="area_lima">Area in lima (optional)</label>
        <input id="area_lima" name="area_lima" type="number" step="any" min="0">
        <button type="submit" id="save-field" disabled>Save field</button>
      </form>
    </div>`;
  const status = document.getElementById("gps-status");
  const save = document.getElementById("save-field");
  const lat = document.getElementById("lat");
  const lon = document.getElementById("lon");

  document.getElementById("gps-btn").addEventListener("click", () => {
    if (!navigator.geolocation) { status.textContent = "This phone cannot give a GPS fix. Use a manual pin."; return; }
    status.textContent = "Getting a fix…";
    navigator.geolocation.getCurrentPosition((pos) => {
      const acc = Math.round(pos.coords.accuracy);
      lat.value = pos.coords.latitude.toFixed(6);
      lon.value = pos.coords.longitude.toFixed(6);
      document.getElementById("gps_accuracy_m").value = acc;
      document.getElementById("location_source").value = "gps";
      const ok = acc <= GPS_MAX_M;
      status.textContent = ok ? `Fix accepted: ±${acc} m.` : `Fix is ±${acc} m, worse than ${GPS_MAX_M} m. Wait and try again, or drop a manual pin.`;
      save.disabled = !ok;
    }, (err) => { status.textContent = `GPS failed: ${err.message}. Try again or use a manual pin.`; },
    { enableHighAccuracy: true, timeout: 30000, maximumAge: 0 });
  });

  document.getElementById("manual-btn").addEventListener("click", () => {
    lat.readOnly = false; lon.readOnly = false;
    document.getElementById("location_source").value = "manual";
    document.getElementById("gps_accuracy_m").value = "";
    status.textContent = "Type the coordinates. Manual pins get low confidence advice.";
    save.disabled = false;
  });

  onSubmit("field-form", async (data) => {
    data.farmer_id = Number(farmerId);
    const field = await post("/fields", data);
    toast("Field saved");
    location.hash = `#/field/${field.field_id}`;
  });
}

async function viewField(fieldId) {
  const [field, history, devices] = await Promise.all([
    api(`/fields/${fieldId}`), api(`/fields/${fieldId}/history`), api("/devices")]);
  const farmer = await api(`/farmers/${field.farmer_id}`).catch(() => ({ alias: "" }));
  let mapHtml;
  try {
    const m = await api(`/fields/${fieldId}/map-estimate`);
    mapHtml = `pH ${esc(m.ph_mean)} ± ${esc(m.ph_sd)} (water), texture ${esc(m.texture || "unknown")}`;
  } catch (error) { mapHtml = esc(error.message); }

  const readings = history.readings.map((r) => `
    <option value="${r.reading_id}" ${r.quality_status === "accepted" ? "" : "data-bad"}>
      #${r.reading_id} ${r.quality_status === "accepted" ? `pH ${r.ph_water}` : "rejected"} (${esc(r.ts)})</option>`).join("");

  $app.innerHTML = `
    <p><a href="#/fields">← Farmers</a> / ${esc(farmer.alias)}</p>
    <h1>Field: ${esc(field.name)}</h1>
    <p class="muted">Farmer: <strong>${esc(farmer.alias)}</strong></p>
    <a class="button big-btn" href="#/live/${esc(fieldId)}">Measure with the probe (live)</a>
    <div class="card">
      <p>${esc(field.lat)}, ${esc(field.lon)} · ${field.location_source === "gps" ? `GPS ±${esc(field.gps_accuracy_m)} m` : "manual pin"}</p>
      <p><strong>Map (iSDAsoil):</strong> ${mapHtml}</p>
    </div>




    <div class="card">
      <h2>Get advice</h2>
      <form id="advice-form">
        <label for="reading_id">Reading</label>
        <select id="reading_id" name="reading_id">
          ${readings}<option value="">Use the lab result</option>
        </select>
        <div class="row">
          <div><label for="crop">Target crop</label>
            <select id="crop" name="crop">${CROPS.map((c) => `<option>${c}</option>`).join("")}</select></div>
          <div><label for="budget_band">Budget</label>
            <select id="budget_band" name="budget_band"><option value="low">Low</option><option value="medium">Medium</option></select></div>
          <div><label for="water">Water</label>
            <select id="water" name="water"><option value="rainfed">Rainfed</option><option value="irrigated">Irrigated</option></select></div>
        </div>
        <button type="submit">Get advice</button>
      </form>
    </div>
    ${history.readings.length ? `<div class="card"><h2>Readings</h2><ul class="list">${history.readings.map((r) => `
        <li><span class="badge ${esc(r.quality_status)}">${esc(r.quality_status)}</span>
          ${r.ph_water != null ? `pH ${esc(r.ph_water)}` : ""} <small>${esc(r.ts)}</small>
          ${r.quality_reasons && r.quality_reasons.length ? `<br><small>${r.quality_reasons.map(esc).join("; ")}</small>` : ""}</li>`).join("")}</ul></div>` : ""}
    <details class="card">
      <summary>Field checks: texture by feel, waterlogging</summary>
      <form id="check-form">
        <label for="texture_by_feel">Texture by feel</label>
        <select id="texture_by_feel" name="texture_by_feel">
          <option value="">Not checked</option><option value="sandy">Sandy (gritty, falls apart)</option>
          <option value="loamy">Loamy (soft, holds shape loosely)</option><option value="clay">Clay (sticky, makes a ribbon)</option>
        </select>
        <label for="colour">Colour</label><input id="colour" name="colour">
        <label for="previous_crop">Previous crop</label><input id="previous_crop" name="previous_crop">
        <label class="check"><input type="checkbox" name="waterlogging"> Waterlogged in the rains</label>
        <label class="check"><input type="checkbox" name="manure_available"> Manure available</label>
        <button type="submit">Save field check</button>
      </form>
    </details>
    <details class="card">
      <summary>Lab result (optional)</summary>
      <form id="lab-form">
        <div class="row">
          <div><label for="ph">pH</label><input id="ph" name="ph" type="number" step="0.01" required></div>
          <div><label for="ph_method">Method</label>
            <select id="ph_method" name="ph_method" required>
              <option value="">Choose…</option><option value="water">Water</option><option value="cacl2">CaCl₂</option>
            </select></div>
        </div>
        <label for="texture">Texture (as on the report)</label><input id="texture" name="texture" placeholder="e.g. Sandy Clay Loam">
        <label for="lab_name">Lab</label><input id="lab_name" name="lab_name">
        <label for="date">Date</label><input id="date" name="date" type="date">
        <button type="submit">Save lab result</button>
      </form>
    </details>
    <details class="card">
      <summary>Enter a reading by hand (without the probe program)</summary>
      <form id="reading-form">
        <label for="device_id">Probe</label>
        <select id="device_id" name="device_id" required>
          ${devices.map((d) => `<option value="${esc(d.device_id)}">${esc(d.label)}
            ${d.latest_calibration ? (d.latest_calibration.accepted ? "" : " (last calibration failed)") : " (not calibrated)"}</option>`).join("")}
        </select>
        <p class="muted">Three readings of the same 1:2.5 soil-water mix. They must be within 0.1 of each other.</p>
        <div class="row">
          <div><label for="r1">pH 1</label><input id="r1" name="r1" type="number" step="0.01" required></div>
          <div><label for="r2">pH 2</label><input id="r2" name="r2" type="number" step="0.01" required></div>
          <div><label for="r3">pH 3</label><input id="r3" name="r3" type="number" step="0.01" required></div>
          <div><label for="temp_c">Temp °C</label><input id="temp_c" name="temp_c" type="number" step="0.1" required></div>
        </div>
        <button type="submit">Save reading</button>
      </form>
    </details>
    ${history.recommendations.length ? `<div class="card"><h2>Earlier advice</h2><ul class="list">${history.recommendations.map((r) => `
      <li><a href="#/advice/${r.rec_id}">${esc(r.crop)} · ${esc(r.as_of_date)}</a>
        <span class="badge ${esc(r.trust_level)}">${esc(r.trust_level)}</span></li>`).join("")}</ul></div>` : ""}`;

  onSubmit("reading-form", async (d) => {
    const reading = await post("/readings", { field_id: Number(fieldId), device_id: d.device_id,
      replicates_ph: [d.r1, d.r2, d.r3], temp_c: d.temp_c });
    toast(reading.quality_status === "accepted" ? `Reading accepted: pH ${reading.ph_water}` :
      `Reading rejected: ${reading.quality_reasons.join("; ")}`, reading.quality_status !== "accepted");
    await viewField(fieldId);
  });
  onSubmit("check-form", async (d) => { await post(`/fields/${fieldId}/checks`, d); toast("Field check saved"); await viewField(fieldId); });
  onSubmit("lab-form", async (d) => { await post(`/fields/${fieldId}/lab-results`, d); toast("Lab result saved"); await viewField(fieldId); });
  onSubmit("advice-form", async (d) => {
    const body = { field_id: Number(fieldId), crop: d.crop, budget_band: d.budget_band, water: d.water, lang: lang() };
    if (d.reading_id) body.reading_id = Number(d.reading_id);
    const advice = await post("/advice", body);
    location.hash = `#/advice/${advice.rec_id}`;
  });
}

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
    <div class="card summary ${esc(trust.level)}">
      <p class="muted">${esc(capital(crop))} · pH ${esc(a.ph_input)} (${esc(a.ph_method_input)}) · ${esc(a.as_of_date)}</p>
      <h1 class="headline">${headline}</h1>
      ${sub ? `<p class="subline">${sub}</p>` : ""}
      <div class="sure"><span class="badge ${esc(trust.level)}">${esc(tPlain(`ui.trust.${trust.level}`))}</span>
        <span>${t("sum.sure")} ${sureText(a)}</span></div>
      ${a.borderline ? `<p class="notice info">${t("borderline")}</p>` : ""}
    </div>
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
    <button class="secondary sms-btn">${tPlain("ui.send_sms")}</button>
    <details class="card tech"><summary>${t("sum.details")}</summary>
      <p class="muted">${esc((trust.reasons || []).join("; "))}${a.texture && a.texture.value ? ` · texture ${esc(a.texture.value)} (${esc(a.texture.source)})` : ""}</p>
      <h3>${t("ui.why")}</h3>
      <table><tr><th>What was checked</th><th>Based on</th></tr>${whyRows(rules)}</table>
      ${a.unreviewed ? `<p class="muted">${t("ui.unconfirmed_rules")}</p>` : ""}
    </details>`;
  target.querySelector(".sms-btn").addEventListener("click", async () => {
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

function viewHelp() {
  $app.innerHTML = `
    <h1>How to take a soil sample</h1>
    <div class="card">
      <ol>
        <li>Divide the field into areas that look alike: soil colour, texture, slope, drainage, crop growth and management.</li>
        <li>In each area, take 15 to 20 small samples from different points and mix them in a clean plastic bucket. That makes one composite sample.</li>
        <li>Sample before planting. Do not sample just after putting on fertiliser or manure.</li>
        <li>Do not sample very dry, dusty soil, or soil that is saturated or under standing water. Wait for moderate moisture, not straight after heavy rain.</li>
        <li>Record the GPS position where you sample.</li>
      </ol>
      <p>Sample the top 0–20 cm of soil, the same depth as the soil map.</p>
      <p class="muted">Soil labs: ZARI Mount Makulu; University of Zambia, Soil Science.
        Source: agronomist questionnaire (K1–K4).</p>
    </div>`;
}

// ----- router -----

async function route() {
  const hash = location.hash || "#/home";
  const [, view, id] = hash.split("/");
  if (!store.get("token") && view !== "login") { location.hash = "#/login"; return; }
  document.getElementById("topbar").hidden = view === "login";
  document.querySelectorAll(".topbar nav a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#/${view}`));
  try {
    switch (view) {
      case "login": return viewLogin();
      case "new-field": return viewNewField(id);
      case "field": return await viewField(id);
      case "advice": return await viewAdvice(id);
      case "probe": return await viewProbe();
      case "live": return await viewLive(id);
      case "help": return viewHelp();
      case "fields": return await viewFields();
      default: return await viewHome();
    }
  } catch (error) { toast(error.message, true); }
}

document.getElementById("logout").addEventListener("click", () => {
  store.remove("token"); store.remove("user"); location.hash = "#/login";
});
document.getElementById("lang").addEventListener("change", () => {
  store.set("lang", lang());
  if (location.hash.startsWith("#/advice/")) route();
});
document.getElementById("lang").value = store.get("lang") || "en";
window.addEventListener("hashchange", route);
route();
