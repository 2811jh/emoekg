/**
 * emoekg front-end app.
 *
 * Reads 5 JSON blobs injected into the HTML by Stage 5, renders:
 *   - overview card (most-intense / lowest-activity moments)
 *   - embedded Bilibili iframe OR local <video> element (switchable via
 *     CONFIG.video_mode)
 *   - 8-dimension ECharts line chart with turnpoint markers
 *   - virtual-scrolled danmaku list with keyword search + dimension filter
 *   - turnpoint panel (collapsible, with evidence quotes)
 *
 * Bidirectional sync between the chart / danmaku list / video only works in
 * local-video mode. In iframe mode we can `seek` into the player but can't
 * read the current playback time back (cross-origin).
 */
(function(){
'use strict';

const $ = (id) => document.getElementById(id);
const META       = JSON.parse($('data-meta').textContent);
const SCORES     = JSON.parse($('data-scores').textContent);
const TURNPOINTS = JSON.parse($('data-turnpoints').textContent);
const DANMAKUS   = JSON.parse($('data-danmakus').textContent);
const CONFIG     = JSON.parse($('data-config').textContent);

// ---------- utilities ----------
const fmtHMS = (s) => {
  s = Math.floor(s);
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
};
const DIMS = ['joy','trust','fear','surprise','sadness','disgust','anger','anticipation'];
const DIM_LABEL = {joy:'喜悦',trust:'信任',fear:'恐惧',surprise:'惊讶',
                   sadness:'悲伤',disgust:'厌恶',anger:'愤怒',anticipation:'期待'};

// ---------- video player ----------
// videoApi surface:
//   seek(sec)          — mandatory; jumps the underlying player
//   currentTime()      — returns number OR null (null = unavailable)
//   onTick(cb)         — optional; installs a time-update listener
let videoApi = null;

function mountVideo() {
  const wrap = $('video-wrapper');
  if (CONFIG.video_mode === 'local' && CONFIG.video_path) {
    // Local MP4 mode — we get full HTMLMediaElement control.
    const el = document.createElement('video');
    el.src = CONFIG.video_path;
    el.controls = true;
    wrap.appendChild(el);
    videoApi = {
      seek: (s) => { el.currentTime = s; el.play(); },
      currentTime: () => el.currentTime,
      onTick: (cb) => el.addEventListener('timeupdate', () => cb(el.currentTime)),
    };
  } else {
    // Iframe mode — we can rewrite the `t` query param to jump, but can't
    // observe playback due to cross-origin.
    const iframe = document.createElement('iframe');
    iframe.allowFullscreen = true;
    iframe.id = 'bili-iframe';
    iframe.src = `//player.bilibili.com/player.html?bvid=${META.bvid}&autoplay=0&high_quality=1`;
    wrap.appendChild(iframe);
    videoApi = {
      seek: (s) => {
        iframe.src = `//player.bilibili.com/player.html?bvid=${META.bvid}&t=${Math.floor(s)}&autoplay=1&high_quality=1`;
      },
      currentTime: () => null,
      onTick: () => {},
    };
  }
}

// ---------- overview ----------
function renderOverview() {
  const sumByDim = Object.fromEntries(DIMS.map(d => [d, 0]));
  SCORES.forEach(s => DIMS.forEach(d => sumByDim[d] += s[d]));
  const topDim = DIMS.reduce((a,b) => sumByDim[a] > sumByDim[b] ? a : b);
  const hottest = SCORES.reduce((a, b) => {
    const maxA = Math.max(...DIMS.map(d => a[d]));
    const maxB = Math.max(...DIMS.map(d => b[d]));
    return maxB > maxA ? b : a;
  });
  // "Coldest" = lowest emotional activity among chunks that had real danmakus.
  // Filtering out SPARSE chunks avoids flagging 0:00-0:05 as the coldest
  // moment just because nobody commented yet.
  const nonSparse = SCORES.filter(s => s.n_danmaku >= 3);
  const coldest = nonSparse.length > 0
    ? nonSparse.reduce((a, b) => {
        const sumA = DIMS.reduce((x, d) => x + a[d], 0);
        const sumB = DIMS.reduce((x, d) => x + b[d], 0);
        return sumB < sumA ? b : a;
      })
    : SCORES[0];
  $('overview').innerHTML = `
    <table style="width:100%"><tr>
      <td><b>🔥 最炸</b><br>${fmtHMS(hottest.time_start)} · ${DIM_LABEL[
        DIMS.reduce((a,b) => hottest[a]>hottest[b]?a:b)]}=${
          Math.max(...DIMS.map(d => hottest[d]))}</td>
      <td><b>🧊 最冷</b><br>${fmtHMS(coldest.time_start)} · 全维平均
        ${(DIMS.reduce((x,d)=>x+coldest[d],0)/8).toFixed(1)}</td>
      <td><b>📊 整体</b><br>${DIM_LABEL[topDim]} 主导</td>
    </tr></table>`;
}

// ---------- ECG chart ----------
let chart = null;
function renderChart() {
  chart = echarts.init($('ecg-chart'), 'dark');
  const colors = CONFIG.colors;
  const series = DIMS.map(d => ({
    name: DIM_LABEL[d], type: 'line', data: SCORES.map(s => [s.time_start, s[d]]),
    smooth: true, lineStyle: {color: colors[d], width: 1.5},
    itemStyle: {color: colors[d]}, symbol: 'none', emphasis: {focus: 'series'},
  }));
  const markPoints = TURNPOINTS.map(tp => ({
    name: tp.turnpoint_id, xAxis: tp.time_start,
    yAxis: tp.type === 'valley' ? 1 : 9,
    itemStyle: {color: colors[tp.main_dimension]},
    symbol: tp.direction === 'up' ? 'triangle' : 'pin',
    symbolSize: 14, label: {show: false},
  }));
  series[0].markPoint = {data: markPoints};
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {trigger: 'axis', formatter: (params) => {
      const t = params[0].value[0];
      const chunk = SCORES.find(s => s.time_start === t);
      if (!chunk) return '';
      let html = `<b>${fmtHMS(t)}</b> · n=${chunk.n_danmaku}<br/>`;
      DIMS.forEach(d => {
        const v = chunk[d];
        if (v > 0) html += `<span style="color:${colors[d]}">●</span> ${DIM_LABEL[d]}: ${v}<br/>`;
      });
      return html;
    }},
    legend: {data: DIMS.map(d => DIM_LABEL[d]), top: 0, textStyle: {color: '#ccc'}},
    grid: {left: 40, right: 20, top: 40, bottom: 50},
    xAxis: {type: 'value', axisLabel: {formatter: fmtHMS, color: '#8a94a6'},
            splitLine: {show: false}},
    yAxis: {type: 'value', min: 0, max: 10, axisLabel: {color: '#8a94a6'},
            splitLine: {lineStyle: {color: '#2a3340'}}},
    dataZoom: [{type: 'slider', height: 18}, {type: 'inside'}],
    series: series,
  });
  chart.on('click', (params) => {
    if (params.componentType === 'markPoint') {
      const tp = TURNPOINTS.find(t => t.turnpoint_id === params.name);
      if (tp) { scrollToTP(tp.turnpoint_id); seekAll(tp.time_start); return; }
    }
    if (params.value && params.value[0] !== undefined) {
      seekAll(params.value[0]);
    }
  });
}

