/* SkySentry v2 front-end: vanilla JS, Chart.js and Leaflet. */
(() => {
  'use strict';

  // ---------- helpers ----------
  const $ = (sel) => document.querySelector(sel);
  const store = {
    get(key, fallback) {
      try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
    },
    set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
  };
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const state = {
    place: null,
    data: null,
    overview: [],
    levels: [],
    sensitive: store.get('ss-sensitive', false),
    unit: store.get('ss-unit', 'C'),
    loadToken: 0,
  };
  const charts = {};
  let map, tiles, markersLayer, hereMarker;

  const toUnit = (c) => (c == null ? null : state.unit === 'F' ? c * 9 / 5 + 32 : c);
  const deg = (c) => (c == null ? '--' : `${Math.round(toUnit(c))}°`);
  const hourLabel = (iso) => new Date(iso).toLocaleTimeString([], { hour: 'numeric' });
  const dayLabel = (iso, opts = { weekday: 'short' }) => new Date(`${iso.slice(0, 10)}T12:00`).toLocaleDateString([], opts);
  const compass = (d) => (d == null ? '' : ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][Math.round(d / 45) % 8]);
  const isDark = () => document.documentElement.dataset.theme === 'dark' ||
    (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);

  function toast(msg, ms = 2600) {
    const el = $('#toast');
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => { el.hidden = true; }, ms);
  }

  async function api(path) {
    const res = await fetch(path);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
    return body;
  }

  function animateNumber(el, to, ms = 900) {
    if (to == null) { el.textContent = '--'; return; }
    const from = Number(el.dataset.value || 0);
    el.dataset.value = to;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) { el.textContent = to; return; }
    const start = performance.now();
    const step = (now) => {
      const p = Math.min(1, (now - start) / ms);
      el.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
    // rAF pauses in background tabs: make sure the final value always lands
    clearTimeout(el._final);
    el._final = setTimeout(() => { el.textContent = to; }, ms + 150);
  }

  // ---------- loading a place ----------
  async function loadPlace(place, { updateUrl = true } = {}) {
    state.place = place;
    store.set('ss-place', place);
    if (updateUrl) {
      const url = new URL(location.href);
      url.searchParams.set('lat', place.lat.toFixed(3));
      url.searchParams.set('lon', place.lon.toFixed(3));
      url.searchParams.set('name', place.name);
      if (place.country) url.searchParams.set('country', place.country); else url.searchParams.delete('country');
      history.replaceState(null, '', url);
    }
    $('#app').setAttribute('aria-busy', 'true');
    $('#place-name').textContent = place.name;
    $('#place-sub').textContent = [place.admin1, place.country].filter(Boolean).join(', ') || 'Loading…';
    highlightChip();

    const token = ++state.loadToken;
    try {
      const data = await api(`/api/conditions?lat=${place.lat}&lon=${place.lon}${state.sensitive ? '&sensitive=1' : ''}`);
      if (token !== state.loadToken) return; // a newer request won
      state.data = data;
      render();
    } catch (err) {
      if (token === state.loadToken) toast(`⚠️ ${err.message}`, 4000);
    } finally {
      if (token === state.loadToken) $('#app').setAttribute('aria-busy', 'false');
    }
  }

  // ---------- rendering ----------
  function render() {
    const d = state.data;
    if (!d) return;
    const { air, weather, insights } = d;
    const level = air.level;
    document.documentElement.style.setProperty('--accent', level.color);

    // Hero
    const p = state.place;
    $('#place-sub').textContent = [p.admin1, p.country].filter(Boolean).join(', ') ||
      `${p.lat.toFixed(2)}°, ${p.lon.toFixed(2)}°`;
    document.title = `${air.aqi ?? '--'} AQI · ${p.name} · SkySentry`;
    animateNumber($('#aqi-value'), air.aqi);
    $('#mascot').textContent = level.mascot;
    $('#aqi-label').textContent = level.label;
    const frac = air.aqi == null ? 0 : Math.min(air.aqi, 300) / 300;
    $('#gauge-fill').style.strokeDasharray = `${(433.5 * frac).toFixed(1)} 578`;
    $('#verdict-title').textContent = insights.verdict.title;
    $('#verdict-text').textContent = insights.verdict.text;

    const bw = insights.best_window;
    const bwEl = $('#best-window');
    if (bw) {
      const range = `${hourLabel(bw.start)} – ${hourLabel(bw.start.slice(0, 11) + String(bw.end_hour % 24).padStart(2, '0') + ':00')}`;
      const bwTitle = bw.aqi <= 100 ? '🌟 <b>Best time to go outside:</b>' : '🕐 <b>Least polluted time:</b>';
      bwEl.innerHTML = `${bwTitle} ${esc(bw.day)}, ${esc(range)}
        <span class="muted">· AQI ${bw.aqi}${bw.feels_like != null ? ` · feels ${deg(bw.feels_like)}` : ''}${bw.rain_chance ? ` · ${bw.rain_chance}% rain` : ''}</span>`;
      bwEl.hidden = false;
    } else {
      bwEl.hidden = true;
    }

    // Weather now
    const now = weather.now;
    const today = weather.daily[0] || {};
    $('#wx-icon').textContent = now.icon;
    $('#wx-temp').textContent = deg(now.temperature);
    $('#wx-label').textContent = `${now.label} · H ${deg(today.tmax)}  L ${deg(today.tmin)}`;
    $('#local-time').textContent = d.location.local_time
      ? `🕒 ${new Date(d.location.local_time).toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })} local`
      : '';
    const stats = [
      ['🤒 Feels like', deg(now.feels_like)],
      ['💧 Humidity', now.humidity != null ? `${now.humidity}%` : '--'],
      ['💨 Wind', now.wind != null ? `${Math.round(now.wind)} km/h ${compass(now.wind_direction)}` : '--'],
      ['🕶️ UV index', now.uv != null ? Math.round(now.uv) : '--'],
      ['🌅 Sunrise', today.sunrise ? hourMinute(today.sunrise) : '--'],
      ['🌇 Sunset', today.sunset ? hourMinute(today.sunset) : '--'],
    ];
    $('#wx-stats').innerHTML = stats.map(([k, v]) => `<div class="stat"><div class="k">${k}</div><div class="v">${esc(v)}</div></div>`).join('');
    $('#hourly').innerHTML = weather.hourly.map((h, i) => `
      <div class="hour"><div class="t">${i === 0 ? 'Now' : esc(hourLabel(h.time))}</div>
      <div class="i">${h.icon}</div><div class="d">${deg(h.temperature)}</div>
      <div class="p">${h.precip_prob >= 20 ? `💧${h.precip_prob}%` : ''}</div></div>`).join('');

    // Activities
    const statusText = { go: '✅ Go for it', caution: '⚠️ Take care', avoid: '⛔ Skip it' };
    $('#activities').innerHTML = insights.activities.map((a) => `
      <div class="card activity" data-status="${a.status}">
        <div class="ico">${a.icon}</div>
        <div class="name">${esc(a.name)}</div>
        <div class="status">${statusText[a.status]}</div>
        <div class="reason">${esc(a.reason)}</div>
      </div>`).join('');

    // Pollutants
    $('#pollutants').innerHTML = air.pollutants.map((pol) => {
      const ratio = pol.ratio ?? 0;
      const color = ratio <= 0.5 ? '#22c55e' : ratio <= 1 ? '#eab308' : ratio <= 2 ? '#f97316' : '#ef4444';
      const value = pol.value == null ? '--' : pol.value >= 100 ? Math.round(pol.value) : pol.value.toFixed(1);
      return `
      <button class="card pollutant" aria-expanded="false">
        <div class="top"><span class="sym">${esc(pol.name)}</span>${pol.key === air.dominant ? '<span class="dom">MAIN</span>' : ''}</div>
        <div class="full">${esc(pol.full)}</div>
        <div class="val">${value} <small>${esc(pol.unit)}</small></div>
        <div class="bar"><i data-w="${Math.min(100, ratio * 50)}" style="background:${color}"></i></div>
        <div class="who">${pol.ratio == null ? 'No reading' : `${Math.round(ratio * 100)}% of WHO limit (${pol.who})`}</div>
        <div class="more"><b>What:</b> ${esc(pol.what)}<br><b>Sources:</b> ${esc(pol.sources)}</div>
      </button>`;
    }).join('');
    requestAnimationFrame(() => document.querySelectorAll('.bar > i').forEach((b) => { b.style.width = `${b.dataset.w}%`; }));
    $('#tips').innerHTML = air.tips.map((t) => `<li>${esc(t)}</li>`).join('');

    // 7-day cards
    $('#days').innerHTML = weather.daily.map((day, i) => `
      <div class="card day ${i === 0 ? 'today' : ''}">
        <div class="dn">${i === 0 ? 'Today' : esc(dayLabel(day.date))}</div>
        <div class="dd">${esc(dayLabel(day.date, { month: 'short', day: 'numeric' }))}</div>
        <div class="di" title="${esc(day.label)}">${day.icon}</div>
        <div class="dt">${deg(day.tmax)} <span>${deg(day.tmin)}</span></div>
        <div class="dr">${day.precip_prob ? `💧 ${day.precip_prob}%` : '&nbsp;'}</div>
        <div class="alerts">${day.alerts.map((a) => `<span class="alert ${a.level}">${a.icon} ${esc(a.text)}</span>`).join('')}</div>
      </div>`).join('');

    renderCharts();
    renderScaleDetail(level.key);
    updateHereMarker();
    syncFeatured();
  }

  // Keep the chip / map bubble for the selected city identical to the detailed reading
  function syncFeatured() {
    const d = state.data;
    const c = state.overview.find((x) => Math.abs(x.lat - state.place.lat) < 0.01 && Math.abs(x.lon - state.place.lon) < 0.01);
    if (!c || !d || c.aqi === d.air.aqi) return;
    Object.assign(c, { aqi: d.air.aqi, color: d.air.level.color, label: d.air.level.label, mascot: d.air.level.mascot });
    renderChips();
    renderMapMarkers();
  }

  function hourMinute(iso) {
    return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  }

  // ---------- charts ----------
  function chartDefaults() {
    Chart.defaults.font.family = '"Plus Jakarta Sans", system-ui, sans-serif';
    Chart.defaults.color = css('--muted');
    Chart.defaults.borderColor = css('--border');
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 10;
  }

  function makeChart(id, config) {
    charts[id]?.destroy();
    charts[id] = new Chart(document.getElementById(id), config);
  }

  function renderCharts() {
    const d = state.data;
    if (!d || typeof Chart === 'undefined') return;
    chartDefaults();
    const unit = `°${state.unit}`;

    // AQI forecast
    const fc = d.air.forecast;
    makeChart('aqi-chart', {
      type: 'bar',
      data: {
        labels: fc.map((f) => f.time),
        datasets: [{ label: 'US AQI', data: fc.map((f) => f.aqi), backgroundColor: fc.map((f) => f.color),
          borderRadius: 4, barPercentage: 1, categoryPercentage: 0.9 }],
      },
      options: {
        responsive: true, maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            title: (items) => new Date(fc[items[0].dataIndex].time).toLocaleString([], { weekday: 'short', hour: 'numeric' }),
            label: (item) => ` AQI ${item.raw} · ${fc[item.dataIndex].label}`,
          } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: false,
            callback: (v, i) => (fc[i].time.endsWith('T00:00') || i === 0 ? dayLabel(fc[i].time) : (fc[i].time.endsWith('T12:00') ? '·' : '')) } },
          y: { beginAtZero: true, suggestedMax: 100, title: { display: true, text: 'US AQI' } },
        },
      },
    });

    // Week: floating temperature bars + rain
    const days = d.weather.daily;
    makeChart('week-chart', {
      data: {
        labels: days.map((x, i) => (i === 0 ? 'Today' : dayLabel(x.date))),
        datasets: [
          { type: 'bar', label: `Temperature (${unit})`, data: days.map((x) => [toUnit(x.tmin), toUnit(x.tmax)]),
            backgroundColor: 'rgba(249, 115, 22, .75)', borderRadius: 999, barPercentage: 0.45, yAxisID: 'y' },
          { type: 'line', label: 'Rain (mm)', data: days.map((x) => x.precip_sum), borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, .15)', fill: true, tension: 0.35, pointRadius: 3, yAxisID: 'y1' },
        ],
      },
      options: {
        plugins: { tooltip: { callbacks: { label: (item) => (item.datasetIndex === 0
          ? ` ${Math.round(item.raw[0])}${unit} – ${Math.round(item.raw[1])}${unit}` : ` ${item.raw ?? 0} mm rain`) } } },
        scales: {
          x: { grid: { display: false } },
          y: { title: { display: true, text: unit } },
          y1: { position: 'right', beginAtZero: true, grid: { display: false }, title: { display: true, text: 'mm' } },
        },
      },
    });

    // History
    const h = d.history;
    makeChart('history-chart', {
      data: {
        labels: h.dates.map((x) => dayLabel(x, { month: 'short', day: 'numeric' })),
        datasets: [
          { type: 'line', label: `High (${unit})`, data: h.tmax.map(toUnit), borderColor: '#f97316', pointRadius: 0, tension: 0.35, yAxisID: 'y' },
          { type: 'line', label: `Low (${unit})`, data: h.tmin.map(toUnit), borderColor: '#38bdf8', pointRadius: 0, tension: 0.35,
            fill: '-1', backgroundColor: 'rgba(148, 163, 184, .15)', yAxisID: 'y' },
          { type: 'bar', label: 'Rain (mm)', data: h.precip, backgroundColor: 'rgba(59, 130, 246, .45)', borderRadius: 3, yAxisID: 'y1' },
        ],
      },
      options: {
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 6, maxRotation: 0 } },
          y: { title: { display: true, text: unit } },
          y1: { position: 'right', beginAtZero: true, grid: { display: false }, title: { display: true, text: 'mm' } },
        },
      },
    });
  }

  // ---------- featured chips & map ----------
  function renderChips() {
    $('#chips').innerHTML = state.overview.map((c, i) => `
      <button class="chip" data-i="${i}" style="--chip-color:${c.color}" title="${esc(c.label)}">
        <span class="chip-aqi">${c.aqi ?? '?'}</span>${esc(c.name)}
      </button>`).join('');
    highlightChip();
  }

  function highlightChip() {
    document.querySelectorAll('.chip').forEach((chip) => {
      const c = state.overview[chip.dataset.i];
      const active = state.place && Math.abs(c.lat - state.place.lat) < 0.01 && Math.abs(c.lon - state.place.lon) < 0.01;
      chip.classList.toggle('active', !!active);
    });
  }

  function cityToPlace(c) {
    return { name: c.name, country: c.country, lat: c.lat, lon: c.lon };
  }

  function setTiles() {
    if (!map || tiles) return; // dark mode is handled with a CSS filter on the tile pane
    tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 12,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
  }

  function initMap() {
    if (typeof L === 'undefined') return;
    map = L.map('map', { worldCopyJump: true, scrollWheelZoom: false, minZoom: 2 }).setView([25, 10], 2);
    setTiles();
    markersLayer = L.layerGroup().addTo(map);
    map.on('click', (e) => {
      const lon = ((e.latlng.lng + 540) % 360) - 180;
      loadPlace({ name: 'Selected spot', lat: e.latlng.lat, lon });
      document.querySelector('.hero').scrollIntoView({ behavior: 'smooth' });
    });
  }

  function renderMapMarkers() {
    if (!markersLayer) return;
    markersLayer.clearLayers();
    state.overview.forEach((c) => {
      const icon = L.divIcon({ className: '', html: `<div class="aqi-marker" style="background:${c.color}">${c.aqi ?? '?'}</div>`,
        iconSize: [40, 40], iconAnchor: [20, 20] });
      const marker = L.marker([c.lat, c.lon], { icon, title: `${c.name}: AQI ${c.aqi}` }).addTo(markersLayer);
      const box = document.createElement('div');
      box.className = 'popup';
      box.innerHTML = `<b>${c.mascot} ${esc(c.name)}</b><br>AQI <b>${c.aqi ?? '--'}</b> · ${esc(c.label)}<br>${c.icon} ${deg(c.temperature)} · ${esc(c.weather)}<br><span class="muted">${esc(c.country)}</span>`;
      const btn = document.createElement('button');
      btn.className = 'btn';
      btn.textContent = 'See full report →';
      btn.addEventListener('click', () => { loadPlace(cityToPlace(c)); document.querySelector('.hero').scrollIntoView({ behavior: 'smooth' }); });
      box.appendChild(btn);
      marker.bindPopup(box);
    });
  }

  function updateHereMarker() {
    if (!map || !state.place) return;
    hereMarker?.remove();
    hereMarker = L.circleMarker([state.place.lat, state.place.lon], {
      radius: 9, color: '#fff', weight: 3, fillColor: css('--accent') || '#38bdf8', fillOpacity: 1,
    }).addTo(map).bindTooltip(`📍 ${state.place.name}`);
  }

  // ---------- AQI scale ----------
  function renderScale() {
    const ranges = ['0–50', '51–100', '101–150', '151–200', '201–300', '301+'];
    const short = ['Good', 'Moderate', 'Sensitive', 'Unhealthy', 'Very bad', 'Hazardous'];
    $('#scale').innerHTML = state.levels.map((l, i) => `
      <button role="tab" data-key="${l.key}" style="background:${l.color}" aria-selected="false">
        ${short[i]}<small>${ranges[i]}</small></button>`).join('');
  }

  function renderScaleDetail(key) {
    const l = state.levels.find((x) => x.key === key) || state.levels[0];
    if (!l) return;
    document.querySelectorAll('#scale button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.key === l.key)));
    $('#scale-detail').innerHTML = `<div class="big">${l.mascot}</div>
      <div><h3 style="margin:0;color:${l.color}">${esc(l.label)}</h3><p>${esc(l.summary)}</p><p class="muted">${esc(l.advice)}</p></div>`;
  }

  // ---------- search ----------
  function initSearch() {
    const input = $('#search');
    const list = $('#search-results');
    let results = [];
    let active = -1;
    let timer;

    const close = () => { list.hidden = true; input.setAttribute('aria-expanded', 'false'); active = -1; };
    const choose = (r) => {
      close();
      input.value = '';
      input.blur();
      loadPlace({ name: r.name, admin1: r.admin1, country: r.country, lat: r.lat, lon: r.lon });
    };
    const paint = () => {
      list.innerHTML = results.length
        ? results.map((r, i) => `<li role="option" data-i="${i}" aria-selected="${i === active}">
            <span>${esc(r.name)}</span><span class="where">${esc([r.admin1, r.country].filter(Boolean).join(', '))}</span></li>`).join('')
        : '<li aria-disabled="true"><span class="muted">No places found 🤷</span></li>';
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    };

    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) { close(); return; }
      timer = setTimeout(async () => {
        try { results = await api(`/api/search?q=${encodeURIComponent(q)}`); active = -1; paint(); } catch (e) { toast(`⚠️ ${e.message}`); }
      }, 250);
    });
    input.addEventListener('keydown', (e) => {
      if (list.hidden) return;
      if (e.key === 'ArrowDown') { active = Math.min(results.length - 1, active + 1); paint(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { active = Math.max(0, active - 1); paint(); e.preventDefault(); }
      else if (e.key === 'Enter' && results.length) { choose(results[Math.max(0, active)]); e.preventDefault(); }
      else if (e.key === 'Escape') close();
    });
    list.addEventListener('mousedown', (e) => {
      const li = e.target.closest('li[data-i]');
      if (li) choose(results[li.dataset.i]);
    });
    input.addEventListener('blur', () => setTimeout(close, 150));
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement !== input) { e.preventDefault(); input.focus(); }
    });
  }

  // ---------- controls ----------
  function initControls() {
    const sens = $('#sensitive');
    const units = $('#units');
    sens.setAttribute('aria-pressed', String(state.sensitive));
    units.textContent = `°${state.unit}`;

    sens.addEventListener('click', () => {
      state.sensitive = !state.sensitive;
      store.set('ss-sensitive', state.sensitive);
      sens.setAttribute('aria-pressed', String(state.sensitive));
      toast(state.sensitive ? '🫁 Sensitive mode on: stricter health advice' : 'Sensitive mode off');
      if (state.place) loadPlace(state.place, { updateUrl: false });
    });
    units.addEventListener('click', () => {
      state.unit = state.unit === 'C' ? 'F' : 'C';
      store.set('ss-unit', state.unit);
      units.textContent = `°${state.unit}`;
      render();
      renderMapMarkers();
    });
    $('#theme').addEventListener('click', () => {
      const next = isDark() ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      store.set('ss-theme', next);
      setTiles();
      renderCharts();
    });
    $('#locate').addEventListener('click', () => {
      if (!navigator.geolocation) { toast('Geolocation is not supported by this browser'); return; }
      toast('📡 Finding you…');
      navigator.geolocation.getCurrentPosition(
        (pos) => loadPlace({ name: 'My location', lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => toast('Could not get your location. Try searching instead.'),
        { timeout: 10000, maximumAge: 600000 },
      );
    });
    $('#share').addEventListener('click', async () => {
      const url = location.href;
      try {
        if (navigator.share && matchMedia('(pointer: coarse)').matches) {
          await navigator.share({ title: 'SkySentry', text: `Air quality in ${state.place?.name}`, url });
        } else {
          await navigator.clipboard.writeText(url);
          toast('🔗 Link copied. Share it with friends!');
        }
      } catch { toast(url, 5000); }
    });
    $('#chips').addEventListener('click', (e) => {
      const chip = e.target.closest('.chip');
      if (chip) loadPlace(cityToPlace(state.overview[chip.dataset.i]));
    });
    $('#pollutants').addEventListener('click', (e) => {
      const card = e.target.closest('.pollutant');
      if (card) card.setAttribute('aria-expanded', String(card.getAttribute('aria-expanded') !== 'true'));
    });
    $('#scale').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-key]');
      if (b) renderScaleDetail(b.dataset.key);
    });
    // Follow OS theme changes when the user has not chosen one
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (!document.documentElement.dataset.theme) { setTiles(); renderCharts(); }
    });
  }

  function initReveal() {
    const blocks = document.querySelectorAll('.block');
    if (!('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver((entries) => entries.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add('visible'); io.unobserve(en.target); }
    }), { threshold: 0.08 });
    blocks.forEach((b) => { b.classList.add('reveal'); io.observe(b); });
  }

  // ---------- boot ----------
  async function boot() {
    initControls();
    initSearch();
    initMap();
    initReveal();

    const params = new URLSearchParams(location.search);
    const lat = parseFloat(params.get('lat'));
    const lon = parseFloat(params.get('lon'));
    const fromUrl = Number.isFinite(lat) && Number.isFinite(lon) ? { name: params.get('name') || 'Selected spot', country: params.get('country') || undefined, lat, lon } : null;
    const initial = fromUrl || store.get('ss-place', null) || { name: 'New York', country: 'United States', lat: 40.7128, lon: -74.006 };
    loadPlace(initial, { updateUrl: !!fromUrl });

    try {
      const scale = await api('/api/scale');
      state.levels = scale.levels;
      renderScale();
      renderScaleDetail(state.data?.air.level.key || 'good');
    } catch { /* non-critical */ }
    try {
      state.overview = await api('/api/overview');
      renderChips();
      renderMapMarkers();
      if (state.data) syncFeatured();
    } catch (e) { toast(`⚠️ ${e.message}`); }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
