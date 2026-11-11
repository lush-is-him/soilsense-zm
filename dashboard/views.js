// SoilSense ZM screens for each role (self-testing model, Nov 2026).
//   farmer : tests their own soil, sees only their own fields, can ask for a lab test or a visit
//   officer: extension or lab staff; works the request list, sees the map of shared tests
//   admin  : accounts, overview and map of everything
// Uses the helpers in app.js (api, post, esc, toast, onSubmit, t, viewAdvice, viewLive, viewProbe).
"use strict";

const LANG_NAMES = { en: "English", ny: "Nyanja", toi: "Tonga" };
const ROLE_NAMES = { farmer: "Farmer", officer: "Extension / lab officer", admin: "Administrator" };
const NAV = {
  farmer: [["home", "Home"], ["measure", "Test my soil"], ["mine", "My fields"], ["referrals", "My requests"]],
  officer: [["home", "Home"], ["referrals", "Requests"], ["map", "Map"], ["fields", "Farmers"], ["probe", "Probe"]],
  admin: [["home", "Home"], ["map", "Map"], ["fields", "Farmers"], ["referrals", "Requests"], ["users", "Accounts"], ["probe", "Probe"]],
};

function me() { try { return JSON.parse(store.get("user")) || {}; } catch (error) { return {}; } }
const firstName = (user) => esc(((user.full_name || user.username || "").split(" ")[0]) || "there");
const patch = (path, data) => api(path, { method: "PATCH", body: JSON.stringify(data) });
const del = (path) => api(path, { method: "DELETE" });
const when = (sql) => (sql ? new Date(sql.replace(" ", "T") + (sql.includes("Z") || sql.includes("+") ? "" : "Z"))
  .toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");

function renderNav() {
  const user = me();
  const nav = document.getElementById("nav");
  nav.innerHTML = (NAV[user.role] || []).map(([view, label]) => `<a href="#/${view}">${label}</a>`).join("");
  const short = { farmer: "Farmer", officer: "Officer", admin: "Admin" }[user.role] || "";
  document.getElementById("whoami").textContent = user.role ? `${(user.full_name || user.username).split(" ")[0]} · ${short}` : "";
}

function probeState(devices) {
  const d = devices[0] || {};
  const c = d.latest_calibration;
  const connected = !!d.last_seen && (Date.now() - new Date(d.last_seen).getTime()) / 1000 < 20;
  const calToday = !!(c && c.accepted && new Date(c.date.replace(" ", "T") + "Z").toDateString() === new Date().toDateString());
  return { connected, calToday, calibration: c };
}

function probeStrip(state) {
  return `<a class="probe-strip ${state.connected && state.calToday ? "ok" : "warn"}" href="#/probe">
    <span class="dot ${state.connected ? "on" : "off"}"></span>
    <span>Probe: <strong>${state.connected ? "connected" : "not connected"}</strong> ·
      ${state.calToday ? "calibrated today" : state.calibration && state.calibration.accepted ? "not calibrated today" : "not calibrated"}</span>
    <span class="go">›</span></a>`;
}

const phClass = (ph) => (ph == null ? "none" : ph < 5.5 ? "acid" : ph <= 7.0 ? "good" : "alkaline");
const phWord = (ph) => ({ acid: "acidic", good: "good range", alkaline: "alkaline", none: "not tested" })[phClass(ph)];

// ----- login and sign-up ---------------------------------------------------------

function viewLogin() {
  $app.innerHTML = `
    <div class="card hero">
      <h1>SoilSense ZM</h1>
      <p>Test your soil yourself, today, and get advice you can act on. If the result is unusual,
        the system tells you to confirm it at a soil lab.</p>
      <form id="login-form">
        <label for="username">Username</label>
        <input id="username" name="username" autocomplete="username" required>
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required>
        <button type="submit">Log in</button>
      </form>
      <p class="center">New farmer? <a href="#/signup"><strong>Create an account</strong></a></p>
    </div>
    <div class="card">
      <h2>Three ways to get soil advice</h2>
      <ol class="ways">
        <li><strong>Test it yourself</strong> with the SoilSense probe: same-day advice.</li>
        <li><strong>Ask an extension officer</strong> to come and test for you.</li>
        <li><strong>Take a sample to a soil lab</strong> (for example ZARI Mount Makulu) for a full report.</li>
      </ol>
      <p class="muted">Extension and lab officers get their accounts from the administrator.</p>
    </div>`;
  onSubmit("login-form", async (data) => {
    const result = await post("/auth/login", data);
    store.set("token", result.token);
    store.set("user", JSON.stringify(result.user));
    location.hash = "#/home";
  });
}

function viewSignup() {
  $app.innerHTML = `
    <p><a href="#/login">← Log in</a></p>
    <h1>Create your farmer account</h1>
    <div class="card">
      <form id="signup-form">
        <label for="full_name">Your name</label><input id="full_name" name="full_name" required maxlength="80">
        <div class="row">
          <div><label for="username">Username</label><input id="username" name="username" required minlength="3"
            pattern="[A-Za-z0-9_.\\-]+" autocomplete="username"><small class="muted">Letters, numbers, . _ -</small></div>
          <div><label for="password">Password</label><input id="password" name="password" type="password" required
            minlength="8" autocomplete="new-password"><small class="muted">At least 8 characters</small></div>
        </div>
        <label for="village">Village or area</label><input id="village" name="village" maxlength="80" placeholder="e.g. Shimabala">
        <label for="preferred_language">Language for advice</label>
        <select id="preferred_language" name="preferred_language">
          <option value="en">English</option><option value="toi">Tonga</option><option value="ny">Nyanja</option></select>
        <label class="check"><input type="checkbox" name="share_consent" checked>
          Share my test results and field location with extension and lab officers, so they can help me and
          add my soil to their map. (You can change this later.)</label>
        <label class="check"><input type="checkbox" name="sms_consent" id="sms_consent"> Send me advice by SMS</label>
        <label for="phone">Phone number (only if you want SMS)</label>
        <input id="phone" name="phone" type="tel" placeholder="+260..." pattern="\\+?[0-9]{9,15}">
        <button type="submit">Create account</button>
      </form>
    </div>`;
  onSubmit("signup-form", async (data) => {
    if (!data.sms_consent) delete data.phone;
    const result = await post("/auth/signup", data);
    store.set("token", result.token);
    store.set("user", JSON.stringify(result.user));
    toast("Welcome! Add your first field, then test your soil.");
    location.hash = "#/home";
  });
}

// ----- home, per role -------------------------------------------------------------

async function viewHome() {
  const user = me();
  if (user.role === "farmer") return farmerHome(user);
  if (user.role === "admin") return adminHome(user);
  return officerHome(user);
}

async function farmerHome(user) {
  const [profile, devices, requests] = await Promise.all([
    api("/farmers/me"), api("/devices"), api("/referrals"), loadStrings(lang())]);
  const state = probeState(devices);
  $app.innerHTML = `
    <h1>Hello, ${firstName(user)}</h1>
    ${probeStrip(state)}
    <a class="button big-btn" href="#/measure">Test my soil</a>
    <div class="card">
      <div class="section-head"><h2>My fields</h2><a href="#/new-field/${profile.farmer_id}">+ Add a field</a></div>
      ${fieldCards(profile.fields, "Add your first field: stand in it and save its GPS position.")}
    </div>
    ${requests.length ? `<div class="card"><h2>My requests</h2>${referralList(requests, user)}</div>` : ""}
    <div class="card">
      <h2>Need help?</h2>
      <p>Open a field and use <strong>Ask for help</strong> to ask an extension officer to visit, or to
        request a lab test at ZARI Mount Makulu or another soil lab.</p>
    </div>`;
  bindReferralActions(user);
}

function fieldCards(fields, empty) {
  if (!fields.length) return `<p class="muted">${empty}</p>`;
  return `<ul class="field-list">${fields.map((f) => `
    <li><a class="field-link" href="#/field/${f.field_id}">
      <span><strong>${esc(f.name)}</strong><br><small class="muted">${f.location_source === "gps" ? `GPS ±${esc(f.gps_accuracy_m)} m` : "manual pin"}</small></span>
      <span class="ph-chip ${phClass(f.lab_ph ?? f.latest_ph)}">${f.lab_ph != null ? `lab pH ${esc(f.lab_ph)}`
        : f.latest_ph != null ? `pH ${esc(f.latest_ph)}` : "not tested"}</span></a></li>`).join("")}</ul>`;
}

async function officerHome(user) {
  const [requests, points, devices] = await Promise.all([api("/referrals"), api("/map/points"), api("/devices")]);
  const tested = points.filter((p) => p.probe_ph != null || p.lab_ph != null).length;
  const labs = requests.filter((r) => r.kind === "lab").length;
  $app.innerHTML = `
    <h1>Hello, ${firstName(user)}</h1>
    <div class="stats">
      <a class="stat" href="#/referrals"><strong>${requests.length}</strong><span>open requests</span></a>
      <a class="stat" href="#/referrals"><strong>${labs}</strong><span>lab tests asked</span></a>
      <a class="stat" href="#/map"><strong>${tested}</strong><span>tested fields on the map</span></a>
    </div>
    ${probeStrip(probeState(devices))}
    <div class="tiles">
      <a class="tile primary" href="#/referrals"><span class="tile-icon" aria-hidden="true">📋</span><strong>Requests</strong><span>Visits and lab tests farmers asked for</span></a>
      <a class="tile" href="#/map"><span class="tile-icon" aria-hidden="true">🗺️</span><strong>Map</strong><span>Every shared soil test</span></a>
      <a class="tile" href="#/fields"><span class="tile-icon" aria-hidden="true">👥</span><strong>Farmers</strong><span>Register a farmer without a phone</span></a>
      <a class="tile" href="#/measure"><span class="tile-icon" aria-hidden="true">🌱</span><strong>Test for a farmer</strong><span>Guided test with the probe</span></a>
    </div>
    ${requests.length ? `<div class="card"><h2>Latest requests</h2>${referralList(requests.slice(0, 5), user)}</div>` : ""}`;
  bindReferralActions(user);
}

async function adminHome(user) {
  const [o, devices] = await Promise.all([api("/overview"), api("/devices")]);
  const n = (obj, key) => (obj && obj[key]) || 0;
  $app.innerHTML = `
    <h1>Overview</h1>
    <div class="stats">
      <div class="stat"><strong>${o.farmers}</strong><span>farmers (${o.farmers_self_testing} test themselves)</span></div>
      <div class="stat"><strong>${o.fields}</strong><span>fields</span></div>
      <div class="stat"><strong>${n(o.readings, "accepted")}</strong><span>readings accepted · ${n(o.readings, "rejected")} rejected</span></div>
      <div class="stat"><strong>${o.referrals_open}</strong><span>open requests</span></div>
      <div class="stat"><strong>${o.lab_results}</strong><span>lab results</span></div>
      <div class="stat"><strong>${n(o.users, "officer")}</strong><span>officers · ${n(o.users, "farmer")} farmer accounts</span></div>
    </div>
    <div class="card"><h2>Advice given, by confidence</h2>
      <div class="bars">${["high", "moderate", "low", "none"].map((k) => {
        const total = Object.values(o.advice || {}).reduce((a, b) => a + b, 0) || 1;
        return `<div class="bar-row"><span>${k}</span><div class="bar"><div class="bar-fill ${k}" style="width:${(100 * n(o.advice, k) / total).toFixed(0)}%"></div></div><b>${n(o.advice, k)}</b></div>`;
      }).join("")}</div></div>
    ${probeStrip(probeState(devices))}
    <div class="tiles">
      <a class="tile primary" href="#/map"><span class="tile-icon" aria-hidden="true">🗺️</span><strong>Map</strong><span>All soil tests</span></a>
      <a class="tile" href="#/users"><span class="tile-icon" aria-hidden="true">🔑</span><strong>Accounts</strong><span>Officers, admins, farmers</span></a>
      <a class="tile" href="#/fields"><span class="tile-icon" aria-hidden="true">👥</span><strong>Farmers</strong><span>Profiles and fields</span></a>
      <a class="tile" href="#/referrals"><span class="tile-icon" aria-hidden="true">📋</span><strong>Requests</strong><span>Visits and lab tests</span></a>
    </div>
    <div class="card"><h2>Recent calibrations</h2>
      ${o.calibrations.length ? `<table><tr><th>When</th><th>Slope</th><th>Result</th></tr>${o.calibrations.slice(0, 5).map((c) => `
        <tr><td>${esc(when(c.date))}</td><td>${esc(c.slope_pct)}%</td><td><span class="badge ${c.accepted ? "accepted" : "rejected"}">${c.accepted ? "accepted" : "failed"}</span></td></tr>`).join("")}</table>`
        : '<p class="muted">No calibrations yet.</p>'}</div>`;
}

// ----- farmers ---------------------------------------------------------------------

async function viewFarmers() {
  const user = me();
  if (user.role === "farmer") { location.hash = "#/mine"; return; }
  const farmers = await api("/farmers");
  $app.innerHTML = `
    <h1>Farmers</h1>
    <input id="farmer-search" type="search" placeholder="Search by name or village" aria-label="Search farmers">
    <ul class="field-list" id="farmer-list">${farmers.map((f) => `
      <li data-q="${esc(`${f.alias} ${f.village || ""}`.toLowerCase())}"><a class="field-link" href="#/farmer/${f.farmer_id}">
        <span><strong>${esc(f.alias)}</strong>${f.village ? ` · ${esc(f.village)}` : ""}<br>
          <small class="muted">${f.field_count} field${f.field_count === 1 ? "" : "s"}
          ${f.own_account ? " · tests themselves" : ` · registered by ${esc(f.registered_by || "—")}`}</small></span>
        <span>${f.mine && !f.own_account ? '<span class="badge moderate">yours</span>' : ""}
          ${!f.share_consent && !f.mine ? '<span class="badge low">asked for help</span>' : ""}</span></a></li>`).join("")}</ul>
    ${farmers.length ? "" : '<div class="card"><p class="muted">No farmers you can see yet.</p></div>'}
    <details class="card">
      <summary>Register a farmer who has no phone or account</summary>
      ${farmerForm({}, "farmer-form", "Register farmer")}
    </details>`;
  document.getElementById("farmer-search").addEventListener("input", (event) => {
    const q = event.target.value.toLowerCase();
    document.querySelectorAll("#farmer-list li").forEach((li) => { li.hidden = !li.dataset.q.includes(q); });
  });
  onSubmit("farmer-form", async (data) => {
    if (!data.sms_consent) delete data.phone;
    const farmer = await post("/farmers", data);
    toast("Farmer registered");
    location.hash = `#/farmer/${farmer.farmer_id}`;
  });
}

function farmerForm(f, id, label) {
  return `<form id="${id}">
    <label for="${id}-alias">Name (or a nickname)</label>
    <input id="${id}-alias" name="alias" required maxlength="60" value="${esc(f.alias || "")}">
    <label for="${id}-village">Village or area</label>
    <input id="${id}-village" name="village" maxlength="80" value="${esc(f.village || "")}">
    <label for="${id}-lang">Language for advice</label>
    <select id="${id}-lang" name="preferred_language">${Object.entries(LANG_NAMES).map(([code, name]) =>
      `<option value="${code}" ${f.preferred_language === code ? "selected" : ""}>${name}</option>`).join("")}</select>
    <label class="check"><input type="checkbox" name="share_consent" ${f.share_consent ? "checked" : ""}>
      Share test results and field locations with extension and lab officers</label>
    <label class="check"><input type="checkbox" name="sms_consent" ${f.sms_consent ? "checked" : ""}> Agrees to receive advice by SMS</label>
    <label for="${id}-phone">Phone (only with SMS consent)</label>
    <input id="${id}-phone" name="phone" type="tel" placeholder="+260..." value="${esc(f.phone || "")}">
    <button type="submit">${label}</button>
  </form>`;
}

async function viewFarmer(farmerId) {
  const user = me();
  const farmer = await api(`/farmers/${farmerId}`);
  const own = user.role === "farmer";
  $app.innerHTML = `
    ${own ? "" : `<p><a href="#/fields">← Farmers</a></p>`}
    <h1>${own ? "My fields" : esc(farmer.alias)}</h1>
    <div class="card">
      <div class="section-head"><h2>Fields</h2><a href="#/new-field/${farmer.farmer_id}">+ Add a field</a></div>
      ${fieldCards(farmer.fields, own ? "Add your first field: stand in it and save its GPS position." : "No fields yet.")}
    </div>
    <div class="card profile">
      <h2>${own ? "My profile" : "Profile"}</h2>
      <dl>
        <dt>Name</dt><dd>${esc(farmer.alias)}</dd>
        <dt>Village</dt><dd>${esc(farmer.village || "—")}</dd>
        <dt>Language</dt><dd>${esc(LANG_NAMES[farmer.preferred_language])}</dd>
        <dt>SMS</dt><dd>${farmer.sms_consent ? `yes, ${esc(farmer.phone || "")}` : "no"}</dd>
        <dt>Shares results</dt><dd>${farmer.share_consent ? "yes, with extension and lab officers" : "no"}</dd>
        <dt>Account</dt><dd>${farmer.own_account ? "tests their own soil" : "kept by an officer"}</dd>
      </dl>
      ${farmer.can_edit ? `<details><summary>Edit ${own ? "my " : ""}profile</summary>${farmerForm(farmer, "profile-form", "Save")}</details>`
        : `<p class="muted">${farmer.own_account ? "This farmer manages their own profile." : "Only the officer who registered this farmer, or an admin, can edit it."}</p>`}
    </div>`;
  if (farmer.can_edit) {
    onSubmit("profile-form", async (data) => {
      if (!data.sms_consent) data.phone = null;
      await patch(`/farmers/${farmer.farmer_id}`, data);
      toast("Profile saved");
      await viewFarmer(farmerId);
    });
  }
}

async function viewMine() {
  const user = me();
  if (user.role !== "farmer" || !user.farmer_id) { location.hash = "#/fields"; return; }
  return viewFarmer(user.farmer_id);
}

function viewNewField(farmerId) {
  $app.innerHTML = `
    <p><a href="javascript:history.back()">← Back</a></p>
    <h1>Add a field</h1>
    <div class="card">
      <form id="field-form">
        <label for="name">Field name</label>
        <input id="name" name="name" required maxlength="60" placeholder="e.g. Plot by the road">
        <p class="muted">Stand in the middle of the field and press <strong>Get GPS position</strong>. It must be ${GPS_MAX_M} m or better.
          The soil map is checked for this exact spot, so test soil taken from here.</p>
        <div class="actions">
          <button type="button" id="gps-btn">Get GPS position</button>
          <button type="button" class="secondary" id="manual-btn">Type coordinates instead</button>
        </div>
        <p id="gps-status" class="muted"></p>
        <div class="row">
          <div><label for="lat">Latitude</label><input id="lat" name="lat" type="number" step="any" required readonly></div>
          <div><label for="lon">Longitude</label><input id="lon" name="lon" type="number" step="any" required readonly></div>
        </div>
        <input type="hidden" name="gps_accuracy_m" id="gps_accuracy_m">
        <input type="hidden" name="location_source" id="location_source" value="gps">
        <label for="area_lima">Size in lima (optional)</label>
        <input id="area_lima" name="area_lima" type="number" step="any" min="0">
        <button type="submit" id="save-field" disabled>Save field</button>
      </form>
    </div>`;
  const status = document.getElementById("gps-status");
  const save = document.getElementById("save-field");
  const lat = document.getElementById("lat");
  const lon = document.getElementById("lon");
  document.getElementById("gps-btn").addEventListener("click", () => {
    if (!navigator.geolocation) { status.textContent = "This device cannot give a GPS position. Type the coordinates."; return; }
    status.textContent = "Getting your position…";
    navigator.geolocation.getCurrentPosition((pos) => {
      const acc = Math.round(pos.coords.accuracy);
      lat.value = pos.coords.latitude.toFixed(6);
      lon.value = pos.coords.longitude.toFixed(6);
      document.getElementById("gps_accuracy_m").value = acc;
      document.getElementById("location_source").value = "gps";
      const ok = acc <= GPS_MAX_M;
      status.textContent = ok ? `Position accepted: ±${acc} m.` : `Position is ±${acc} m, worse than ${GPS_MAX_M} m. Wait a moment and try again.`;
      save.disabled = !ok;
    }, (err) => { status.textContent = `GPS failed: ${err.message}. Try again, or type the coordinates.`; },
    { enableHighAccuracy: true, timeout: 30000, maximumAge: 0 });
  });
  document.getElementById("manual-btn").addEventListener("click", () => {
    lat.readOnly = false; lon.readOnly = false;
    document.getElementById("location_source").value = "manual";
    document.getElementById("gps_accuracy_m").value = "";
    status.textContent = "Typed coordinates are less certain: advice for this field gets low confidence.";
    save.disabled = false;
  });
  onSubmit("field-form", async (data) => {
    data.farmer_id = Number(farmerId);
    const field = await post("/fields", data);
    toast("Field saved");
    location.hash = `#/field/${field.field_id}`;
  });
}

// ----- one field -----------------------------------------------------------------------

function readingExplanation(r) {
  const reasons = (r.quality_reasons || []).join(" ");
  if (r.quality_status === "accepted") return "";
  if (reasons.includes("plausible")) return "This number is outside what soils have. It is almost certainly the probe: rinse it, check it in the pH 7.00 buffer, recalibrate, and measure again.";
  if (reasons.includes("calibration")) return "The probe had no valid calibration. Calibrate it first.";
  if (reasons.includes("temperature")) return "The sample was much warmer or cooler than the buffers. Let everything stand in the same room, then measure again.";
  if (reasons.includes("spread")) return "The probe had not settled. Stir, wait 2 minutes and measure again.";
  return "";
}

async function viewField(fieldId) {
  const user = me();
  const [field, history, devices] = await Promise.all([
    api(`/fields/${fieldId}`), api(`/fields/${fieldId}/history`), api("/devices"), loadStrings(lang())]);
  const farmer = await api(`/farmers/${field.farmer_id}`);
  let mapHtml;
  try {
    const m = await api(`/fields/${fieldId}/map-estimate`);
    mapHtml = `pH ${esc(m.ph_mean)} ± ${esc(m.ph_sd)} (water), texture ${esc(m.texture || "unknown")}`;
  } catch (error) { mapHtml = esc(error.message); }
  const own = user.role === "farmer";
  const openRefs = history.referrals.filter((r) => r.status === "open" || r.status === "in_progress");
  const openLab = openRefs.filter((r) => r.kind === "lab");
  const readingOptions = history.readings.filter((r) => r.quality_status === "accepted").map((r) =>
    `<option value="${r.reading_id}">pH ${esc(r.ph_water)} · ${esc(when(r.ts))}</option>`).join("");
  const latest = history.readings.find((r) => r.quality_status === "accepted");

  $app.innerHTML = `
    <p>${own ? `<a href="#/mine">← My fields</a>` : `<a href="#/farmer/${farmer.farmer_id}">← ${esc(farmer.alias)}</a>`}</p>
    <h1>${esc(field.name)}</h1>
    <p class="muted">${own ? "" : `Farmer: <strong>${esc(farmer.alias)}</strong>${farmer.village ? `, ${esc(farmer.village)}` : ""} · `}
      ${field.location_source === "gps" ? `GPS ±${esc(field.gps_accuracy_m)} m` : "typed coordinates"} · soil map: ${mapHtml}</p>
    <a class="button big-btn" href="#/live/${esc(fieldId)}">Measure with the probe</a>
    ${openRefs.length ? `<div class="card notice info">${openRefs.map((r) => `<p><strong>${r.kind === "lab" ? "Lab test requested" : "Officer visit requested"}</strong>
      · ${esc(r.status.replace("_", " "))} · ${esc(when(r.created_at))}</p>`).join("")}</div>` : ""}

    <div class="card">
      <h2>Get advice</h2>
      ${readingOptions || history.lab_results.length ? `<form id="advice-form">
        <label for="reading_id">Use</label>
        <select id="reading_id" name="reading_id">${readingOptions}${history.lab_results.length ? '<option value="">the lab result</option>' : ""}</select>
        <div class="row">
          <div><label for="crop">Crop</label><select id="crop" name="crop">${CROPS.map((c) => `<option value="${c}">${esc(capital(cropName(c)))}</option>`).join("")}</select></div>
          <div><label for="budget_band">Money available</label>
            <select id="budget_band" name="budget_band"><option value="low">Little</option><option value="medium">Some</option></select></div>
          <div><label for="water">Water</label>
            <select id="water" name="water"><option value="rainfed">Rain only</option><option value="irrigated">Irrigated</option></select></div>
        </div>
        <button type="submit">Get advice</button>
      </form>` : `<p class="muted">Measure the soil first, or enter a lab result.</p>`}
    </div>

    <div class="card">
      <h2>Ask for help</h2>
      <p class="muted">${latest ? `Latest probe reading: pH ${esc(latest.ph_water)}.` : ""} If you are not sure about the result, or cannot test yourself:</p>
      <div class="actions">
        <button class="secondary" id="ask-visit">Ask an officer to visit</button>
        <button class="secondary" id="ask-lab">Request a lab test</button>
      </div>
    </div>

    ${history.readings.length ? `<div class="card"><h2>Readings</h2><ul class="list">${history.readings.map((r) => `
      <li><span class="badge ${esc(r.quality_status)}">${r.quality_status === "accepted" ? "accepted" : "rejected"}</span>
        ${r.ph_water != null ? `pH ${esc(r.ph_water)}` : ""} <small>${esc(when(r.ts))}${r.temp_c != null ? ` · ${esc(r.temp_c)} °C` : ""}</small>
        ${readingExplanation(r) ? `<br><small>${esc(readingExplanation(r))}</small>` : ""}</li>`).join("")}</ul></div>` : ""}
    ${history.recommendations.length ? `<div class="card"><h2>Earlier advice</h2><ul class="list">${history.recommendations.map((r) => `
      <li><a href="#/advice/${r.rec_id}">${esc(capital(cropName(r.crop)))} · ${esc(r.as_of_date)}</a>
        <span class="badge ${esc(r.trust_level)}">${esc(r.trust_level)}</span></li>`).join("")}</ul></div>` : ""}
    ${history.lab_results.length ? `<div class="card"><h2>Lab results</h2><ul class="list">${history.lab_results.map((l) => `
      <li>pH ${esc(l.ph)} (${l.ph_method === "cacl2" ? "CaCl₂" : "water"})${l.texture ? ` · ${esc(l.texture)}` : ""}
        <small>${esc(l.lab_name || "")} ${esc(l.date || "")}</small></li>`).join("")}</ul></div>` : ""}

    <details class="card" ${openLab.length && !own ? "open" : ""}>
      <summary>${own ? "I have a lab report" : "Enter a lab result"}</summary>
      <form id="lab-form">
        ${openLab.length ? `<label for="referral_id">For request</label><select id="referral_id" name="referral_id">
          ${openLab.map((r) => `<option value="${r.referral_id}">Lab test asked ${esc(when(r.created_at))}</option>`).join("")}<option value="">none</option></select>` : ""}
        <div class="row">
          <div><label for="ph">pH</label><input id="ph" name="ph" type="number" step="0.01" min="2" max="11" required></div>
          <div><label for="ph_method">Method</label>
            <select id="ph_method" name="ph_method" required><option value="water">Water</option><option value="cacl2">CaCl₂</option></select></div>
        </div>
        <label for="texture">Texture (as on the report)</label><input id="texture" name="texture" placeholder="e.g. Sandy Clay Loam">
        <label for="lab_name">Lab</label><input id="lab_name" name="lab_name" placeholder="e.g. ZARI Mount Makulu">
        <label for="date">Date</label><input id="date" name="date" type="date">
        <button type="submit">Save lab result</button>
      </form>
    </details>
    <details class="card">
      <summary>Field checks: texture by feel, waterlogging</summary>
      <form id="check-form">
        <label for="texture_by_feel">Texture by feel</label>
        <select id="texture_by_feel" name="texture_by_feel">
          <option value="">Not checked</option><option value="sandy">Sandy (gritty, falls apart)</option>
          <option value="loamy">Loamy (soft, holds shape loosely)</option><option value="clay">Clay (sticky, makes a ribbon)</option>
        </select>
        <label for="previous_crop">Previous crop</label><input id="previous_crop" name="previous_crop">
        <label class="check"><input type="checkbox" name="waterlogging"> Waterlogged in the rains</label>
        <label class="check"><input type="checkbox" name="manure_available"> Manure available</label>
        <button type="submit">Save field check</button>
      </form>
    </details>
    <details class="card">
      <summary>Type a reading by hand</summary>
      <form id="reading-form">
        <input type="hidden" name="device_id" value="${esc((devices[0] || {}).device_id || "probe-1")}">
        <p class="muted">Three readings of the same soil-water mix, within 0.1 of each other.</p>
        <div class="row">
          <div><label for="r1">pH 1</label><input id="r1" name="r1" type="number" step="0.01" required></div>
          <div><label for="r2">pH 2</label><input id="r2" name="r2" type="number" step="0.01" required></div>
          <div><label for="r3">pH 3</label><input id="r3" name="r3" type="number" step="0.01" required></div>
          <div><label for="temp_c">Temp °C</label><input id="temp_c" name="temp_c" type="number" step="0.1" required></div>
        </div>
        <button type="submit">Save reading</button>
      </form>
    </details>
    ${farmer.can_edit ? `<details class="card">
      <summary>Rename, move or delete this field</summary>
      <form id="edit-field-form">
        <label for="ef-name">Name</label><input id="ef-name" name="name" value="${esc(field.name)}" required maxlength="60">
        <div class="row">
          <div><label for="ef-lat">Latitude</label><input id="ef-lat" name="lat" type="number" step="any" value="${esc(field.lat)}"></div>
          <div><label for="ef-lon">Longitude</label><input id="ef-lon" name="lon" type="number" step="any" value="${esc(field.lon)}"></div>
        </div>
        <p class="muted">Changing the coordinates by hand marks the location as typed (low confidence).</p>
        <button type="submit">Save changes</button>
      </form>
      <button class="danger" id="delete-field">Delete this field and its history</button>
    </details>` : ""}`;

  const ask = async (kind) => {
    const reason = kind === "lab" ? "Confirm the soil pH with a lab test" : "Please come and test my soil";
    await post("/referrals", { field_id: Number(fieldId), kind, reason, reading_id: latest ? latest.reading_id : null });
    toast(kind === "lab" ? "Lab test requested. An officer will contact you about taking the sample in."
      : "Visit requested. An extension officer will contact you.");
    await viewField(fieldId);
  };
  document.getElementById("ask-visit").addEventListener("click", () => ask("visit").catch((e) => toast(e.message, true)));
  document.getElementById("ask-lab").addEventListener("click", () => ask("lab").catch((e) => toast(e.message, true)));
  if (document.getElementById("advice-form")) {
    onSubmit("advice-form", async (d) => {
      const body = { field_id: Number(fieldId), crop: d.crop, budget_band: d.budget_band, water: d.water, lang: lang() };
      if (d.reading_id) body.reading_id = Number(d.reading_id);
      const advice = await post("/advice", body);
      location.hash = `#/advice/${advice.rec_id}`;
    });
  }
  onSubmit("reading-form", async (d) => {
    const reading = await post("/readings", { field_id: Number(fieldId), device_id: d.device_id,
      replicates_ph: [d.r1, d.r2, d.r3], temp_c: d.temp_c });
    toast(reading.quality_status === "accepted" ? `Reading accepted: pH ${reading.ph_water}`
      : `Reading rejected: ${readingExplanation(reading) || reading.quality_reasons.join("; ")}`, reading.quality_status !== "accepted");
    await viewField(fieldId);
  });
  onSubmit("check-form", async (d) => { await post(`/fields/${fieldId}/checks`, d); toast("Field check saved"); await viewField(fieldId); });
  onSubmit("lab-form", async (d) => {
    if (d.referral_id) d.referral_id = Number(d.referral_id); else delete d.referral_id;
    await post(`/fields/${fieldId}/lab-results`, d);
    toast("Lab result saved. Ask for advice to use it.");
    await viewField(fieldId);
  });
  if (farmer.can_edit) {
    onSubmit("edit-field-form", async (d) => {
      const changes = { name: d.name };
      if (Number(d.lat) !== Number(field.lat) || Number(d.lon) !== Number(field.lon)) {
        Object.assign(changes, { lat: Number(d.lat), lon: Number(d.lon), location_source: "manual" });
      }
      await patch(`/fields/${fieldId}`, changes);
      toast("Field updated");
      await viewField(fieldId);
    });
    document.getElementById("delete-field").addEventListener("click", async () => {
      if (!confirm(`Delete "${field.name}" with all its readings and advice? This cannot be undone.`)) return;
      try { await del(`/fields/${fieldId}`); toast("Field deleted"); location.hash = own ? "#/mine" : `#/farmer/${farmer.farmer_id}`; }
      catch (error) { toast(error.message, true); }
    });
  }
}

// ----- guided soil test --------------------------------------------------------------

const STEPS = [
  { title: "Walk the field in a zig-zag", anim: "sample", body: `<p>Walk across the field in a zig-zag and stop at <strong>15 to 20 spots</strong>.
      Skip spots near trees, anthills, paths, or where manure or fertiliser was just put.</p>` },
  { title: "Dig to 20 cm and mix in one bucket", anim: "bucket", body: `<p>At each spot dig a small hole and take a thin slice of soil from the
      surface down to <strong>20 cm</strong> (about the length of your hand). Put all the slices in one clean bucket and mix well.</p>` },
  { title: "Dry, crush and sieve", anim: "sieve", body: `<p>Spread a few handfuls in the shade to dry for 2 to 3 days. Crush the lumps and
      shake the soil through a sieve or mosquito net. Keep the rest in a labelled bag in case you need a lab test.</p>` },
  { title: "Calibrate the probe (once a day)", anim: "calibrate", calibrate: true, body: `<p>Put the probe in the <strong>pH 7.00</strong> buffer,
      rinse it in clean water, then put it in the <strong>pH 4.00</strong> buffer, following the black window on the laptop
      (double-click <strong>START DEMO</strong> and answer <strong>Y</strong>).</p>` },
  { title: "Prepare the cup", anim: "cup", body: `<p>Put <strong>10 ml of soil</strong> (one medicine cup) and <strong>30 ml of clean water</strong>
      in a clean cup. Stir for a minute, wait 10 minutes, and stir again just before measuring.</p>` },
  { title: "Choose the field and measure", anim: "probe", choose: true, body: `<p>Choose the field the soil came from. Then put the
      probe in the cup: the pH appears on the screen, and the advice follows.</p>` },
];

async function viewMeasure(stepParam) {
  const user = me();
  let step = Math.min(Math.max(Number(stepParam) || 1, 1), STEPS.length);
  const s = STEPS[step - 1];
  let extra = "";
  if (s.calibrate) {
    const state = probeState(await api("/devices"));
    extra = state.calToday ? `<p class="notice info"><strong>Done today.</strong> The probe was calibrated today: you can skip this step.</p>`
      : `<p class="notice"><strong>Not calibrated today.</strong> Calibrate before measuring, or the reading will be refused.</p>
         <p><a href="#/probe">Probe status</a></p>`;
  }
  if (s.choose) {
    let fields;
    if (user.role === "farmer") fields = (await api("/farmers/me")).fields.map((f) => ({ ...f, farmer: "" }));
    else fields = (await api("/map/points")).map((p) => ({ field_id: p.field_id, name: p.field, farmer: p.farmer }));
    extra = fields.length ? `<ul class="field-list">${fields.map((f) => `
      <li><a class="field-link" href="#/live/${f.field_id}"><span><strong>${esc(f.name)}</strong>${f.farmer ? `<br><small class="muted">${esc(f.farmer)}</small>` : ""}</span>
        <span class="go">Measure ›</span></a></li>`).join("")}</ul>`
      : `<p>No field yet. ${user.role === "farmer" ? `<a href="#/new-field/${user.farmer_id}">Add your field</a> first (stand in it to save its position).`
        : `<a href="#/fields">Open a farmer</a> and add their field first.`}</p>`;
  }
  $app.innerHTML = `
    <h1>${user.role === "farmer" ? "Test my soil" : "Guided soil test"}</h1>
    <ol class="stepper" aria-label="Steps">${STEPS.map((x, i) => `<li class="${i + 1 === step ? "now" : i + 1 < step ? "done" : ""}">
      <a href="#/measure/${i + 1}" aria-label="Step ${i + 1}: ${esc(x.title)}">${i + 1}</a></li>`).join("")}</ol>
    <div class="card step">
      <p class="muted">Step ${step} of ${STEPS.length}</p>
      <h2>${s.title}</h2>
      <div class="anim-box">${ANIM[s.anim]}</div>
      ${s.body}
      ${extra}
      <div class="actions step-nav">
        ${step > 1 ? `<a class="button secondary-btn" href="#/measure/${step - 1}">← Back</a>` : "<span></span>"}
        ${step < STEPS.length ? `<a class="button" href="#/measure/${step + 1}">Next →</a>` : ""}
      </div>
    </div>`;
}

// ----- requests (referrals) -----------------------------------------------------------

function referralList(items, user) {
  if (!items.length) return '<p class="muted">No requests.</p>';
  const staff = user.role !== "farmer";
  return `<ul class="list referrals">${items.map((r) => `
    <li data-ref="${r.referral_id}">
      <div><span class="badge ${r.kind === "lab" ? "moderate" : "low"}">${r.kind === "lab" ? "Lab test" : "Visit"}</span>
        <strong>${esc(staff ? r.farmer : r.field)}</strong>${staff ? ` · ${esc(r.field)}${r.village ? `, ${esc(r.village)}` : ""}` : ""}
        <span class="status ${esc(r.status)}">${esc(r.status.replace("_", " "))}</span></div>
      <small class="muted">${esc(when(r.created_at))}${r.reading_ph != null ? ` · probe pH ${esc(r.reading_ph)}` : ""}${r.reason ? ` · ${esc(r.reason)}` : ""}
        ${staff && r.phone ? ` · ☎ ${esc(r.phone)}` : ""}${r.handled_by_name ? ` · handled by ${esc(r.handled_by_name)}` : ""}</small>
      <div class="actions small">
        <a href="#/field/${r.field_id}">Open field</a>
        ${staff && r.status === "open" ? `<button class="link" data-act="in_progress">Start</button>` : ""}
        ${staff && (r.status === "open" || r.status === "in_progress") && r.kind === "visit" ? `<button class="link" data-act="done">Mark done</button>` : ""}
        ${staff && r.kind === "lab" && r.status !== "done" && r.status !== "cancelled" ? `<a href="#/field/${r.field_id}">Enter lab result</a>` : ""}
        ${r.status === "open" || r.status === "in_progress" ? `<button class="link" data-act="cancelled">Cancel</button>` : ""}
      </div>
    </li>`).join("")}</ul>`;
}

function bindReferralActions() {
  document.querySelectorAll("[data-ref] [data-act]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.closest("[data-ref]").dataset.ref;
      try { await patch(`/referrals/${id}`, { status: button.dataset.act }); toast("Request updated"); route(); }
      catch (error) { toast(error.message, true); }
    });
  });
}

