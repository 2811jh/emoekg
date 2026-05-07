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

// Pull the chart palette from the template's CSS variables so the chart stays
// visually in-sync with the report theme — no duplicate hex codes in JS.
// These are the *muted* ECG-trace colors; CONFIG.colors keeps the vivid
// Plutchik defaults for small markers (danmaku-list dots, turnpoint badges).
const CSSVAR = getComputedStyle(document.documentElement);
const CHART_COLORS = {
  joy:          CSSVAR.getPropertyValue('--e-joy').trim(),
  trust:        CSSVAR.getPropertyValue('--e-trust').trim(),
  fear:         CSSVAR.getPropertyValue('--e-fear').trim(),
  surprise:     CSSVAR.getPropertyValue('--e-surprise').trim(),
  sadness:      CSSVAR.getPropertyValue('--e-sadness').trim(),
  disgust:      CSSVAR.getPropertyValue('--e-disgust').trim(),
  anger:        CSSVAR.getPropertyValue('--e-anger').trim(),
  anticipation: CSSVAR.getPropertyValue('--e-anticipation').trim(),
};
const ACC       = CSSVAR.getPropertyValue('--acc').trim();
const INK_MUTED = CSSVAR.getPropertyValue('--n-6').trim();
const INK       = CSSVAR.getPropertyValue('--n-8').trim();
const INK_HI    = CSSVAR.getPropertyValue('--n-9').trim();
const LINE      = CSSVAR.getPropertyValue('--n-4').trim();
const SURF_1    = CSSVAR.getPropertyValue('--n-1').trim();

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
    //
    // Two constraints worth spelling out:
    //   1. We must use an **absolute** `https://` URL rather than the
    //      protocol-relative `//player.bilibili.com/...` form. Researchers
    //      open this report via `file://` (double-click in Explorer / Finder),
    //      under which `//...` would resolve to `file://player.bilibili.com`
    //      and instantly 404.
    //   2. Bilibili's public iframe endpoint now expects `isOutside=true`
    //      when embedded outside the bilibili.com origin; without it the
    //      player returns "视频可能已被移动、编辑或删除".
    const playerUrl = (t) => {
      const params = new URLSearchParams({
        isOutside: 'true',
        bvid: META.bvid,
        autoplay: t > 0 ? '1' : '0',
        high_quality: '1',
      });
      if (t > 0) params.set('t', String(Math.floor(t)));
      return `https://player.bilibili.com/player.html?${params.toString()}`;
    };

    const iframe = document.createElement('iframe');
    iframe.allowFullscreen = true;
    iframe.id = 'bili-iframe';
    iframe.referrerPolicy = 'no-referrer';  // some CDNs reject file:// referrers
    iframe.src = playerUrl(0);
    wrap.appendChild(iframe);
    videoApi = {
      seek: (s) => { iframe.src = playerUrl(s); },
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
  // "Coldest" excludes SPARSE chunks — otherwise the opening/closing seconds
  // (when nobody has commented yet) trivially win. n_danmaku >= 3 matches
  // the SPARSE threshold elsewhere in the pipeline.
  const nonSparse = SCORES.filter(s => s.n_danmaku >= 3);
  const coldest = nonSparse.length > 0
    ? nonSparse.reduce((a, b) => {
        const sumA = DIMS.reduce((x, d) => x + a[d], 0);
        const sumB = DIMS.reduce((x, d) => x + b[d], 0);
        return sumB < sumA ? b : a;
      })
    : SCORES[0];

  const hottestDim = DIMS.reduce((a, b) => hottest[a] > hottest[b] ? a : b);
  const hottestVal = Math.max(...DIMS.map(d => hottest[d]));
  const coldestAvg = (DIMS.reduce((x, d) => x + coldest[d], 0) / 8).toFixed(1);
  const totalSum   = DIMS.reduce((x, d) => x + sumByDim[d], 0) || 1;
  const topShare   = Math.round(100 * sumByDim[topDim] / totalSum);

  // Three "vital" readouts — editorial display typography with accent
  // highlight on the one number that matters most per card.
  $('overview').innerHTML = `
    <div class="vitals">
      <div class="vital" data-seek="${hottest.time_start}">
        <div class="label">Peak · 最炸时刻<span class="marker" style="color:${ACC}">HIGH</span></div>
        <div class="headline"><span class="accent">${fmtHMS(hottest.time_start)}</span></div>
        <div class="detail">
          ${DIM_LABEL[hottestDim]} 达到 <b style="color:${INK_HI}">${hottestVal}/10</b>
          · n=${hottest.n_danmaku} · chunk ${hottest.chunk_id}
        </div>
      </div>
      <div class="vital" data-seek="${coldest.time_start}">
        <div class="label">Valley · 最冷时刻<span class="marker" style="color:${INK_MUTED}">LOW</span></div>
        <div class="headline">${fmtHMS(coldest.time_start)}</div>
        <div class="detail">
          全维平均 <b style="color:${INK_HI}">${coldestAvg}</b>
          · n=${coldest.n_danmaku} · chunk ${coldest.chunk_id}
        </div>
      </div>
      <div class="vital">
        <div class="label">Dominant · 主导情绪<span class="marker" style="color:${ACC}">${topShare}%</span></div>
        <div class="headline"><span class="accent">${DIM_LABEL[topDim]}</span></div>
        <div class="detail">
          累计 <b style="color:${INK_HI}">${sumByDim[topDim]}</b> 分 · 占全量 ${topShare}% ·
          跨 ${SCORES.filter(s => s[topDim] > 0).length} 个 chunk
        </div>
      </div>
    </div>`;

  $('overview').addEventListener('click', (e) => {
    const card = e.target.closest('.vital[data-seek]');
    if (card) seekAll(parseFloat(card.dataset.seek));
  });
}