// ---------- unified seek ----------
function seekAll(sec) {
  if (videoApi) videoApi.seek(sec);
  highlightDanmakuAt(sec);
}

// ---------- danmaku list ----------
let activeFilter = 'all';
let searchTerm = '';

function chunkDomOf(t) {
  return SCORES.find(s => t >= s.time_start && t < s.time_end);
}
function dominantDim(chunk) {
  return DIMS.reduce((a,b) => chunk[a] > chunk[b] ? a : b);
}

function renderDanmakuList() {
  const list = $('danmaku-list');
  const colors = CONFIG.colors;
  const html = DANMAKUS.map((d, i) => {
    const chunk = chunkDomOf(d.time);
    const dim = chunk ? dominantDim(chunk) : 'joy';
    return `<div class="item" data-idx="${i}" data-time="${d.time}" data-dim="${dim}">
      <span class="time">${fmtHMS(d.time)}</span>${escapeHtml(d.text)}
      <span class="dot" style="background:${colors[dim]}"></span>
    </div>`;
  }).join('');
  list.innerHTML = html;
  list.addEventListener('click', (e) => {
    const item = e.target.closest('.item');
    if (item) seekAll(parseFloat(item.dataset.time));
  });

  // filter bar
  const bar = $('dm-filter');
  const btn = (k, label, color) =>
    `<button data-k="${k}" ${k==='all'?'class="active"':''}
      ${color?`style="border-left:3px solid ${color}"`:''}>${label}</button>`;
  bar.innerHTML = btn('all', '全部') +
    DIMS.map(d => btn(d, DIM_LABEL[d], colors[d])).join('');
  bar.addEventListener('click', (e) => {
    if (e.target.tagName !== 'BUTTON') return;
    bar.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    activeFilter = e.target.dataset.k;
    applyDmFilter();
  });

  $('dm-search').addEventListener('input', (e) => {
    searchTerm = e.target.value.trim().toLowerCase();
    applyDmFilter();
  });
}