async function viewReferrals(filter) {
  const user = me();
  const status = filter === "all" ? "all" : "active";
  const items = await api(`/referrals?status=${status}`);
  $app.innerHTML = `
    <h1>${user.role === "farmer" ? "My requests" : "Requests"}</h1>
    <p class="tabs"><a class="${status === "active" ? "on" : ""}" href="#/referrals">Open</a>
      <a class="${status === "all" ? "on" : ""}" href="#/referrals/all">All</a></p>
    ${user.role === "farmer" ? "" : `<p class="muted">Farmers who asked for a visit, or for a lab test to confirm their own reading.
      For a lab test: arrange the sample, then open the field and enter the lab result; the farmer’s advice then has high confidence.</p>`}
    <div class="card">${referralList(items, user)}</div>`;
  bindReferralActions();
}

// ----- map -------------------------------------------------------------------------------

function loadLeaflet() {
  if (window.L) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const css = document.createElement("link");
    css.rel = "stylesheet"; css.href = "/static/vendor/leaflet/leaflet.css";
    document.head.appendChild(css);
    const js = document.createElement("script");
    js.src = "/static/vendor/leaflet/leaflet.js";
    js.onload = resolve; js.onerror = () => reject(new Error("Map library failed to load"));
    document.head.appendChild(js);
  });
}

