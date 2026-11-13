// SoilSense ZM screens for each role (self-testing model, Nov 2026; redesigned).
//   farmer : tests their own soil, sees only their own fields, can ask for a lab test or a visit
//   officer: extension or lab staff; works the request list, sees the map of shared tests
//   admin  : accounts, overview and map of everything
// Uses the helpers in app.js (api, post, esc, toast, onSubmit, t, viewAdvice, viewLive, viewProbe).
"use strict";

const LANG_NAMES = { en: "English", ny: "Nyanja", toi: "Tonga" };
let OFFERED = [["en", "English"], ["toi", "Tonga"]];          // replaced by /languages at start-up

async function loadLanguages() {
  try { OFFERED = (await api("/languages")).map((l) => [l.code, l.name]); } catch (error) { /* keep default */ }
  const select = document.getElementById("lang");
  const current = store.get("lang") || "en";
  select.innerHTML = OFFERED.map(([code, name]) => `<option value="${code}">${name}</option>`).join("");
  select.value = OFFERED.some(([code]) => code === current) ? current : "en";
  store.set("lang", select.value);
}
const ROLE_NAMES = { farmer: "Farmer", officer: "Extension / lab officer", admin: "Administrator" };

// Stroke icons (24 x 24), drawn inline so they need no files.
const ICON_PATHS = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
  sprout: '<path d="M12 21v-9"/><path d="M12 12c0-4 3-7 8-7 0 5-3 7-8 7z"/><path d="M12 14c0-3-2.5-5.5-7-5.5 0 4 2.5 5.5 7 5.5z"/>',
  fields: '<path d="M3 7l6-3 6 3 6-3v13l-6 3-6-3-6 3z"/><path d="M9 4v13"/><path d="M15 7v13"/>',
  inbox: '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5.5 5h13L21 13v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6z"/>',
  map: '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M18 14.7c1.8.7 3 2.5 3.5 5.3"/>',
  flask: '<path d="M9 3h6"/><path d="M10 3v6L4.5 18.5A1.6 1.6 0 0 0 5.9 21h12.2a1.6 1.6 0 0 0 1.4-2.5L14 9V3"/><path d="M7.5 14h9"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9"/><path d="M17 6l3 3"/><path d="M15 8l2 2"/>',
  book: '<path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H20v15H5.5A1.5 1.5 0 0 0 4 19.5z"/><path d="M4 19.5A1.5 1.5 0 0 0 5.5 21H20"/><path d="M9 7h7"/>',
  plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  chev: '<path d="M9 6l6 6-6 6"/>',
  back: '<path d="M15 6l-6 6 6 6"/>',
  drop: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
  pin: '<path d="M12 21s-6-5.6-6-10.5a6 6 0 0 1 12 0C18 15.4 12 21 12 21z"/><circle cx="12" cy="10.5" r="2"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 0 1 4.8 1c0 1.7-2.3 2-2.3 3.5"/><path d="M12 17.5h.01"/>',
  lab: '<path d="M6 3h12"/><path d="M8 3v5l-4 8a3 3 0 0 0 2.7 4.3h10.6A3 3 0 0 0 20 16l-4-8V3"/>',
  visit: '<circle cx="12" cy="7" r="3.5"/><path d="M5 21c1-4 3.8-6.5 7-6.5s6 2.5 7 6.5"/>',
  list: '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3.5 6h.01"/><path d="M3.5 12h.01"/><path d="M3.5 18h.01"/>',
  check: '<path d="M4 12.5l5 5L20 6.5"/>',
};
function icon(name) {
  return `<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON_PATHS[name] || ""}</svg>`;
}

const NAV = {
  farmer: [["home", "Home", "home"], ["measure", "Test soil", "sprout"], ["mine", "My fields", "fields"],
           ["referrals", "Requests", "inbox"], ["guide", "How to sample", "book"]],
  officer: [["home", "Home", "home"], ["referrals", "Requests", "inbox"], ["map", "Map", "map"],
            ["fields", "Farmers", "users"], ["guide", "How to sample", "book"], ["probe", "Probe", "flask"]],
  admin: [["home", "Home", "home"], ["map", "Map", "map"], ["fields", "Farmers", "users"],
          ["referrals", "Requests", "inbox"], ["users", "Accounts", "key"], ["probe", "Probe", "flask"]],
};
// which tab is lit for pages that are not in the menu
const NAV_PARENT = { farmer: "fields", "new-field": "fields", field: "fields", advice: "fields", live: "measure" };

