/* SF Soft-Story Seismic Risk: MapLibre front end. Data built by `python -m seismic_risk web`. */

const COLORS = {
  score: ["#fbe3cf", "#f5b08f", "#eb6834", "#c4401b", "#7f2a10"],
  mmi: ["#f2f0f7", "#dadaeb", "#bcbddc", "#9e9ac8", "#756bb1"],
  nta: ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
  liq: "rgba(42,120,214,0.7)", ls: "rgba(138,90,43,0.75)", fault: "#3d3c39", ring: "#0b0b0b",
};
const SCORE_BREAKS = [0.3, 0.4, 0.5, 0.6];
const MMI_BREAKS = [6.0, 6.5, 7.0, 7.5];

const METRICS = {
  units_in_high_score: { label: "Units", breaks: [25, 100, 250, 500, 1000, 2000], fmt: (v) => Math.round(v).toLocaleString() },
  est_residents_in_high_score: { label: "Residents", breaks: [50, 200, 500, 1000, 2000, 4000], fmt: (v) => Math.round(v).toLocaleString() },
  unretrofitted: { label: "Buildings", breaks: [1, 3, 6, 10, 15, 30], fmt: (v) => Math.round(v).toLocaleString() },
  in_cgs_liquefaction_zone: { label: "Buildings", breaks: [1, 10, 25, 50, 100, 200], fmt: (v) => Math.round(v).toLocaleString() },
};
const STATUS = {
  retrofitted: ["#1baf7a", "Retrofitted (certificate of final completion)"],
  non_compliant: ["#0b0b0b", "Not retrofitted: non-compliant"],
  newly_added: ["#0b0b0b", "Not retrofitted: newly added to the list"],
};
const FOOTPRINT_ZOOM = 15.5;

const fmtInt = (n) => Math.round(n).toLocaleString();
const dataUrl = (f) => new URL(`data/${f}`, location.href).href;
const $ = (id) => document.getElementById(id);
const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: [-122.44, 37.765],
  zoom: 12,
  minZoom: 9.5,
  maxZoom: 18.5,
  maxBounds: [[-123.05, 37.45], [-121.85, 38.05]],
  hash: true,
  attributionControl: { compact: true },
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
map.addControl(new maplibregl.ScaleControl({ unit: "imperial" }), "bottom-right");

function step(prop, breaks, colors) {
  const expr = ["step", ["to-number", ["get", prop]], colors[0]];
  breaks.forEach((b, i) => expr.push(b, colors[i + 1]));
  return expr;
}

// Diagonal hatch drawn once into an image the fill-pattern can use.
function hatchImage(color, flip = false, size = 12) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d");
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.4;
  for (const o of [-size, 0, size]) {
    ctx.beginPath();
    if (flip) { ctx.moveTo(o, 0); ctx.lineTo(o + size, size); } else { ctx.moveTo(o, size); ctx.lineTo(o + size, 0); }
    ctx.stroke();
  }
  return ctx.getImageData(0, 0, size, size);
}

const byId = new Map();
let ntaData = null;
let stats = null;