async function viewMap() {
  const user = me();
  const [points] = await Promise.all([api("/map/points"), loadLeaflet()]);
  const tested = points.filter((p) => p.probe_ph != null || p.lab_ph != null);
  $app.innerHTML = `
    <h1>Soil map</h1>
    <p class="muted">${user.role === "admin" ? "Every field in the system." : "Fields of farmers who share their results, or asked for help."}
      Colour shows the latest pH (lab result if there is one, else the probe).</p>
    <div id="map" class="map" role="region" aria-label="Map of tested fields"></div>
    <div class="legend"><span><i class="acid"></i> acidic (below 5.5)</span><span><i class="good"></i> 5.5–7.0</span>
      <span><i class="alkaline"></i> alkaline (above 7.0)</span><span><i class="none"></i> not tested</span>
      <span><i class="ring"></i> request open</span></div>
    <div class="card"><h2>${tested.length} tested of ${points.length} fields</h2>
      <table><tr><th>Farmer</th><th>Field</th><th>Probe</th><th>Lab</th><th>Map</th></tr>${points.map((p) => `
        <tr><td>${esc(p.farmer)}</td><td><a href="#/field/${p.field_id}">${esc(p.field)}</a></td>
          <td>${p.probe_ph ?? "–"}</td><td>${p.lab_ph ?? "–"}</td><td>${p.map_ph ?? "–"}</td></tr>`).join("")}</table></div>`;
  const colours = { acid: "#c0392b", good: "#198754", alkaline: "#2f5f8a", none: "#8a8f8c" };
  const map = L.map("map", { scrollWheelZoom: false });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
  const layer = L.featureGroup().addTo(map);
  points.forEach((p) => {
    const ph = p.lab_ph ?? p.probe_ph;
    L.circleMarker([p.lat, p.lon], { radius: 9, weight: p.referral_open ? 4 : 2, color: p.referral_open ? "#c98a14" : "#ffffff",
      fillColor: colours[phClass(ph)], fillOpacity: 0.9 })
      .bindPopup(`<strong>${esc(p.farmer)}</strong><br>${esc(p.field)}${p.village ? `, ${esc(p.village)}` : ""}<br>
        ${p.lab_ph != null ? `Lab pH ${esc(p.lab_ph)}<br>` : ""}${p.probe_ph != null ? `Probe pH ${esc(p.probe_ph)}<br>` : ""}
        ${p.map_ph != null ? `Map pH ${esc(p.map_ph)}<br>` : ""}${p.referral_open ? "<em>Request open</em><br>" : ""}
        <a href="#/field/${p.field_id}">Open field</a>`).addTo(layer);
  });
  if (points.length) map.fitBounds(layer.getBounds().pad(0.3), { maxZoom: 16 });
  else map.setView([-13.1, 27.8], 6);                     // Zambia
}