function me() { try { return JSON.parse(store.get("user")) || {}; } catch (error) { return {}; } }
const firstName = (user) => esc(((user.full_name || user.username || "").split(" ")[0]) || "there");
const initials = (name) => esc((name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join(""));
const patch = (path, data) => api(path, { method: "PATCH", body: JSON.stringify(data) });
const del = (path) => api(path, { method: "DELETE" });
const when = (sql) => (sql ? new Date(sql.replace(" ", "T") + (sql.includes("Z") || sql.includes("+") ? "" : "Z"))
  .toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");

function renderNav(view) {
  const user = me();
  const items = NAV[user.role] || [];
  let current = view;
  if (NAV_PARENT[view]) current = user.role === "farmer" && NAV_PARENT[view] === "fields" ? "mine" : NAV_PARENT[view];
  document.getElementById("nav").innerHTML = items.map(([v, label, ic]) =>
    `<a href="#/${v}" class="${v === current ? "active" : ""}">${icon(ic)}<span>${label}</span></a>`).join("");
  const name = user.full_name || user.username || "";
  document.getElementById("whoami").innerHTML = user.role ? `<span class="avatar">${initials(name)}</span>
    <span class="who-text"><strong>${esc(name)}</strong><small class="muted">${esc(ROLE_NAMES[user.role])}</small></span>` : "";
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
    <span>Probe <strong>${state.connected ? "connected" : "not connected"}</strong> ·
      ${state.calToday ? "calibrated today" : state.calibration && state.calibration.accepted ? "not calibrated today" : "not calibrated"}</span>
    <span class="go">${icon("chev")}</span></a>`;
}

const demoBadge = (row) => (row && row.is_demo ? ' <span class="badge demo" title="Made-up demonstration data">demo</span>' : "");
const phClass = (ph) => (ph == null ? "none" : ph < 5.5 ? "acid" : ph <= 7.0 ? "good" : "alkaline");
const phWord = (ph) => ({ acid: "acidic", good: "good range", alkaline: "alkaline", none: "not tested" })[phClass(ph)];
const PH_COLOURS = { acid: "#c0392b", good: "#198754", alkaline: "#2f6fa8", none: "#8a8f8c" };

function pageHead(title, subtitle = "", actions = "", crumb = "") {
  return `${crumb ? `<div class="crumb">${crumb}</div>` : ""}<div class="page-head"><div><h1>${title}</h1>${subtitle ? `<p>${subtitle}</p>` : ""}</div>${actions}</div>`;
}

function segmented(id, options, value) {
  return `<div class="seg" role="tablist" id="${id}">${options.map(([v, label, ic]) =>
    `<button type="button" data-v="${v}" class="${v === value ? "on" : ""}" role="tab" aria-selected="${v === value}">${ic ? icon(ic) : ""} ${label}</button>`).join("")}</div>`;
}

function bindSegmented(id, onChange) {
  const box = document.getElementById(id);
  if (!box) return;
  box.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    box.querySelectorAll("button").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-selected", x === b); });
    try { localStorage.setItem(`seg:${id}`, b.dataset.v); } catch (error) { /* ignore */ }
    onChange(b.dataset.v);
  }));
}
function savedSeg(id, fallback) { try { return localStorage.getItem(`seg:${id}`) || fallback; } catch (error) { return fallback; } }

// A Leaflet map of points: [{lat, lon, ph, label, href, popup, ring}]
async function drawMap(elementId, points, { zoom = 16 } = {}) {
  await loadLeaflet();
  const el = document.getElementById(elementId);
  if (!el) return null;
  const map = L.map(el, { scrollWheelZoom: false, attributionControl: true });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap" }).addTo(map);
  const layer = L.featureGroup().addTo(map);
  points.filter((p) => p.lat != null && p.lon != null).forEach((p) => {
    const marker = L.circleMarker([p.lat, p.lon], { radius: p.small ? 7 : 9, weight: p.ring ? 4 : 2, color: p.ring ? "#c98a14" : "#ffffff",
      fillColor: PH_COLOURS[phClass(p.ph)], fillOpacity: 0.95 });
    if (p.label) marker.bindTooltip(p.label, { permanent: !!p.small, direction: "top", offset: [0, -6], className: "pt-label" });
    if (p.popup) marker.bindPopup(p.popup);
    marker.addTo(layer);
  });
  if (layer.getLayers().length) map.fitBounds(layer.getBounds().pad(0.35), { maxZoom: zoom });
  else map.setView([-15.7, 28.2], 10);
  setTimeout(() => map.invalidateSize(), 50);
  return map;
}

// ----- login and sign-up ---------------------------------------------------------

function viewLogin() {
  $app.innerHTML = `
    <div class="auth">
      <div class="auth-brand">
        <img class="logo" src="/static/favicon.svg" alt="">
        <h1>SoilSense ZM</h1>
        <p>Test your soil yourself, today, and get advice you can act on. When a result is unusual, we send you to a soil lab.</p>
      </div>
      <div class="card">
        <form id="login-form">
          <label for="username">Username</label>
          <input id="username" name="username" autocomplete="username" required>
          <label for="password">Password</label>
          <input id="password" name="password" type="password" autocomplete="current-password" required>
          <button type="submit" style="width:100%">Log in</button>
        </form>
        <p class="center" style="margin-top:0.9rem">New farmer? <a href="#/signup"><strong>Create an account</strong></a></p>
      </div>
      <div class="card">
        <h2>Three ways to get soil advice</h2>
        <ul class="ways">
          <li><span class="ico">${icon("sprout")}</span><p><strong>Test it yourself</strong><br><small class="muted">With the SoilSense probe. Advice the same day.</small></p></li>
          <li><span class="ico alkaline">${icon("visit")}</span><p><strong>Ask an extension officer</strong><br><small class="muted">They come and test it with you.</small></p></li>
          <li><span class="ico acid">${icon("lab")}</span><p><strong>Take a sample to a soil lab</strong><br><small class="muted">For example ZARI Mount Makulu, for a full report.</small></p></li>
        </ul>
        <p class="muted" style="margin-top:0.6rem">Extension and lab officers get their accounts from the administrator.</p>
      </div>
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
    <div class="auth">
      <div class="crumb"><a href="#/login">${icon("back")} Log in</a></div>
      <div class="page-head"><div><h1>Create your account</h1><p>For farmers who want to test their own soil.</p></div></div>
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
            ${OFFERED.map(([code, name]) => `<option value="${code}">${name}</option>`).join("")}</select>
          <label class="check"><input type="checkbox" name="share_consent" checked>
            <span>Share my results and field location with extension and lab officers, so they can help me and add my soil to their map. You can change this later.</span></label>
          <label class="check"><input type="checkbox" name="sms_consent" id="sms_consent"> <span>Send me advice by SMS</span></label>
          <label for="phone">Phone number (only if you want SMS)</label>
          <input id="phone" name="phone" type="tel" placeholder="+260..." pattern="\\+?[0-9]{9,15}">
          <button type="submit" style="width:100%">Create account</button>
        </form>
      </div>
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
    <div class="hello"><div><h1>Hello, ${firstName(user)}</h1><p>${esc(profile.village || "")}${profile.village ? " · " : ""}${profile.fields.length} field${profile.fields.length === 1 ? "" : "s"}</p></div>
      <span class="avatar" style="width:44px;height:44px">${initials(profile.alias)}</span></div>
    ${probeStrip(state)}
    <a class="button big-btn" href="#/measure">${icon("sprout")} Test my soil</a>
    <div class="card">
      <div class="section-head"><h2>My fields</h2><a href="#/new-field/${profile.farmer_id}">${icon("plus")} Add a field</a></div>
      ${fieldCards(profile.fields, "Add your first field: stand in it and save its GPS position.")}
    </div>
    ${requests.length ? `<div class="card"><h2>My requests</h2>${referralList(requests, user)}</div>` : ""}
    <div class="tiles">
      <a class="tile" href="#/guide"><span class="ico">${icon("book")}</span><strong>How to sample</strong><span>Six steps with pictures</span></a>
      <a class="tile" href="#/referrals"><span class="ico alkaline">${icon("help")}</span><strong>Get help</strong><span>Ask an officer, or a lab test</span></a>
    </div>`;
  bindReferralActions(user);
}

function fieldCards(fields, empty) {
  if (!fields.length) return `<div class="center muted" style="padding:1.5rem 0">${icon("fields")}<p>${empty}</p></div>`;
  return `<ul class="field-list">${fields.map((f) => {
    const v = fieldValue(f);
    const sub = [f.point_count > 1 ? `${f.point_count} sampling points` : "",
                 f.location_source === "gps" ? `GPS ±${f.gps_accuracy_m} m` : "typed location"].filter(Boolean).join(" · ");
    return `<li><a class="field-link" href="#/field/${f.field_id}">
      <span class="ico ${phClass(v.ph)}">${icon("fields")}</span>
      <span class="grow"><strong>${esc(f.name)}</strong><small class="muted">${esc(sub)}</small></span>
      <span class="ph-chip ${phClass(v.ph)}">${esc(v.text)}</span><span class="chev">${icon("chev")}</span></a></li>`;
  }).join("")}</ul>`;
}

async function officerHome(user) {
  const [requests, points, devices] = await Promise.all([api("/referrals"), api("/map/points"), api("/devices")]);
  const tested = points.filter((p) => p.probe_ph != null || p.lab_ph != null).length;
  const labs = requests.filter((r) => r.kind === "lab").length;
  $app.innerHTML = `
    <div class="hello"><div><h1>Hello, ${firstName(user)}</h1><p>Extension and lab work</p></div></div>
    <div class="stats">
      <a class="stat" href="#/referrals"><strong>${requests.length}</strong><span>open requests</span></a>
      <a class="stat" href="#/referrals"><strong>${labs}</strong><span>lab tests asked for</span></a>
      <a class="stat" href="#/map"><strong>${tested}</strong><span>tested fields on the map</span></a>
    </div>
    ${probeStrip(probeState(devices))}
    <div class="tiles">
      <a class="tile primary" href="#/referrals"><span class="ico">${icon("inbox")}</span><strong>Requests</strong><span>Visits and lab tests farmers asked for</span></a>
      <a class="tile" href="#/map"><span class="ico alkaline">${icon("map")}</span><strong>Soil map</strong><span>Every shared soil test</span></a>
      <a class="tile" href="#/fields"><span class="ico">${icon("users")}</span><strong>Farmers</strong><span>Profiles, fields, and farmers without a phone</span></a>
      <a class="tile" href="#/measure"><span class="ico acid">${icon("sprout")}</span><strong>Test for a farmer</strong><span>Guided test with the probe</span></a>
    </div>
    ${requests.length ? `<div class="card"><div class="section-head"><h2>Latest requests</h2><a href="#/referrals">See all</a></div>${referralList(requests.slice(0, 4), user)}</div>` : ""}`;
  bindReferralActions(user);
}

async function adminHome(user) {
  const [o, devices] = await Promise.all([api("/overview"), api("/devices")]);
  const n = (obj, key) => (obj && obj[key]) || 0;
  const total = Object.values(o.advice || {}).reduce((a, b) => a + b, 0) || 1;
  $app.innerHTML = `
    <div class="hello"><div><h1>Overview</h1><p>Everything in SoilSense ZM</p></div></div>
    ${o.farmers_demo ? `<p class="notice info">Includes ${o.farmers_demo} made-up demonstration farms, marked <span class="badge demo">demo</span>.
      Remove them with <code>python -m backend.seed_demo --remove</code>.</p>` : ""}
    <div class="stats">
      <div class="stat"><strong>${o.farmers}</strong><span>farmers · ${o.farmers_self_testing} test themselves</span></div>
      <div class="stat"><strong>${o.fields}</strong><span>fields</span></div>
      <div class="stat"><strong>${n(o.readings, "accepted")}</strong><span>readings · ${n(o.readings, "rejected")} refused</span></div>
      <a class="stat" href="#/referrals"><strong>${o.referrals_open}</strong><span>open requests</span></a>
      <div class="stat"><strong>${o.lab_results}</strong><span>lab results</span></div>
      <a class="stat" href="#/users"><strong>${n(o.users, "officer")}</strong><span>officers · ${n(o.users, "farmer")} farmer accounts</span></a>
    </div>
    <div class="grid-2">
      <div class="card"><h2>Advice given, by confidence</h2>
        <div class="bars">${["high", "moderate", "low", "none"].map((k) =>
          `<div class="bar-row"><span>${k}</span><div class="bar"><div class="bar-fill ${k}" style="width:${(100 * n(o.advice, k) / total).toFixed(0)}%"></div></div><b>${n(o.advice, k)}</b></div>`).join("")}</div></div>
      <div class="card"><h2>Recent calibrations</h2>
        ${o.calibrations.length ? `<table><tr><th>When</th><th>Slope</th><th>Result</th></tr>${o.calibrations.slice(0, 5).map((c) => `
          <tr><td>${esc(when(c.date))}</td><td>${esc(c.slope_pct)}%</td><td><span class="badge ${c.accepted ? "accepted" : "rejected"}">${c.accepted ? "accepted" : "failed"}</span></td></tr>`).join("")}</table>`
          : '<p class="muted">No calibrations yet.</p>'}</div>
    </div>
    ${probeStrip(probeState(devices))}
    <div class="tiles">
      <a class="tile primary" href="#/map"><span class="ico">${icon("map")}</span><strong>Soil map</strong><span>All soil tests</span></a>
      <a class="tile" href="#/users"><span class="ico">${icon("key")}</span><strong>Accounts</strong><span>Officers, admins, farmers</span></a>
      <a class="tile" href="#/fields"><span class="ico alkaline">${icon("users")}</span><strong>Farmers</strong><span>Profiles and fields</span></a>
      <a class="tile" href="#/referrals"><span class="ico acid">${icon("inbox")}</span><strong>Requests</strong><span>Visits and lab tests</span></a>
    </div>`;
}

// ----- farmers ---------------------------------------------------------------------

async function viewFarmers() {
  const user = me();
  if (user.role === "farmer") { location.hash = "#/mine"; return; }
  const [farmers, points] = await Promise.all([api("/farmers"), api("/map/points")]);
  const mode = savedSeg("farmers-view", "list");
  $app.innerHTML = `
    ${pageHead("Farmers", `${farmers.length} farmer${farmers.length === 1 ? "" : "s"} you can see`,
      segmented("farmers-view", [["list", "List", "list"], ["map", "Map", "map"]], mode))}
    <div id="farmers-list" ${mode === "map" ? "hidden" : ""}>
      <input id="farmer-search" type="search" placeholder="Search by name or village" aria-label="Search farmers" style="margin-bottom:0.8rem">
      <ul class="field-list" id="farmer-list">${farmers.map((f) => `
        <li data-q="${esc(`${f.alias} ${f.village || ""}`.toLowerCase())}"><a class="field-link" href="#/farmer/${f.farmer_id}">
          <span class="avatar">${initials(f.alias)}</span>
          <span class="grow"><strong>${esc(f.alias)}</strong>${demoBadge(f)}
            <small class="muted">${esc(f.village || "—")} · ${f.field_count} field${f.field_count === 1 ? "" : "s"} ·
            ${f.own_account ? "tests themselves" : `registered by ${esc(f.registered_by || "—")}`}</small></span>
          ${f.mine && !f.own_account ? '<span class="badge moderate">yours</span>' : ""}
          ${!f.share_consent && !f.mine ? '<span class="badge low">asked for help</span>' : ""}
          <span class="chev">${icon("chev")}</span></a></li>`).join("")}</ul>
      ${farmers.length ? "" : '<div class="card"><p class="muted">No farmers you can see yet.</p></div>'}
    </div>
    <div id="farmers-map" ${mode === "map" ? "" : "hidden"}>
      <div id="fmap" class="map"></div>
      ${legend()}
    </div>
    <details class="card" style="margin-top:1rem">
      <summary>${icon("plus")} Register a farmer who has no phone or account</summary>
      ${farmerForm({}, "farmer-form", "Register farmer")}
    </details>`;
  document.getElementById("farmer-search").addEventListener("input", (event) => {
    const q = event.target.value.toLowerCase();
    document.querySelectorAll("#farmer-list li").forEach((li) => { li.hidden = !li.dataset.q.includes(q); });
  });
  let drawn = false;
  const show = async (v) => {
    document.getElementById("farmers-list").hidden = v !== "list";
    document.getElementById("farmers-map").hidden = v !== "map";
    if (v === "map" && !drawn) { drawn = true; await drawMap("fmap", mapPoints(points), { zoom: 13 }); }
  };
  bindSegmented("farmers-view", show);
  if (mode === "map") show("map");
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
    <select id="${id}-lang" name="preferred_language">${OFFERED.concat(f.preferred_language && !OFFERED.some(([c]) => c === f.preferred_language)
      ? [[f.preferred_language, LANG_NAMES[f.preferred_language]]] : []).map(([code, name]) =>
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
  const mode = savedSeg("fields-view", "list");
  $app.innerHTML = `
    ${pageHead(own ? "My fields" : `${esc(farmer.alias)}${demoBadge(farmer)}`,
      own ? "Your fields and what the soil said" : `${esc(farmer.village || "")}`,
      segmented("fields-view", [["list", "List", "list"], ["map", "Map", "map"]], mode),
      own ? "" : `<a href="#/fields">${icon("back")} Farmers</a>`)}
    <div class="card">
      <div class="section-head"><h2>Fields</h2><a href="#/new-field/${farmer.farmer_id}">${icon("plus")} Add a field</a></div>
      <div id="fields-list" ${mode === "map" ? "hidden" : ""}>${fieldCards(farmer.fields, own ? "Add your first field: stand in it and save its GPS position." : "No fields yet.")}</div>
      <div id="fields-map" ${mode === "map" ? "" : "hidden"}><div id="fieldmap" class="map small"></div>${legend()}</div>
    </div>
    <div class="card profile">
      <div class="section-head"><h2>${own ? "My profile" : "Profile"}</h2></div>
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
  let drawn = false;
  const show = async (v) => {
    document.getElementById("fields-list").hidden = v !== "list";
    document.getElementById("fields-map").hidden = v !== "map";
    if (v === "map" && !drawn) {
      drawn = true;
      await drawMap("fieldmap", farmer.fields.map((f) => ({ lat: f.lat, lon: f.lon, ph: fieldValue(f).ph, label: f.name,
        popup: `<strong>${esc(f.name)}</strong><br>${esc(fieldValue(f).text)}<br><a href="#/field/${f.field_id}">Open field</a>` })), { zoom: 15 });
    }
  };
  bindSegmented("fields-view", show);
  if (mode === "map") show("map");
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
    ${pageHead("Add a field", "Stand in the middle of the field to save its position", "", `<a href="javascript:history.back()">${icon("back")} Back</a>`)}
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
  let estimate = null;
  try { estimate = await api(`/fields/${fieldId}/map-estimate`); } catch (error) { estimate = null; }
  const own = user.role === "farmer";
  const points = history.points || [];
  const values = points.map((p) => p.ph).sort((a, b) => a - b);
  const median = values.length ? (values.length % 2 ? values[(values.length - 1) / 2]
    : Math.round(((values[values.length / 2 - 1] + values[values.length / 2]) / 2) * 100) / 100) : null;
  const spread = values.length ? Math.round((values[values.length - 1] - values[0]) * 100) / 100 : 0;
  const lab = history.lab_results[0];
  const shownPh = lab ? lab.ph : median;
  const openRefs = history.referrals.filter((r) => r.status === "open" || r.status === "in_progress");
  const openLab = openRefs.filter((r) => r.kind === "lab");
  const latest = history.readings.find((r) => r.quality_status === "accepted");
  const multi = points.length > 1;
  const readingOptions = history.readings.filter((r) => r.quality_status === "accepted").map((r) =>
    `<option value="${r.reading_id}">${r.point_label ? `${esc(r.point_label)}: ` : ""}pH ${esc(r.ph_water)} · ${esc(when(r.ts))}</option>`).join("");

  $app.innerHTML = `
    ${pageHead(`${esc(field.name)}${demoBadge(farmer)}`,
      own ? `${esc(farmer.village || "")}` : `${esc(farmer.alias)}${farmer.village ? `, ${esc(farmer.village)}` : ""}`, "",
      own ? `<a href="#/mine">${icon("back")} My fields</a>` : `<a href="#/farmer/${farmer.farmer_id}">${icon("back")} ${esc(farmer.alias)}</a>`)}
    <div class="grid-2">
      <div>
        <div class="card">
          <div class="facts">
            <div class="fact"><span>${lab ? "Lab pH" : multi ? "pH (middle value)" : "Latest pH"}</span>
              <strong>${shownPh != null ? `<span class="ph-chip ${phClass(shownPh)}">${esc(shownPh)}</span>` : "not tested"}</strong></div>
            <div class="fact"><span>Soil map says</span><strong>${estimate ? `pH ${esc(estimate.ph_mean)} ± ${esc(estimate.ph_sd)}` : "—"}</strong></div>
            <div class="fact"><span>${multi ? "Sampling points" : "Readings"}</span><strong>${multi ? points.length : history.readings.length}</strong></div>
            <div class="fact"><span>Location</span><strong>${field.location_source === "gps" ? `GPS ±${esc(field.gps_accuracy_m)} m` : "typed"}</strong></div>
          </div>
          <div id="fmap" class="map small" aria-label="Map of the field${multi ? " and its sampling points" : ""}"></div>
          ${multi ? `<div class="points">${points.map((p) => `<span class="point ${phClass(p.ph)}">${esc(p.label || "point")} <small>pH</small> ${esc(p.ph)}</span>`).join("")}</div>
            ${spread > 1.0 ? `<p class="notice" style="margin-top:0.8rem">The samples in this field differ a lot (pH ${esc(values[0])} to ${esc(values[values.length - 1])}).
              Parts of the field may need different treatment: test them as separate fields.</p>` : ""}` : ""}
        </div>
        <a class="button big-btn" href="#/live/${esc(fieldId)}">${icon("sprout")} Measure with the probe</a>
        ${openRefs.length ? `<div class="notice info">${openRefs.map((r) => `<p style="margin:0"><strong>${r.kind === "lab" ? "Lab test requested" : "Officer visit requested"}</strong>
          · ${esc(r.status.replace("_", " "))} · ${esc(when(r.created_at))}</p>`).join("")}</div>` : ""}
      </div>
      <div>
        <div class="card">
          <h2>Get advice</h2>
          ${readingOptions || history.lab_results.length ? `<form id="advice-form">
            <label for="reading_id">Based on</label>
            <select id="reading_id" name="reading_id">
              ${multi ? `<option value="whole">The whole field (${points.length} points, middle pH ${esc(median)})</option>` : ""}
              ${history.lab_results.length ? '<option value="">The lab result</option>' : ""}${readingOptions}</select>
            <div class="row">
              <div><label for="crop">Crop</label><select id="crop" name="crop">${CROPS.map((c) => `<option value="${c}">${esc(capital(cropName(c)))}</option>`).join("")}</select></div>
              <div><label for="budget_band">Money available</label>
                <select id="budget_band" name="budget_band"><option value="low">Little</option><option value="medium">Some</option></select></div>
              <div><label for="water">Water</label>
                <select id="water" name="water"><option value="rainfed">Rain only</option><option value="irrigated">Irrigated</option></select></div>
            </div>
            <button type="submit" style="width:100%">Get advice</button>
          </form>` : `<p class="muted">Measure the soil first, or enter a lab result.</p>`}
        </div>
        <div class="card help-card">
          <h2>Not sure? Ask for help</h2>
          <div class="actions">
            <button class="secondary" id="ask-visit">${icon("visit")} Ask an officer to visit</button>
            <button class="secondary" id="ask-lab">${icon("lab")} Request a lab test</button>
          </div>
        </div>
        ${history.recommendations.length ? `<div class="card"><h2>Earlier advice</h2><ul class="field-list">${history.recommendations.slice(0, 6).map((r) => `
          <li><a class="field-link" href="#/advice/${r.rec_id}"><span class="grow"><strong>${esc(capital(cropName(r.crop)))}</strong>
            <small class="muted">${esc(r.as_of_date)}</small></span><span class="badge ${esc(r.trust_level)}">${esc(r.trust_level)}</span>
            <span class="chev">${icon("chev")}</span></a></li>`).join("")}</ul></div>` : ""}
      </div>
    </div>

    ${history.readings.length ? `<details class="card"><summary>All readings (${history.readings.length})</summary><ul class="list">${history.readings.map((r) => `
      <li><span class="badge ${esc(r.quality_status)}">${r.quality_status === "accepted" ? "accepted" : "refused"}</span>
        ${r.point_label ? `<strong>${esc(r.point_label)}</strong> · ` : ""}${r.ph_water != null ? `pH ${esc(r.ph_water)}` : ""}
        <small class="muted">${esc(when(r.ts))}${r.temp_c != null ? ` · ${esc(r.temp_c)} °C` : ""}</small>
        ${readingExplanation(r) ? `<br><small>${esc(readingExplanation(r))}</small>` : ""}</li>`).join("")}</ul></details>` : ""}
    ${history.lab_results.length ? `<div class="card"><h2>Lab results</h2><ul class="list">${history.lab_results.map((l) => `
      <li>pH ${esc(l.ph)} (${l.ph_method === "cacl2" ? "CaCl₂" : "water"})${l.texture ? ` · ${esc(l.texture)}` : ""}
        <small class="muted">${esc(l.lab_name || "")} ${esc(l.date || "")}</small></li>`).join("")}</ul></div>` : ""}

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
        <label class="check"><input type="checkbox" name="waterlogging"> <span>Waterlogged in the rains</span></label>
        <label class="check"><input type="checkbox" name="manure_available"> <span>Manure available</span></label>
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
        <label for="point_label">Sampling point (optional)</label><input id="point_label" name="point_label" maxlength="20" placeholder="e.g. S03">
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

  const mapPts = multi
    ? points.map((p) => ({ lat: p.lat ?? field.lat, lon: p.lon ?? field.lon, ph: p.ph, label: p.label || "", small: true }))
    : [{ lat: field.lat, lon: field.lon, ph: shownPh, label: field.name }];
  drawMap("fmap", mapPts, { zoom: multi ? 19 : 16 }).catch(() => {});

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
      if (d.reading_id === "whole") body.whole_field = true;
      else if (d.reading_id) body.reading_id = Number(d.reading_id);
      const advice = await post("/advice", body);
      location.hash = `#/advice/${advice.rec_id}`;
    });
  }
  onSubmit("reading-form", async (d) => {
    const body = { field_id: Number(fieldId), device_id: d.device_id, replicates_ph: [d.r1, d.r2, d.r3], temp_c: d.temp_c };
    if (d.point_label) body.point_label = d.point_label;
    const reading = await post("/readings", body);
    toast(reading.quality_status === "accepted" ? `Reading accepted: pH ${reading.ph_water}`
      : `Reading refused: ${readingExplanation(reading) || reading.quality_reasons.join("; ")}`, reading.quality_status !== "accepted");
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
  const step = Math.min(Math.max(Number(stepParam) || 1, 1), STEPS.length);
  const s = STEPS[step - 1];
  let extra = "";
  if (s.calibrate) {
    const state = probeState(await api("/devices"));
    extra = state.calToday ? `<p class="notice info"><strong>Done today.</strong> The probe was calibrated today: you can skip this step.</p>`
      : `<p class="notice"><strong>Not calibrated today.</strong> Calibrate before measuring, or the reading will be refused.
         <a href="#/probe">Probe status</a></p>`;
  }
  if (s.choose) {
    let fields;
    if (user.role === "farmer") fields = (await api("/farmers/me")).fields.map((f) => ({ ...f, farmer: "" }));
    else fields = (await api("/map/points")).map((p) => ({ field_id: p.field_id, name: p.field, farmer: p.farmer }));
    extra = fields.length ? `<ul class="field-list">${fields.map((f) => `
      <li><a class="field-link" href="#/live/${f.field_id}"><span class="ico">${icon("fields")}</span>
        <span class="grow"><strong>${esc(f.name)}</strong>${f.farmer ? `<small class="muted">${esc(f.farmer)}</small>` : ""}</span>
        <span class="badge high">Measure</span><span class="chev">${icon("chev")}</span></a></li>`).join("")}</ul>`
      : `<p>No field yet. ${user.role === "farmer" ? `<a href="#/new-field/${user.farmer_id}">Add your field</a> first (stand in it to save its position).`
        : `<a href="#/fields">Open a farmer</a> and add their field first.`}</p>`;
  }
  $app.innerHTML = `
    ${pageHead(user.role === "farmer" ? "Test my soil" : "Guided soil test", `Step ${step} of ${STEPS.length}`,
      `<a href="#/guide">${icon("book")} All steps</a>`)}
    <ol class="stepper" aria-label="Steps">${STEPS.map((x, i) => `<li class="${i + 1 === step ? "now" : i + 1 < step ? "done" : ""}">
      <a href="#/measure/${i + 1}" aria-label="Step ${i + 1}: ${esc(x.title)}">${i + 1 < step ? "✓" : i + 1}</a></li>`).join("")}</ol>
    <div class="card step">
      <h2>${esc(s.title)}</h2>
      <div class="anim-box">${ANIM[s.anim]}</div>
      ${s.body}
      ${extra}
      <div class="actions step-nav">
        ${step > 1 ? `<a class="button secondary-btn" href="#/measure/${step - 1}">${icon("back")} Back</a>` : "<span></span>"}
        ${step < STEPS.length ? `<a class="button" href="#/measure/${step + 1}">Next ${icon("chev")}</a>` : ""}
      </div>
    </div>`;
}

// ----- requests (referrals) -----------------------------------------------------------

function referralList(items, user) {
  if (!items.length) return `<div class="center muted" style="padding:1.25rem 0">${icon("check")}<p>No requests.</p></div>`;
  const staff = user.role !== "farmer";
  return `<ul class="list referrals">${items.map((r) => `
    <li data-ref="${r.referral_id}">
      <div style="display:flex;gap:0.75rem;align-items:flex-start">
        <span class="ico ${r.kind === "lab" ? "alkaline" : "acid"}">${icon(r.kind === "lab" ? "lab" : "visit")}</span>
        <div class="grow" style="flex:1;min-width:0">
          <div><strong>${esc(staff ? r.farmer : r.field)}</strong>${staff ? demoBadge(r) : ""}
            <span class="status ${esc(r.status)}">${esc(r.status.replace("_", " "))}</span></div>
          <small class="muted">${r.kind === "lab" ? "Lab test" : "Visit"} · ${staff ? `${esc(r.field)}${r.village ? `, ${esc(r.village)}` : ""} · ` : ""}${esc(when(r.created_at))}
            ${r.reading_ph != null ? ` · probe pH ${esc(r.reading_ph)}` : ""}${staff && r.phone ? ` · ☎ ${esc(r.phone)}` : ""}
            ${r.handled_by_name ? ` · ${esc(r.handled_by_name)}` : ""}</small>
          <div class="actions small">
            <a href="#/field/${r.field_id}">Open field</a>
            ${staff && r.status === "open" ? `<button class="link" data-act="in_progress">Start</button>` : ""}
            ${staff && (r.status === "open" || r.status === "in_progress") && r.kind === "visit" ? `<button class="link" data-act="done">Mark done</button>` : ""}
            ${staff && r.kind === "lab" && r.status !== "done" && r.status !== "cancelled" ? `<a href="#/field/${r.field_id}">Enter lab result</a>` : ""}
            ${r.status === "open" || r.status === "in_progress" ? `<button class="link" data-act="cancelled">Cancel</button>` : ""}
          </div>
        </div>
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
    ${pageHead(user.role === "farmer" ? "My requests" : "Requests",
      user.role === "farmer" ? "Visits and lab tests you asked for" : "Farmers who asked for a visit, or for a lab test to confirm their reading")}
    <div class="tabs"><a class="${status === "active" ? "on" : ""}" href="#/referrals">Open</a>
      <a class="${status === "all" ? "on" : ""}" href="#/referrals/all">All</a></div>
    <div class="card">${referralList(items, user)}</div>
    ${user.role === "farmer" ? "" : `<p class="muted">For a lab test: arrange the sample, then open the field and enter the lab result. The farmer’s advice then has high confidence.</p>`}`;
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
  const points = await api("/map/points");
  const tested = points.filter((p) => p.probe_ph != null || p.lab_ph != null);
  $app.innerHTML = `
    ${pageHead("Soil map", `${tested.length} of ${points.length} fields tested · ${user.role === "admin" ? "every field in the system"
      : "farmers who share their results or asked for help"}`)}
    <div id="map" class="map" role="region" aria-label="Map of tested fields"></div>
    ${legend()}
    <details class="card"><summary>${icon("list")} As a table</summary>
      <table><tr><th>Farmer</th><th>Field</th><th>Probe</th><th>Lab</th><th>Soil map</th></tr>${points.map((p) => `
        <tr><td>${esc(p.farmer)}${demoBadge(p)}</td><td><a href="#/field/${p.field_id}">${esc(p.field)}</a></td>
          <td>${p.probe_ph ?? "–"}</td><td>${p.lab_ph ?? "–"}</td><td>${p.map_ph ?? "–"}</td></tr>`).join("")}</table></details>`;
  await drawMap("map", mapPoints(points), { zoom: 13 });
}

// ----- accounts (admin) --------------------------------------------------------------

async function viewUsers() {
  const users = await api("/users");
  $app.innerHTML = `
    ${pageHead("Accounts", `${users.filter((u) => u.active).length} active`)}
    <div class="card"><ul class="field-list">${users.map((u) => `
      <li class="${u.active ? "" : "inactive"}" data-user="${u.user_id}"><div class="field-link" style="cursor:default">
        <span class="avatar">${initials(u.full_name || u.username)}</span>
        <span class="grow"><strong>${esc(u.full_name || u.username)}</strong>
          <small class="muted">@${esc(u.username)} · ${esc(ROLE_NAMES[u.role])}${u.active ? "" : " · deactivated"}</small></span>
        <span class="actions small" style="margin:0"><button class="link" data-act="${u.active ? "off" : "on"}">${u.active ? "Deactivate" : "Activate"}</button>
          <button class="link" data-act="pw">Reset password</button></span></div></li>`).join("")}</ul>
    </div>
    <details class="card">
      <summary>${icon("plus")} Create an account for an officer or admin</summary>
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

function fieldValue(f) {
  if (f.lab_ph != null) return { ph: f.lab_ph, text: `lab pH ${f.lab_ph}` };
  if (f.point_count > 1) return { ph: f.median_ph, text: `pH ${f.median_ph}` };
  if (f.latest_ph != null) return { ph: f.latest_ph, text: `pH ${f.latest_ph}` };
  return { ph: null, text: "not tested" };
}

function legend() {
  return `<div class="legend"><span><i class="acid"></i> acidic (below 5.5)</span><span><i class="good"></i> 5.5–7.0</span>
    <span><i class="alkaline"></i> alkaline (above 7.0)</span><span><i class="none"></i> not tested</span><span><i class="ring"></i> request open</span></div>`;
}

function mapPoints(points) {
  return points.map((p) => ({ lat: p.lat, lon: p.lon, ph: p.lab_ph ?? p.probe_ph, ring: p.referral_open,
    popup: `<strong>${esc(p.farmer)}</strong>${p.is_demo ? " (demo)" : ""}<br>${esc(p.field)}${p.village ? `, ${esc(p.village)}` : ""}<br>
      ${p.lab_ph != null ? `Lab pH ${esc(p.lab_ph)}<br>` : ""}${p.probe_ph != null ? `Probe pH ${esc(p.probe_ph)}<br>` : ""}
      ${p.map_ph != null ? `Soil map pH ${esc(p.map_ph)}<br>` : ""}${p.referral_open ? "<em>Request open</em><br>" : ""}
      <a href="#/field/${p.field_id}">Open field</a>` }));
}

function viewGuide() {
  const steps = [STEPS[0], STEPS[1], STEPS[2], STEPS[4], STEPS[3], STEPS[5]];
  $app.innerHTML = `
    ${pageHead("How to sample and test your soil", "Six steps. A good sample matters more than a good probe.",
      `<a class="button" href="#/measure/1" style="margin:0">${icon("sprout")} Start a test</a>`)}
    <div class="guide">${steps.map((s, i) => `
      <div class="card">
        <h2><span class="step-no">${i + 1}</span>${esc(s.title)}</h2>
        <div class="anim-box">${ANIM[s.anim]}</div>
        ${s.body}
      </div>`).join("")}</div>
    <div class="card" style="margin-top:1rem">
      <h2>One field, one sample</h2>
      <p>Mix the 15 to 20 small samples from one field into <strong>one</strong> sample: that gives one pH and one piece of advice
        for the field. If parts of the field look different (colour, slope, how crops grow), treat them as separate fields and
        sample each one.</p>
    </div>`;
}

// ----- router --------------------------------------------------------------------------

async function route() {
  const hash = location.hash || "#/home";
  const [, view, id] = hash.split("/");
  const open = view === "login" || view === "signup";
  if (!store.get("token") && !open) { location.hash = "#/login"; return; }
  document.getElementById("topbar").hidden = open;
  if (!open) renderNav(view);
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
      case "guide": return viewGuide();
      case "help": location.hash = "#/guide"; return undefined;
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
window.addEventListener("hashchange", route);
loadLanguages().finally(route);