// ---------- ECG chart ----------
let chart = null;
function renderChart() {
  chart = echarts.init($('ecg-chart'), null, {renderer: 'canvas'});
  // The chart uses the muted editorial palette, not the vivid Plutchik one.
  // Small UI dots (danmaku list, legend chips) still use CONFIG.colors so
  // researchers can cross-reference the two.
  const colors = CHART_COLORS;

  const series = DIMS.map(d => ({
    name: DIM_LABEL[d],
    type: 'line',
    data: SCORES.map(s => [s.time_start, s[d]]),
    smooth: 0.35,
    lineStyle: {
      color: colors[d],
      width: 1.4,
      // A very subtle phosphor glow — just enough to read as "ECG trace"
      // rather than a flat line. Hover raises it meaningfully (see emphasis).
      shadowColor: colors[d],
      shadowBlur: 2,
      shadowOffsetY: 0,
    },
    itemStyle: {color: colors[d]},
    symbol: 'none',
    emphasis: {
      focus: 'series',
      lineStyle: {
        width: 2.2,
        shadowColor: colors[d],
        shadowBlur: 8,
      },
    },
    z: 5,
  }));
  const markPoints = TURNPOINTS.map(tp => ({
    name: tp.turnpoint_id, xAxis: tp.time_start,
    yAxis: tp.type === 'valley' ? 1 : 9,
    itemStyle: {
      color: ACC, borderColor: SURF_1, borderWidth: 1.5
    },
    symbol: tp.direction === 'up' ? 'triangle' : 'pin',
    symbolSize: 12,
    label: {show: false},
  }));
  series[0].markPoint = {data: markPoints};

  chart.setOption({
    backgroundColor: 'transparent',
    textStyle: {fontFamily: 'inherit', fontSize: 11},
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111113',
      borderColor: LINE,
      borderWidth: 1,
      padding: [10, 12],
      textStyle: {color: INK, fontSize: 12, fontFamily: 'inherit'},
      extraCssText: 'box-shadow:0 4px 24px rgba(0,0,0,.6); border-radius:0',
      formatter: (params) => {
        const t = params[0].value[0];
        const chunk = SCORES.find(s => s.time_start === t);
        if (!chunk) return '';
        const ff_mono = "ui-monospace,'SF Mono','Menlo',monospace";
        let html = `<div style="font-family:${ff_mono};font-size:10px;letter-spacing:.16em;color:${INK_MUTED};text-transform:uppercase;margin-bottom:6px">
          t = ${fmtHMS(t)} · n = ${chunk.n_danmaku}
        </div>`;
        DIMS.forEach(d => {
          const v = chunk[d];
          if (v > 0) html += `<div style="margin:4px 0;display:flex;justify-content:space-between;gap:16px">
            <span><span style="display:inline-block;width:8px;height:8px;background:${colors[d]};margin-right:8px;vertical-align:middle"></span>${DIM_LABEL[d]}</span>
            <b style="font-family:${ff_mono};color:${INK_HI}">${v}</b>
          </div>`;
        });
        return html;
      },
      axisPointer: {type: 'line', lineStyle: {color: LINE, width: 1, type: 'solid'}},
    },
    legend: {
      data: DIMS.map(d => DIM_LABEL[d]),
      top: 8, right: 16,
      textStyle: {color: INK, fontSize: 11, fontFamily: 'inherit'},
      itemWidth: 18, itemHeight: 2,
      itemGap: 18,
      inactiveColor: '#3a3d43',
    },
    grid: {left: 48, right: 24, top: 44, bottom: 58},
    xAxis: {
      type: 'value',
      axisLabel: {
        formatter: fmtHMS,
        color: INK_MUTED,
        fontFamily: "ui-monospace,'SF Mono',monospace",
        fontSize: 10,
      },
      axisLine: {lineStyle: {color: LINE}},
      axisTick: {lineStyle: {color: LINE}},
      splitLine: {show: false},
    },
    yAxis: {
      type: 'value', min: 0, max: 10, interval: 2,
      axisLabel: {
        color: INK_MUTED,
        fontFamily: "ui-monospace,'SF Mono',monospace",
        fontSize: 10,
      },
      axisLine: {show: false},
      axisTick: {show: false},
      splitLine: {lineStyle: {color: LINE, type: 'solid', opacity: 0.4}},
    },
    dataZoom: [
      {type: 'slider', height: 20, bottom: 16,
       backgroundColor: 'transparent',
       fillerColor: 'rgba(235,94,40,0.12)',
       borderColor: LINE,
       dataBackground: {
         lineStyle: {color: INK_MUTED, width: 0.5},
         areaStyle: {color: INK_MUTED, opacity: 0.15},
       },
       selectedDataBackground: {
         lineStyle: {color: ACC, width: 1},
         areaStyle: {color: ACC, opacity: 0.25},
       },
       handleStyle: {color: ACC, borderColor: ACC},
       moveHandleStyle: {color: ACC},
       textStyle: {color: INK_MUTED, fontFamily: "ui-monospace,monospace", fontSize: 10}},
      {type: 'inside'}
    ],
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

  // Canvas click — covers clicks on *empty* area of the chart (not on any
  // line/symbol). Translates pixel coords → xAxis value so the hint
  // "点击下方心电图任意位置可同步跳转视频时刻" is actually true.
  chart.getZr().on('click', (ev) => {
    // If the click already landed on a series / markPoint, the series
    // handler above will have fired; we only process "background" clicks.
    if (!chart.containPixel({gridIndex: 0}, [ev.offsetX, ev.offsetY])) return;
    const t = chart.convertFromPixel({gridIndex: 0}, [ev.offsetX, ev.offsetY])[0];
    if (typeof t === 'number' && t >= 0) seekAll(t);
  });

  window.addEventListener('resize', () => chart && chart.resize());
}

// ---------- unified seek ----------
// Called by *every* seek-trigger in the UI (vital card, TP card, danmaku
// item, chart click). Three concerns, explicitly separated:
//   1. Tell the video player to jump.
//   2. Highlight & in-list-scroll the matching danmaku (never scrolls the page).
//   3. Bring the video widget into the viewport, so the user actually sees
//      the jump happen instead of staring at whatever section they clicked.
function seekAll(sec) {
  if (videoApi) videoApi.seek(sec);
  highlightDanmakuAt(sec);
  scrollVideoIntoView();
}

function scrollVideoIntoView() {
  const wrap = $('video-wrapper');
  if (!wrap) return;
  // Only scroll if the video isn't already fully visible — prevents the
  // annoying "double-jump" when the user is already watching and clicks a
  // fine-grained marker.
  const rect = wrap.getBoundingClientRect();
  const vh = window.innerHeight || document.documentElement.clientHeight;
  const fullyVisible = rect.top >= 0 && rect.bottom <= vh;
  if (!fullyVisible) {
    wrap.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
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
      <span class="time">${fmtHMS(d.time)}</span>
      <span class="text">${escapeHtml(d.text)}</span>
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
  bar.innerHTML = btn('all', 'all') +
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
    // IMPORTANT: scroll only the danmaku list container, never the page.
    // Using `el.scrollIntoView({block:'center'})` would yank the entire
    // viewport down to the analysis section every time the chart/video
    // advances — confusing when the user is reading a turnpoint card
    // somewhere else on the page.
    const list = $('danmaku-list');
    if (list) {
      const targetTop = target.offsetTop - list.offsetTop;
      const desiredScroll = targetTop - list.clientHeight / 2 + target.clientHeight / 2;
      list.scrollTo({top: Math.max(0, desiredScroll), behavior: 'smooth'});
    }
  }
}

// ---------- turnpoints ----------
function renderTurnpoints() {
  const colors = CONFIG.colors;  // vivid Plutchik for the tiny dim indicator
  const typeTag = {peak: 'PEAK', valley: 'VALLEY', shift: 'SHIFT'};

  $('turnpoints').innerHTML = TURNPOINTS.map((tp, i) => {
    const col = colors[tp.main_dimension];
    // First three TPs open by default (usually enough to orient a researcher),
    // the rest collapse to keep the column scrollable.
    const collapsed = i >= 3 ? 'collapsed' : '';
    // Two-tier description:
    //   .head   — the hero line ("joy 达到 6/10"), big editorial serif.
    //   .detail — the supporting technical readout ("局部峰值" or
    //             "变化 +2.0 分 / 10 · JS=0.28"), smaller + dimmer,
    //             so it reads as *annotation* rather than headline.
    const detailHtml = tp.detail
      ? `<div class="tp-detail">${escapeHtml(tp.detail)}</div>`
      : '';
    return `<article class="tp ${collapsed}" id="tp-${tp.turnpoint_id}" data-seek="${tp.time_start}">
      <div class="tp-meta">
        <span class="id">${tp.turnpoint_id}</span>
        <button class="time" data-seek="${tp.time_start}" title="点击跳转视频到此时刻">${fmtHMS(tp.time_start)}</button>
        <span class="type" style="color:${col}">${typeTag[tp.type] || tp.type}</span>
        <span>${DIM_LABEL[tp.main_dimension]}</span>
      </div>
      <div class="head">${escapeHtml(tp.description)}</div>
      ${detailHtml}
      <ul class="evidence">
        ${tp.evidence_danmakus.map(ed =>
          `<li><button class="t" data-seek="${ed.time}" title="点击跳转视频到此时刻">${fmtHMS(ed.time)}</button>${escapeHtml(ed.text)}</li>`
        ).join('')}
      </ul>
    </article>`;
  }).join('');

  // Click behavior split:
  //   · `.time` / `.t` buttons (the HH:MM:SS labels)  →  jump video only,
  //     do NOT toggle collapse.
  //   · everywhere else on the card                    →  toggle collapse,
  //     do NOT jump video.
  // This matches the user's mental model: "times are clickable to navigate,
  // the rest of the card is just content I can expand/collapse."
  $('turnpoints').addEventListener('click', (e) => {
    const seekBtn = e.target.closest('[data-seek]');
    if (seekBtn && seekBtn.matches('button.time, button.t')) {
      e.stopPropagation();
      seekAll(parseFloat(seekBtn.dataset.seek));
      return;
    }
    const card = e.target.closest('.tp');
    if (card) card.classList.toggle('collapsed');
  });
}

function scrollToTP(id) {
  const el = $(`tp-${id}`);
  if (el) {
    el.classList.remove('collapsed');
    el.scrollIntoView({behavior: 'smooth', block: 'center'});
  }
}

// ---------- legend ----------
function renderLegend() {
  // The legend bridges the two palettes: the big swatch uses the muted
  // chart color (so it matches the ECG), but we list the Plutchik English
  // code and Chinese label side by side so the key is self-documenting.
  $('legend').innerHTML = DIMS.map(d =>
    `<span class="chip">
      <span class="sw" style="background:${CHART_COLORS[d]}"></span>
      <span><b>${DIM_LABEL[d]}</b>&nbsp;·&nbsp;${d}</span>
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