// ----- accounts (admin) --------------------------------------------------------------

async function viewUsers() {
  const users = await api("/users");
  $app.innerHTML = `
    <h1>Accounts</h1>
    <div class="card"><ul class="list">${users.map((u) => `
      <li class="${u.active ? "" : "inactive"}" data-user="${u.user_id}">
        <strong>${esc(u.full_name || u.username)}</strong> <small class="muted">@${esc(u.username)}</small><br>
        <small>${esc(ROLE_NAMES[u.role])}${u.active ? "" : " · deactivated"}</small>
        <div class="actions small"><button class="link" data-act="${u.active ? "off" : "on"}">${u.active ? "Deactivate" : "Activate"}</button>
          <button class="link" data-act="pw">Reset password</button></div></li>`).join("")}</ul>
    </div>
    <details class="card" open>
      <summary>Create an account for an officer or admin</summary>
      <form id="user-form">
        <label for="u-name">Full name</label><input id="u-name" name="full_name" required maxlength="80">
        <div class="row">
          <div><label for="u-username">Username</label><input id="u-username" name="username" required minlength="3" pattern="[A-Za-z0-9_.\\-]+"></div>
          <div><label for="u-password">Temporary password</label><input id="u-password" name="password" required minlength="8"></div>
        </div>
        <label for="u-role">Role</label>
        <select id="u-role" name="role"><option value="officer">Extension / lab officer</option><option value="admin">Administrator</option>
          <option value="farmer">Farmer (for a farmer who cannot sign up themselves)</option></select>
        <button type="submit">Create account</button>
      </form>
    </details>`;
  onSubmit("user-form", async (d) => { await post("/users", d); toast(`Account created for ${d.full_name}`); await viewUsers(); });
  document.querySelectorAll("[data-user] [data-act]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.closest("[data-user]").dataset.user;
      try {
        if (button.dataset.act === "pw") {
          const pw = prompt("New password (at least 8 characters):");
          if (!pw) return;
          await patch(`/users/${id}`, { password: pw });
          toast("Password changed");
        } else {
          await patch(`/users/${id}`, { active: button.dataset.act === "on" });
          toast("Account updated");
        }
        await viewUsers();
      } catch (error) { toast(error.message, true); }
    });
  });
}

// ----- router --------------------------------------------------------------------------

async function route() {
  const hash = location.hash || "#/home";
  const [, view, id] = hash.split("/");
  const open = view === "login" || view === "signup";
  if (!store.get("token") && !open) { location.hash = "#/login"; return; }
  document.getElementById("topbar").hidden = open;
  if (!open) renderNav();
  document.querySelectorAll(".topbar nav a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#/${view}`));
  window.scrollTo(0, 0);
  try {
    switch (view) {
      case "login": return viewLogin();
      case "signup": return viewSignup();
      case "fields": return await viewFarmers();
      case "farmer": return await viewFarmer(id);
      case "mine": return await viewMine();
      case "new-field": return viewNewField(id);
      case "field": return await viewField(id);
      case "advice": return await viewAdvice(id);
      case "live": return await viewLive(id);
      case "measure": return await viewMeasure(id);
      case "help": location.hash = "#/measure/1"; return undefined;
      case "probe": return await viewProbe();
      case "referrals": return await viewReferrals(id);
      case "map": return await viewMap();
      case "users": return await viewUsers();
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