map.on("load", async () => {
  const firstLabel = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
  map.addImage("hatch-liq", hatchImage(COLORS.liq), { pixelRatio: 2 });
  map.addImage("hatch-ls", hatchImage(COLORS.ls, true), { pixelRatio: 2 });

  const [buildings, nta, s] = await Promise.all(["buildings.geojson", "neighborhoods.geojson", "stats.json"]
    .map((f) => fetch(dataUrl(f)).then((r) => r.json())));
  buildings.features.forEach((f) => byId.set(f.properties.id, f));
  ntaData = nta;
  stats = s;

  map.addSource("nta", { type: "geojson", data: nta });
  map.addSource("shaking", { type: "geojson", data: dataUrl("shaking.geojson") });
  map.addSource("liq", { type: "geojson", data: dataUrl("liquefaction.geojson") });
  map.addSource("ls", { type: "geojson", data: dataUrl("landslide.geojson") });
  map.addSource("faults", { type: "geojson", data: dataUrl("faults.geojson") });
  map.addSource("buildings", { type: "geojson", data: buildings, promoteId: "id" });
  map.addSource("footprints", { type: "geojson", data: dataUrl("footprints.geojson"), promoteId: "id" });
  map.addSource("epicenter", { type: "geojson", data: { type: "Feature", geometry: { type: "Point", coordinates: s.epicenter }, properties: {} } });

  map.addLayer({ id: "nta-fill", type: "fill", source: "nta", layout: { visibility: "none" },
    paint: { "fill-color": COLORS.nta[0], "fill-opacity": 0.65 } }, firstLabel);
  map.addLayer({ id: "shaking", type: "fill", source: "shaking",
    paint: { "fill-color": step("mmi", MMI_BREAKS, COLORS.mmi), "fill-opacity": 0.38, "fill-outline-color": "rgba(117,107,177,0.35)" } }, firstLabel);
  map.addLayer({ id: "liq", type: "fill", source: "liq", paint: { "fill-pattern": "hatch-liq" } }, firstLabel);
  map.addLayer({ id: "liq-line", type: "line", source: "liq", paint: { "line-color": COLORS.liq, "line-width": 0.8 } }, firstLabel);
  map.addLayer({ id: "ls", type: "fill", source: "ls", paint: { "fill-pattern": "hatch-ls" } }, firstLabel);
  map.addLayer({ id: "ls-line", type: "line", source: "ls", paint: { "line-color": COLORS.ls, "line-width": 0.8 } }, firstLabel);
  map.addLayer({ id: "nta-line", type: "line", source: "nta",
    paint: { "line-color": "#ffffff", "line-width": ["interpolate", ["linear"], ["zoom"], 11, 0.6, 15, 1.6], "line-opacity": 0.9 } }, firstLabel);
  map.addLayer({ id: "faults", type: "line", source: "faults",
    paint: { "line-color": COLORS.fault, "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1, 14, 2.2], "line-dasharray": [3, 1.5] } });

  map.addLayer({ id: "footprints", type: "fill", source: "footprints", minzoom: FOOTPRINT_ZOOM - 0.5,
    paint: { "fill-color": step("score", SCORE_BREAKS, COLORS.score),
      "fill-opacity": ["interpolate", ["linear"], ["zoom"], FOOTPRINT_ZOOM - 0.5, 0, FOOTPRINT_ZOOM, 0.95] } });
  map.addLayer({ id: "footprints-ring", type: "line", source: "footprints", minzoom: FOOTPRINT_ZOOM - 0.5,
    filter: ["==", ["get", "retro"], 0], paint: { "line-color": COLORS.ring, "line-width": 2.2 } });
  map.addLayer({ id: "points", type: "circle", source: "buildings",
    paint: {
      "circle-color": step("score", SCORE_BREAKS, COLORS.score),
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, ["case", ["==", ["get", "status"], "retrofitted"], 1.6, 3.2],
        15, ["case", ["==", ["get", "status"], "retrofitted"], 4.5, 6.5]],
      "circle-stroke-color": ["case", ["==", ["get", "status"], "retrofitted"], "rgba(255,255,255,0.8)", COLORS.ring],
      "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 10, ["case", ["==", ["get", "status"], "retrofitted"], 0.3, 1.2],
        15, ["case", ["==", ["get", "status"], "retrofitted"], 0.8, 2]],
      "circle-opacity": ["interpolate", ["linear"], ["zoom"], FOOTPRINT_ZOOM, 1, FOOTPRINT_ZOOM + 0.6, 0],
      "circle-stroke-opacity": ["interpolate", ["linear"], ["zoom"], FOOTPRINT_ZOOM, 1, FOOTPRINT_ZOOM + 0.6, 0],
    } });
  map.addLayer({ id: "selected-fp", type: "line", source: "footprints", filter: ["==", ["get", "id"], -1],
    paint: { "line-color": "#2a78d6", "line-width": 3.5 } });
  map.addLayer({ id: "selected-pt", type: "circle", source: "buildings", filter: ["==", ["get", "id"], -1],
    paint: { "circle-radius": 9, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#2a78d6", "circle-stroke-width": 3 } });
  map.addLayer({ id: "epicenter", type: "symbol", source: "epicenter",
    layout: { "text-field": "★", "text-size": 24, "text-allow-overlap": true },
    paint: { "text-color": "#c4401b", "text-halo-color": "#ffffff", "text-halo-width": 2 } });

  legends();
  fillStats();
  wireControls();
  wireSearch();
  renderMetric();
});

function legends() {
  const ramp = (colors, ticks) => colors.map((c, i) => `<div><div class="bin" style="--c:${c}"></div><div class="tick">${ticks[i]}</div></div>`).join("");
  $("legend-score").innerHTML = ramp(COLORS.score, ["0", ...SCORE_BREAKS.map(String)]);
  $("legend-mmi").innerHTML = ramp(COLORS.mmi, ["<6", ...MMI_BREAKS.map((b) => b.toFixed(1))]);
}

function fillStats() {
  $("s-buildings").textContent = fmtInt(stats.buildings);
  $("s-pct-retro").textContent = stats.pct_retrofitted.toFixed(1);
  $("s-unretro").textContent = fmtInt(stats.unretrofitted);
  $("s-liq").textContent = fmtInt(stats.in_liquefaction);
  $("s-high-res").textContent = `~${fmtInt(Math.round(stats.high_residents / 100) * 100)}`;
}

function buildingFilter() {
  const parts = ["all"];
  if ($("only-unretro").checked) parts.push(["!=", ["get", "status"], "retrofitted"]);
  if ($("only-high").checked) parts.push([">=", ["get", "score"], stats.high_cut]);
  return parts.length > 1 ? parts : null;
}

function applyFilters() {
  const f = buildingFilter();
  map.setFilter("points", f);
  // Footprints only carry id, score and retro, so filter them by id against the points' rules.
  if (!f) { map.setFilter("footprints", null); map.setFilter("footprints-ring", ["==", ["get", "retro"], 0]); return; }
  const keep = [...byId.values()].filter((b) => (!$("only-unretro").checked || b.properties.status !== "retrofitted")
    && (!$("only-high").checked || b.properties.score >= stats.high_cut)).map((b) => b.properties.id);
  const inKeep = ["in", ["get", "id"], ["literal", keep]];
  map.setFilter("footprints", inKeep);
  map.setFilter("footprints-ring", ["all", inKeep, ["==", ["get", "retro"], 0]]);
}

function wireControls() {
  const vis = (ids, on) => ids.forEach((id) => map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
  $("lyr-shaking").addEventListener("change", (e) => vis(["shaking"], e.target.checked));
  $("lyr-liq").addEventListener("change", (e) => vis(["liq", "liq-line"], e.target.checked));
  $("lyr-ls").addEventListener("change", (e) => vis(["ls", "ls-line"], e.target.checked));
  $("lyr-faults").addEventListener("change", (e) => vis(["faults", "epicenter"], e.target.checked));
  $("only-unretro").addEventListener("change", applyFilters);
  $("only-high").addEventListener("change", applyFilters);
  $("metric").addEventListener("change", renderMetric);
  $("collapse").addEventListener("click", () => {
    const collapsed = $("panel").classList.toggle("collapsed");
    $("collapse").setAttribute("aria-expanded", String(!collapsed));
  });
  // Browsers restore form state on reload without firing change events. Push the restored state to the map.
  ["lyr-shaking", "lyr-liq", "lyr-ls", "lyr-faults"].forEach((id) => $(id).dispatchEvent(new Event("change")));
  applyFilters();

  for (const layer of ["points", "footprints"]) {
    map.on("mouseenter", layer, () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = ""; });
  }

  map.on("click", (e) => {
    const pad = 6;
    const box = [[e.point.x - pad, e.point.y - pad], [e.point.x + pad, e.point.y + pad]];
    const hit = map.queryRenderedFeatures(box, { layers: ["footprints", "points"] })[0];
    if (hit) return showBuilding(hit.properties.id, e.lngLat);
    const n = map.getLayoutProperty("nta-fill", "visibility") === "visible"
      && map.queryRenderedFeatures(e.point, { layers: ["nta-fill"] })[0];
    if (n) return ntaPopup(e.lngLat, n.properties);
    const cell = map.getLayoutProperty("shaking", "visibility") !== "none"
      && map.queryRenderedFeatures(e.point, { layers: ["shaking"] })[0];
    if (cell) cellPopup(e.lngLat, cell.properties);
  });
}

function popup(lngLat, html) {
  return new maplibregl.Popup({ maxWidth: "320px" }).setLngLat(lngLat).setHTML(html).addTo(map);
}

const mmiRoman = (v) => ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][Math.max(0, Math.min(9, Math.round(v) - 1))];

function bar(label, value, weight) {
  return `<div class="bar"><span class="bl">${label}<span class="w">× ${weight.toFixed(2)}</span></span>
    <span class="track"><span class="fill" style="width:${Math.round(value * 100)}%"></span></span><span class="bv">${value.toFixed(2)}</span></div>`;
}

function showBuilding(id, lngLat) {
  const f = byId.get(id);
  if (!f) return;
  const p = f.properties;
  map.setFilter("selected-fp", ["==", ["get", "id"], id]);
  map.setFilter("selected-pt", ["==", ["get", "id"], id]);
  const [color, label] = STATUS[p.status];
  const w = stats.weights;
  popup(lngLat ?? f.geometry.coordinates, `<div class="pop">
    <h3>${escapeHtml(p.addr)}</h3>
    <div class="sub">${escapeHtml(p.nhood)} · tier ${p.tier}${p.yr ? ` · built ${p.yr}` : ""}${p.units ? (p.lot_n > 1 ? ` · ${p.units} units on a lot shared by ${p.lot_n} listed buildings` : ` · ${p.units} units`) : ""}${p.res ? ` · ~${fmtInt(p.res)} residents` : ""}</div>
    <div class="tag" style="--c:${color}">${label}</div>
    <div class="score"><span class="big">${p.score.toFixed(2)}</span> risk score · rank ${fmtInt(p.rank)} of ${fmtInt(stats.buildings)}${p.hi ? " · <b>top 20%</b>" : ""}</div>
    <div class="bars">${bar("Shaking", p.c_s, w.shaking)}${bar("Ground failure", p.c_g, w.ground_failure)}${bar("Vulnerability", p.c_v, w.vulnerability)}${bar("Not retrofitted", p.c_r, w.retrofit)}</div>
    <dl>
      <dt>Shaking</dt><dd>MMI ${p.mmi.toFixed(1)} (${mmiRoman(p.mmi)}) · ${p.pga.toFixed(0)}% g · ${p.pgv.toFixed(0)} cm/s</dd>
      <dt>CGS zones</dt><dd>${[p.liq && "Liquefaction", p.ls && "Landslide"].filter(Boolean).join(", ") || "None"}</dd>
      <dt>Liquefaction prob.</dt><dd>${escapeHtml(p.lp ?? "n/a")} (HayWired)</dd>
      <dt>Hayward Fault</dt><dd>${p.hay_km} km away</dd>
    </dl></div>`).on("close", () => {
    map.setFilter("selected-fp", ["==", ["get", "id"], -1]);
    map.setFilter("selected-pt", ["==", ["get", "id"], -1]);
  });
}

function ntaPopup(lngLat, p) {
  popup(lngLat, `<div class="pop">
    <h3>${escapeHtml(p.nhood)}</h3>
    <div class="sub">${fmtInt(p.soft_story_buildings)} soft-story buildings</div>
    <dl>
      <dt>Not retrofitted</dt><dd>${fmtInt(p.unretrofitted)}</dd>
      <dt>In top 20% by score</dt><dd>${fmtInt(p.high_score_buildings)}</dd>
      <dt>Units in top-20% buildings</dt><dd>${fmtInt(p.units_in_high_score)}</dd>
      <dt>Est. residents in top 20%</dt><dd>${fmtInt(p.est_residents_in_high_score)}</dd>
      <dt>In a liquefaction zone</dt><dd>${fmtInt(p.in_cgs_liquefaction_zone)}</dd>
      <dt>Mean shaking (MMI)</dt><dd>${p.soft_story_buildings ? Number(p.mean_mmi).toFixed(2) : "n/a"}</dd>
    </dl></div>`);
}

function cellPopup(lngLat, p) {
  popup(lngLat, `<div class="pop">
    <h3>ShakeMap cell</h3>
    <div class="sub">About 1.5 × 1.85 km. Every building in this square gets these values.</div>
    <dl>
      <dt>Shaking (MMI)</dt><dd>${p.mmi.toFixed(2)} (${mmiRoman(p.mmi)})</dd>
      <dt>Peak ground accel.</dt><dd>${p.pga.toFixed(1)}% g</dd>
      <dt>Peak ground velocity</dt><dd>${p.pgv.toFixed(1)} cm/s</dd>
      <dt>0.3 s spectral accel.</dt><dd>${p.psa03.toFixed(1)}% g</dd>
    </dl></div>`);
}

function renderMetric() {
  const key = $("metric").value;
  const on = key !== "off";
  map.setLayoutProperty("nta-fill", "visibility", on ? "visible" : "none");
  const tableKey = on ? key : "units_in_high_score";
  const m = METRICS[tableKey];
  if (on) {
    map.setPaintProperty("nta-fill", "fill-color", step(key, m.breaks, COLORS.nta));
    const ticks = ["0", ...m.breaks.map((b) => (b >= 1000 ? `${b / 1000}K` : String(b)))];
    $("legend-nta").innerHTML = COLORS.nta.map((c, i) => `<div><div class="bin" style="--c:${c}"></div><div class="tick">${ticks[i]}</div></div>`).join("");
  } else {
    $("legend-nta").innerHTML = "";
  }
  const rows = ntaData.features.filter((f) => f.properties[tableKey] > 0)
    .sort((a, b) => b.properties[tableKey] - a.properties[tableKey]).slice(0, 10);
  $("top-metric").textContent = on ? m.label : "Units in top 20%";
  const tbody = document.querySelector("#top-table tbody");
  tbody.innerHTML = rows.map((f, i) => `<tr><td><button data-i="${i}">${escapeHtml(f.properties.nhood)}</button></td>
    <td class="num">${m.fmt(Number(f.properties[tableKey]))}</td></tr>`).join("");
  tbody.querySelectorAll("button").forEach((btn) => btn.addEventListener("click", () => {
    const f = rows[Number(btn.dataset.i)];
    map.fitBounds(bbox(f.geometry), { padding: { top: 40, bottom: 40, left: window.innerWidth > 640 ? 400 : 40, right: 40 }, maxZoom: 15 });
  }));
}

function bbox(geom) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const walk = (c) => {
    if (typeof c[0] === "number") {
      minX = Math.min(minX, c[0]); maxX = Math.max(maxX, c[0]);
      minY = Math.min(minY, c[1]); maxY = Math.max(maxY, c[1]);
    } else c.forEach(walk);
  };
  walk(geom.coordinates);
  return [[minX, minY], [maxX, maxY]];
}

/* ---------- Search: soft-story addresses only, matched in the browser ---------- */

function wireSearch() {
  const input = $("q"), list = $("results"), status = $("search-status");
  const index = [...byId.values()].map((f) => ({ id: f.properties.id, addr: f.properties.addr, key: f.properties.addr.toUpperCase(), nhood: f.properties.nhood }));
  let results = [], active = -1;

  const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; };
  const highlight = (i) => {
    active = i;
    [...list.children].forEach((li, j) => li.setAttribute("aria-selected", String(j === i)));
    input.setAttribute("aria-activedescendant", i >= 0 ? `res-${i}` : "");
  };

  input.addEventListener("input", () => {
    const words = input.value.trim().toUpperCase().split(/\s+/).filter(Boolean);
    status.textContent = "";
    if (!words.length || input.value.trim().length < 2) return close();
    results = index.filter((r) => words.every((w) => r.key.includes(w)))
      .sort((a, b) => Number(!a.key.startsWith(words[0])) - Number(!b.key.startsWith(words[0])) || a.key.localeCompare(b.key))
      .slice(0, 8);
    if (!results.length) { close(); status.textContent = "No soft-story building at that address. The list only covers soft-story buildings."; return; }
    list.innerHTML = results.map((r, i) => `<li id="res-${i}" role="option" aria-selected="false" data-i="${i}">${escapeHtml(r.addr)}<span class="boro">${escapeHtml(r.nhood)}</span></li>`).join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    highlight(-1);
  });
  input.addEventListener("keydown", (e) => {
    if (list.hidden) return;
    if (e.key === "ArrowDown") { e.preventDefault(); highlight(Math.min(active + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); highlight(Math.max(active - 1, 0)); }
    else if (e.key === "Escape") close();
  });
  $("search").addEventListener("submit", (e) => {
    e.preventDefault();
    if (results.length) choose(results[Math.max(active, 0)]);
  });
  list.addEventListener("mousedown", (e) => {
    const li = e.target.closest("li");
    if (li) { e.preventDefault(); choose(results[Number(li.dataset.i)]); }
  });
  input.addEventListener("blur", () => setTimeout(close, 150));

  function choose(r) {
    close();
    input.value = r.addr;
    const f = byId.get(r.id);
    const pad = window.innerWidth > 640 ? { left: 380, top: 0, right: 0, bottom: 0 } : { bottom: window.innerHeight * 0.5, top: 0, left: 0, right: 0 };
    map.flyTo({ center: f.geometry.coordinates, zoom: 17, padding: pad, essential: true });
    map.once("moveend", () => showBuilding(r.id));
  }
}