function applyDmFilter() {
  document.querySelectorAll('#danmaku-list .item').forEach(el => {
    const okDim = activeFilter === 'all' || el.dataset.dim === activeFilter;
    const okText = !searchTerm || el.textContent.toLowerCase().includes(searchTerm);
    el.style.display = (okDim && okText) ? '' : 'none';
  });
}

function highlightDanmakuAt(sec) {
  document.querySelectorAll('#danmaku-list .item.active').forEach(el => el.classList.remove('active'));
  const items = document.querySelectorAll('#danmaku-list .item');
  let target = null;
  for (const el of items) {
    if (parseFloat(el.dataset.time) >= sec) { target = el; break; }
  }
  if (target) {
    target.classList.add('active');
    target.scrollIntoView({block: 'center', behavior: 'smooth'});
  }
}

// ---------- turnpoints ----------
function renderTurnpoints() {
  const colors = CONFIG.colors;
  $('turnpoints').innerHTML = TURNPOINTS.map((tp, i) => `
    <div class="tp-item ${i>=3?'collapsed':''}" id="tp-${tp.turnpoint_id}"
         style="border-left-color:${colors[tp.main_dimension]}">
      <h3>▸ #${i+1}  ${fmtHMS(tp.time_start)}  ${escapeHtml(tp.description)}</h3>
      <ul class="evidence">
        ${tp.evidence_danmakus.map(ed =>
          `<li>[${fmtHMS(ed.time)}] ${escapeHtml(ed.text)}</li>`
        ).join('')}
      </ul>
      <a class="tp-link" href="#" data-time="${tp.time_start}">🔗 跳到 ${fmtHMS(tp.time_start)}</a>
    </div>
  `).join('');
  $('turnpoints').addEventListener('click', (e) => {
    const link = e.target.closest('.tp-link');
    if (link) { e.preventDefault(); seekAll(parseFloat(link.dataset.time)); return; }
    const item = e.target.closest('.tp-item');
    if (item) item.classList.toggle('collapsed');
  });
}

function scrollToTP(id) {
  const el = $(`tp-${id}`);
  if (el) { el.classList.remove('collapsed'); el.scrollIntoView({behavior: 'smooth'}); }
}

// ---------- legend ----------
function renderLegend() {
  const colors = CONFIG.colors;
  $('legend').innerHTML = DIMS.map(d =>
    `<span style="display:inline-block;margin-right:14px">
      <span class="dot" style="background:${colors[d]};width:10px;height:10px;
            border-radius:50%;display:inline-block;vertical-align:middle"></span>
      ${DIM_LABEL[d]} (${d})
    </span>`
  ).join('');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
}

// ---------- bootstrap ----------
mountVideo();
if (SCORES.length > 0) {
  renderOverview();
  renderChart();
}
renderDanmakuList();
renderTurnpoints();
renderLegend();

// bidirectional sync (local video mode only — iframe mode can't read back time)
if (videoApi && videoApi.onTick) {
  videoApi.onTick((t) => {
    highlightDanmakuAt(t);
    if (chart && !window._cursorBusy) {
      window._cursorBusy = true;
      chart.setOption({
        series: [{markLine: {silent: true, symbol: 'none',
          lineStyle: {color: '#fff', width: 1}, data: [{xAxis: t}]}}]
      });
      setTimeout(() => window._cursorBusy = false, 100);
    }
  });
}

window.addEventListener('resize', () => chart && chart.resize());

})();
