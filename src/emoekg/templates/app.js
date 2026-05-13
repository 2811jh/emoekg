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
// Plutchik's canonical bilingual labels. Four opposing pairs:
//   joy ↔ sadness · trust ↔ disgust · fear ↔ anger · surprise ↔ anticipation
// Note on "惊奇" (not "惊讶"): in the standard Chinese translation of
// Plutchik's wheel, `surprise` is rendered as 惊奇 (a cognitive/appraisal
// reaction) while 惊讶 tends to conflate with shock/startle. Keeping
// 惊奇 here matches academic Plutchik glosses and the 6seconds.org poster.
const DIM_LABEL = {joy:'喜悦',trust:'信任',fear:'恐惧',surprise:'惊奇',
                   sadness:'悲伤',disgust:'厌恶',anger:'愤怒',anticipation:'期待'};

// 8-emotion reference card for the Plutchik-wheel widget. Each entry follows
// the Six Seconds EQ card format: Similar words → Typical sensations →
// What is X telling you? → How can X help you?  The text is intentionally
// kept in English to preserve the authoritative source phrasing; a Chinese
// headline is shown alongside via DIM_LABEL.
//
// `opposite` records the Plutchik dyad. Changing it would break the
// "Opposite · ... " line in the info panel.
// ---------- Plutchik wheel info cards ----------
// Content source: Six Seconds (6seconds.org) "Eight Core Emotions" framework —
// the canonical educational framing of Plutchik's 8 primaries. Each entry
// carries four fields in both Chinese (primary — UX research audience is
// Mandarin-dominant) and English (secondary — preserves the original
// phrasing for researchers cross-referencing the 6seconds literature):
//
//   similar    — 相似情绪 / Similar Words
//   sensation  — 典型感受 / Typical Sensations
//   telling    — 这份情绪在告诉你什么 / What is X telling you?
//   helping    — 这份情绪如何帮助你 / How can X help you?
//
// `opposite` records the Plutchik dyad. Changing it breaks the
// "对立 · ..." line in the info panel.
const WHEEL_INFO = {
  joy: {
    en: 'Joy', opposite: 'sadness',
    similar_zh:   '兴奋、愉快',
    similar_en:   'Excited, Pleased',
    sensation_zh: '充满能量与可能性的感觉',
    sensation_en: 'Sense of energy and possibility',
    telling_zh:   '生活正在顺利进行',
    telling_en:   'Life is going well',
    helping_zh:   '激发创造力、促进连接、赋予能量',
    helping_en:   'Sparks creativity, connection, gives energy',
  },
  trust: {
    en: 'Trust', opposite: 'disgust',
    similar_zh:   '接纳、安心',
    similar_en:   'Accepting, Safe',
    sensation_zh: '温暖',
    sensation_en: 'Warm',
    telling_zh:   '这是安全的',
    telling_en:   'This is safe',
    helping_zh:   '保持开放、建立连接、结成同盟',
    helping_en:   'Be open, connect, build alliance',
  },
  fear: {
    en: 'Fear', opposite: 'anger',
    similar_zh:   '紧张、害怕',
    similar_en:   'Stressed, Scared',
    sensation_zh: '焦躁不安',
    sensation_en: 'Agitated',
    telling_zh:   '我在乎的东西正处于风险中',
    telling_en:   'Something I care about is at risk',
    helping_zh:   '守护我们所珍视的事物',
    helping_en:   'Protect what we care about',
  },
  surprise: {
    en: 'Surprise', opposite: 'anticipation',
    similar_zh:   '震惊、出乎意料',
    similar_en:   'Shocked, Unexpected',
    sensation_zh: '心跳加速',
    sensation_en: 'Heart pounding',
    telling_zh:   '有新的事情正在发生',
    telling_en:   'Something new happened',
    helping_zh:   '关注此刻正在眼前展开的一切',
    helping_en:   "Pay attention to what's right here",
  },
  sadness: {
    en: 'Sadness', opposite: 'joy',
    similar_zh:   '失落、失去',
    similar_en:   'Bummed, Loss',
    sensation_zh: '沉重',
    sensation_en: 'Heavy',
    telling_zh:   '所爱正在远去',
    telling_en:   'Love is going away',
    helping_zh:   '聚焦于我们真正重视的事物',
    helping_en:   "Focus on what's important to us",
  },
  disgust: {
    en: 'Disgust', opposite: 'trust',
    similar_zh:   '不信任、拒斥',
    similar_en:   'Distrust, Rejecting',
    sensation_zh: '苦涩、排斥',
    sensation_en: 'Bitter & unwanted',
    telling_zh:   '出了问题；规则被打破了',
    telling_en:   'Wrong; rules are violated',
    helping_zh:   '识别不安全或不对劲的信号',
    helping_en:   'Notice something unsafe or wrong',
  },
  anger: {
    en: 'Anger', opposite: 'fear',
    similar_zh:   '暴怒、激烈',
    similar_en:   'Mad, Fierce',
    sensation_zh: '强烈而灼热',
    sensation_en: 'Strong and heated',
    telling_zh:   '有东西挡在了去路上',
    telling_en:   'Something is in the way',
    helping_zh:   '聚集能量突破障碍',
    helping_en:   'Energize to break through a barrier',
  },
  anticipation: {
    en: 'Anticipation', opposite: 'surprise',
    similar_zh:   '好奇、斟酌',
    similar_en:   'Curious, Considering',
    sensation_zh: '警觉、探索',
    sensation_en: 'Alert and exploring',
    telling_zh:   '变化正在发生',
    telling_en:   'Change is happening',
    helping_zh:   '望向前方，预见可能到来的事',
    helping_en:   'Look ahead, look at what might be coming',
  },
};

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
    // Hover feedback — glow + scale, tells the researcher the dot is clickable.
    emphasis: {
      itemStyle: {shadowColor: ACC, shadowBlur: 12, borderColor: ACC, borderWidth: 2},
      scale: 1.35,
      label: {show: false},
    },
    // Per-point tooltip — overrides the chart-level axis tooltip when hovering
    // the triangle itself. Tells the researcher what TP this is, what emotion
    // drives it, and that it's clickable.
    tooltip: {
      show: true,
      trigger: 'item',
      backgroundColor: '#111113',
      borderColor: ACC,
      borderWidth: 1,
      padding: [10, 12],
      textStyle: {color: INK, fontSize: 12, fontFamily: 'inherit'},
      extraCssText: 'box-shadow:0 4px 24px rgba(0,0,0,.6); border-radius:0; max-width:260px;',
      formatter: () => {
        const ff_mono = "ui-monospace,'SF Mono','Menlo',monospace";
        const dimLabel = DIM_LABEL[tp.main_dimension] || tp.main_dimension;
        const typeLabel = tp.type === 'peak' ? 'PEAK'
                        : tp.type === 'valley' ? 'VALLEY'
                        : 'SHIFT';
        const detail = tp.detail || tp.description || '';
        return `
          <div style="font-family:${ff_mono};font-size:10px;letter-spacing:.18em;color:${ACC};text-transform:uppercase;margin-bottom:6px">
            ${tp.turnpoint_id} · ${typeLabel}
          </div>
          <div style="margin:4px 0;display:flex;justify-content:space-between;gap:16px;font-size:13px">
            <span style="color:${INK_HI}">${dimLabel}</span>
            <b style="font-family:${ff_mono};color:${ACC}">${tp.magnitude}/10</b>
          </div>
          <div style="font-family:${ff_mono};font-size:10px;color:${INK_MUTED};margin-top:4px">
            t = ${fmtHMS(tp.time_start)} – ${fmtHMS(tp.time_end)}
          </div>
          ${detail ? `<div style="font-size:11px;color:${INK};margin-top:8px;line-height:1.5">${detail}</div>` : ''}
          <div style="font-size:10px;color:${ACC};margin-top:8px;letter-spacing:.05em;border-top:1px solid ${LINE};padding-top:6px">
            → 点击同步视频至此时刻
          </div>
        `;
      },
    },
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
      if (tp) { seekAll(tp.time_start); return; }
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
  // v0.4.4: drive the vital console directly (no panel scroll, no mode switch)
  if (typeof updateVitalReadout === 'function') {
    const status = (CONFIG.video_mode === 'local') ? '播放中' : '已跳转';
    updateVitalReadout(sec, status);
  }
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

// ---------- Plutchik wheel ----------
// Interactive SVG re-imagining of Plutchik's classic 8-emotion wheel, with
// two research-oriented twists:
//   1. Petal *length* encodes this video's mean score for that dimension
//      — so the overall silhouette is a per-video emotion fingerprint.
//   2. Clicking a petal surfaces the Six-Seconds reference card
//      (Similar / Sensations / Telling / Helping) next to the numerical
//      readouts (avg score, share, timestamp of peak).
//
// Opposites are diagonally placed (top–bottom, etc.) so the reader can
// read dyads at a glance: joy↔sadness, trust↔disgust, fear↔anger,
// surprise↔anticipation.
function renderWheel() {
  const svg = $('plutchik-wheel');
  if (!svg) return;

  // --- stats ---
  // Exclude SPARSE chunks (n_danmaku < 3) — otherwise the opening seconds
  // of a video, which typically score 0 across the board, would drag every
  // average toward zero and flatten the wheel.
  const nonSparse = SCORES.filter(s => s.n_danmaku >= 3);
  const base = nonSparse.length > 0 ? nonSparse : SCORES;
  const totalSum = base.reduce((s, r) =>
    s + DIMS.reduce((x, d) => x + r[d], 0), 0) || 1;

  const perDim = {};
  DIMS.forEach(d => {
    const vs = base.map(r => r[d]);
    const sum = vs.reduce((a, b) => a + b, 0);
    const avg = vs.length ? sum / vs.length : 0;
    const peak = base.reduce((best, r) =>
      (!best || r[d] > best[d]) ? r : best, null);
    const peakVal = peak ? peak[d] : 0;
    perDim[d] = {
      sum, avg, share: sum / totalSum,
      peakTime: peak ? peak.time_start : 0,
      peakVal,
    };
  });

  // --- geometry ---
  // Petal radius clamped to [R_MIN, R_MAX]. R_MIN keeps a tiny petal
  // readable even when a dimension is essentially absent. Saturation at
  // avg=8 rather than 10: a "10 out of 10" wheel would leave no headroom
  // and a typical strong video peaks around 5–7 on averages.
  const R_MIN = 48, R_MAX = 150;
  const SAT = 8;
  const HW_RAD = 22 * Math.PI / 180;   // petal half-width angle

  // Subtle reference rings at 2/5/8 — the "gridlines" of the wheel.
  const rings = [2, 5, 8].map(v => {
    const r = R_MIN + (R_MAX - R_MIN) * (v / SAT);
    return `<circle class="wheel-ring" r="${r.toFixed(1)}"/>`;
  }).join('');

  const petals = DIMS.map((d, i) => {
    const col = CHART_COLORS[d];
    const info = WHEEL_INFO[d];
    const theta = (-90 + i * 45) * Math.PI / 180;  // joy at 12 o'clock, cw
    const L = R_MIN + (R_MAX - R_MIN) * Math.min(1, perDim[d].avg / SAT);

    const tx = L * Math.cos(theta), ty = L * Math.sin(theta);
    const mid = L * 0.55;
    const lx = mid * Math.cos(theta - HW_RAD), ly = mid * Math.sin(theta - HW_RAD);
    const rx = mid * Math.cos(theta + HW_RAD), ry = mid * Math.sin(theta + HW_RAD);
    const path = `M 0 0 Q ${lx.toFixed(1)} ${ly.toFixed(1)} ${tx.toFixed(1)} ${ty.toFixed(1)} Q ${rx.toFixed(1)} ${ry.toFixed(1)} 0 0 Z`;

    // Score badge sits at ~60% of petal length, centered on the axis.
    const badgeR = L * 0.6;
    const bx = badgeR * Math.cos(theta), by = badgeR * Math.sin(theta);

    // Chinese/English labels float just outside the petal tip. The
    // text-anchor follows the horizontal component so labels never
    // overlap the petal: top/bottom labels center, right-side start,
    // left-side end.
    const labelR = L + 22;
    const lbx = labelR * Math.cos(theta), lby = labelR * Math.sin(theta);
    const anchor = Math.abs(Math.cos(theta)) < 0.25 ? 'middle'
                 : Math.cos(theta) > 0            ? 'start'
                 :                                   'end';

    return `
      <g class="wheel-emo" data-dim="${d}" style="--emo:${col}">
        <path class="wheel-petal" d="${path}"/>
        <text class="wheel-score" x="${bx.toFixed(1)}" y="${by.toFixed(1)}"
              text-anchor="middle" dominant-baseline="middle">${perDim[d].avg.toFixed(1)}</text>
        <text class="wheel-label-cn" x="${lbx.toFixed(1)}" y="${(lby - 7).toFixed(1)}"
              text-anchor="${anchor}" dominant-baseline="middle">${DIM_LABEL[d]}</text>
        <text class="wheel-label-en" x="${lbx.toFixed(1)}" y="${(lby + 8).toFixed(1)}"
              text-anchor="${anchor}" dominant-baseline="middle">${info.en}</text>
      </g>`;
  }).join('');

  svg.innerHTML = rings + petals;

  // --- hub: top emotion of the entire video ---
  const topDim = DIMS.reduce((a, b) => perDim[a].sum > perDim[b].sum ? a : b);
  const hubEl = $('wheel-hub-value');
  if (hubEl) {
    hubEl.textContent = DIM_LABEL[topDim];
    hubEl.style.color = CHART_COLORS[topDim];
  }

  // --- info panel + selection state ---
  const infoBox = $('wheel-info');
  const selectDim = (d) => {
    svg.querySelectorAll('.wheel-emo').forEach(g =>
      g.classList.toggle('active', g.dataset.dim === d));
    svg.querySelectorAll('.wheel-emo').forEach(g =>
      g.classList.toggle('dimmed', g.dataset.dim !== d));
    const info = WHEEL_INFO[d];
    const st = perDim[d];
    const opp = WHEEL_INFO[info.opposite];
    const hasPeak = st.peakVal > 0;
    infoBox.innerHTML = `
      <div class="title">
        <span class="cn">${DIM_LABEL[d]}</span>
        <span class="en">${info.en}</span>
        <span class="badge" style="background:${CHART_COLORS[d]}">SELECTED</span>
      </div>
      <div class="opposite">对立情绪 Opposite · ${DIM_LABEL[info.opposite]} ↔ ${opp.en}</div>
      <dl>
        <dt><span class="zh">相似情绪</span><span class="la">Similar Words</span></dt>
        <dd><span class="zh">${info.similar_zh}</span><span class="la">${info.similar_en}</span></dd>

        <dt><span class="zh">典型感受</span><span class="la">Typical Sensations</span></dt>
        <dd><span class="zh">${info.sensation_zh}</span><span class="la">${info.sensation_en}</span></dd>

        <dt><span class="zh">在告诉你</span><span class="la">Telling You</span></dt>
        <dd><span class="zh">${info.telling_zh}</span><span class="la">${info.telling_en}</span></dd>

        <dt><span class="zh">如何帮助你</span><span class="la">Helping You</span></dt>
        <dd><span class="zh">${info.helping_zh}</span><span class="la">${info.helping_en}</span></dd>
      </dl>
      <div class="stats">
        <div class="cell">
          <span class="k">Avg score</span>
          <span class="v">${st.avg.toFixed(1)}<b> / 10</b></span>
        </div>
        <div class="cell">
          <span class="k">Share</span>
          <span class="v">${(st.share * 100).toFixed(0)}<b>%</b></span>
        </div>
        <div class="cell ${hasPeak ? 'seekable' : ''}"
             ${hasPeak ? `data-seek="${st.peakTime}"` : ''}>
          <span class="k">Peak @</span>
          <span class="v">${hasPeak ? fmtHMS(st.peakTime) : '—'}<b>${hasPeak ? ` / ${st.peakVal}` : ''}</b></span>
        </div>
      </div>`;
    const seekEl = infoBox.querySelector('[data-seek]');
    if (seekEl) seekEl.addEventListener('click',
      () => seekAll(parseFloat(seekEl.dataset.seek)));
  };

  // petal click → select
  svg.addEventListener('click', (e) => {
    const g = e.target.closest('.wheel-emo');
    if (g) selectDim(g.dataset.dim);
  });

  // opposite-pair chips → select the left-side of the pair
  document.querySelectorAll('.wheel-pairs .p').forEach(el => {
    el.addEventListener('click', () => {
      const [a] = el.dataset.pair.split(',');
      selectDim(a);
    });
  });

  // Default selection: whatever emotion dominates the video overall.
  selectDim(topDim);
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

// ========================================================================
// DanmakuPanel (v0.4.0)
// ------------------------------------------------------------------------
// A §02 right-column panel with two modes (follow / browse), virtual
// scrolling, and TP evidence ▲ badges. Coexists with the legacy §04
// `#danmaku-list` — shares the DANMAKUS constant but owns isolated UI
// state. All elements live under `#panel-root` with the `.panel-*` class
// namespace to prevent CSS / selector collisions.
// ========================================================================

// v0.4.4: 8 Plutchik dims with display copy + colours. Order is the
// canonical wheel order (joy → anticipation → trust → ... → anger).
const DIMENSIONS_META = [
  { key: 'joy',          en: 'JOY',   zh: '喜悦', color: '#F4C95D' },
  { key: 'anticipation', en: 'ANTI',  zh: '期待', color: '#E89B5C' },
  { key: 'trust',        en: 'TRUST', zh: '信任', color: '#6FAE6E' },
  { key: 'surprise',     en: 'SURP',  zh: '惊讶', color: '#D9A14A' },
  { key: 'fear',         en: 'FEAR',  zh: '恐惧', color: '#6E7AA6' },
  { key: 'sadness',      en: 'SAD',   zh: '悲伤', color: '#4A6E8C' },
  { key: 'disgust',      en: 'DISG',  zh: '厌恶', color: '#8C5A8E' },
  { key: 'anger',        en: 'ANGER', zh: '愤怒', color: '#C8472D' },
];
const POSITIVE_DIMS = ['joy', 'trust', 'anticipation', 'surprise'];
const NEGATIVE_DIMS = ['fear', 'sadness', 'disgust', 'anger'];

const PanelStore = {
  currentTime: 0,
};

function mountPanel() {
  const root = document.getElementById('panel-root');
  if (!root) return;
  try {
    if (!Array.isArray(DANMAKUS) || DANMAKUS.length === 0) {
      root.innerHTML = `
        <div class="panel-empty">
          <div class="panel-empty-title">暂无弹幕</div>
          <div class="panel-empty-body">此视频未抓到历史弹幕。</div>
        </div>
      `;
      return;
    }

    renderPanelShell(root);
    syncPanelHeight();          // lock panel height to video height
    bindBilibiliPostMessage();  // best-effort iframe progress listener
    wirePanelEvents();
    updateVitalReadout(0, '待同步');  // initial paint at t=0
    console.log(`[Panel] vital console mounted with ${DANMAKUS.length} danmakus`);
  } catch (err) {
    console.error('[Panel] mount failed, hiding panel', err);
    root.style.display = 'none';
  }
}

// v0.4.5: Vital console — compact baseline header (time + dominant only),
// 8-dim readout bars, nearby danmaku trail. No more DOMINANT label,
// no more pulsing status dot — they were noise.
function renderPanelShell(root) {
  const dimsHtml = DIMENSIONS_META.map(d => `
    <div class="vd-row" data-dim="${d.key}">
      <span class="vd-name">
        <span class="vd-en">${d.en}</span>
        <span class="vd-zh">${d.zh}</span>
      </span>
      <div class="vd-bar"><div class="vd-fill" id="vd-fill-${d.key}"></div></div>
      <span class="vd-num" id="vd-num-${d.key}">0</span>
    </div>
  `).join('');

  root.innerHTML = `
    <header class="vital-card">
      <span class="vital-time-code" id="vital-time-code" aria-live="polite">
        <span class="vt-min">00</span><span class="colon">:</span><span class="vt-sec">00</span>
      </span>
      <span class="vital-dom">
        <span class="vital-dom-zh" id="vital-dom-zh">—</span>
        <span class="vital-dom-sep">·</span>
        <span class="vital-dom-en" id="vital-dom-en">—</span>
        <span class="vital-dom-score" id="vital-dom-score"><span class="num">0</span><span class="max">/10</span></span>
      </span>
    </header>

    <section class="vital-dims" id="vital-dims">${dimsHtml}</section>

    <section class="vital-dms" id="vital-dms">
      <div class="vital-dms-head">
        <span>该时刻 · 邻近弹幕 (±20s)</span>
        <span class="count" id="vital-dms-count">0 条</span>
      </div>
      <div id="vital-dms-list"></div>
    </section>
  `;
}

// v0.4.4: utilities used by vital console + danmaku list (formatMMSS still
// referenced by §05 renderDanmakuList).
function formatMMSS(sec) {
  const s = Math.max(0, Math.floor(sec || 0));
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

// Back-compat shims: seekAll + bindBilibiliPostMessage still call these.
// New behaviour lives in updateVitalReadout.
function scrollToCenter(t)        { updateVitalReadout(t); }
function updateCurrentHighlight() { /* vital console paints itself */ }
function updateVitalTime(sec, status) { updateVitalReadout(sec, status); }
function scrollToNearest(t)       { updateVitalReadout(t); }

/* ====================================================================== *
 * Vital readout — paint the right-side console for cursor time t.
 * Three blocks: time code, 8-dim bars + dominant, ±20s danmaku trail.
 * ====================================================================== */
function updateVitalReadout(t, status) {
  const sec = Math.max(0, Number(t) || 0);
  PanelStore.currentTime = sec;

  // Time code
  const tc = document.getElementById('vital-time-code');
  if (tc) {
    const total = Math.floor(sec);
    const minEl = tc.querySelector('.vt-min');
    const secEl = tc.querySelector('.vt-sec');
    if (minEl) minEl.textContent = String(Math.floor(total / 60)).padStart(2, '0');
    if (secEl) secEl.textContent = String(total % 60).padStart(2, '0');
  }

  const score = chunkScoreAt(sec);
  if (!score) return;

  // 8-dim bars + dominant
  let domKey = null, domScore = -1;
  DIMENSIONS_META.forEach(d => {
    const v = Math.max(0, Math.min(10, score[d.key] || 0));
    const fillEl = document.getElementById('vd-fill-' + d.key);
    const numEl  = document.getElementById('vd-num-' + d.key);
    if (fillEl) fillEl.style.width = (v * 10) + '%';
    if (numEl)  numEl.textContent  = v.toFixed(0);
    const row = document.querySelector('.vd-row[data-dim="' + d.key + '"]');
    if (row) {
      row.classList.toggle('is-zero', v === 0);
      row.classList.remove('is-dom');
    }
    if (v > domScore) { domScore = v; domKey = d.key; }
  });
  if (domKey && domScore > 0) {
    const domDef = DIMENSIONS_META.find(d => d.key === domKey);
    const zhEl    = document.getElementById('vital-dom-zh');
    const enEl    = document.getElementById('vital-dom-en');
    const scoreEl = document.getElementById('vital-dom-score');
    if (zhEl)    zhEl.textContent = domDef.zh;
    if (enEl)    enEl.textContent = domDef.en;
    if (scoreEl) scoreEl.innerHTML = `<span class="num">${domScore}</span><span class="max">/10</span>`;
    const row = document.querySelector('.vd-row[data-dim="' + domKey + '"]');
    if (row) row.classList.add('is-dom');
  } else {
    // SPARSE chunk → mute the dominant readout
    const zhEl    = document.getElementById('vital-dom-zh');
    const enEl    = document.getElementById('vital-dom-en');
    const scoreEl = document.getElementById('vital-dom-score');
    if (zhEl)    zhEl.textContent = '静默';
    if (enEl)    enEl.textContent = 'SILENT';
    if (scoreEl) scoreEl.innerHTML = `<span class="num">0</span><span class="max">/10</span>`;
  }

  // (status pulse removed in v0.4.5; the ECG hover + iframe-mode hint
  // already convey the sync state.)
  void status;

  updateVitalDanmakus(sec);
}

function chunkScoreAt(sec) {
  if (!Array.isArray(SCORES) || SCORES.length === 0) return null;
  for (let i = 0; i < SCORES.length; i++) {
    const s = SCORES[i];
    if (sec >= s.time_start && sec < s.time_end) return s;
  }
  if (sec < SCORES[0].time_start) return SCORES[0];
  return SCORES[SCORES.length - 1];
}

function updateVitalDanmakus(t) {
  const list  = document.getElementById('vital-dms-list');
  const count = document.getElementById('vital-dms-count');
  if (!list) return;
  const win = 20;
  const near = (DANMAKUS || []).filter(d => Math.abs(d.time - t) <= win);
  near.sort((a, b) => Math.abs(a.time - t) - Math.abs(b.time - t));
  const top = near.slice(0, 12);

  if (count) count.textContent = near.length + ' 条';
  if (top.length === 0) {
    list.innerHTML = '<div class="vital-dm-empty">此时段无弹幕</div>';
    return;
  }
  list.innerHTML = top.map(d => `
    <div class="vital-dm" data-time="${d.time}">
      <span class="vital-dm-time">${formatMMSS(d.time)}</span>
      <span class="vital-dm-text">${escapeHtml(d.text)}</span>
    </div>
  `).join('');
}

function wirePanelEvents() {
  const isIframeMode = (CONFIG.video_mode !== 'local');

  // ECG axis pointer (hover or click) → drive vital readout
  if (typeof chart !== 'undefined' && chart) {
    chart.on('updateAxisPointer', params => {
      if (!params || !params.axesInfo || !params.axesInfo.length) return;
      const t = Number(params.axesInfo[0].value);
      if (!Number.isFinite(t)) return;
      updateVitalReadout(t, isIframeMode ? '预览中' : 'LIVE');
    });
  }

  // Click on a danmaku in the trail → jump video there
  const dmList = document.getElementById('vital-dms-list');
  if (dmList) {
    dmList.addEventListener('click', e => {
      const row = e.target.closest('.vital-dm');
      if (!row) return;
      const t = Number(row.dataset.time);
      if (Number.isFinite(t)) seekAll(t);
    });
  }

  // Local-video tick → drive readout in real time
  if (videoApi && typeof videoApi.onTick === 'function') {
    videoApi.onTick(t => updateVitalReadout(t, '播放中'));
  }
  if (!isIframeMode) {
    const ribbon = document.getElementById('video-col-hint');
    if (ribbon) ribbon.style.display = 'none';
  }
}

/* ====================================================================== *
 * v0.4.4: Vital statistics grid (6 cards) below the ECG. Editorial,
 * gauge-y, clickable cards that double as quick navigation.
 * ====================================================================== */
function renderVitalStats() {
  const grid = document.getElementById('vital-stats-grid');
  if (!grid) return;
  const dur = META.duration_sec || 0;

  // 1. Dominant emotion: argmax sum across non-sparse chunks
  const sums = {};
  DIMENSIONS_META.forEach(d => sums[d.key] = 0);
  let countedChunks = 0;
  SCORES.forEach(s => {
    if ((s.n_danmaku || 0) < 3) return;
    DIMENSIONS_META.forEach(d => sums[d.key] += (s[d.key] || 0));
    countedChunks++;
  });
  const domKey = Object.keys(sums).reduce((a, b) => sums[a] >= sums[b] ? a : b);
  const domDef = DIMENSIONS_META.find(d => d.key === domKey);
  const domAvg = countedChunks ? (sums[domKey] / countedChunks) : 0;

  // 2. Totals
  const total = (DANMAKUS || []).length;
  const peakChunkN = SCORES.reduce((m, s) => Math.max(m, s.n_danmaku || 0), 0);

  // 3. Turnpoints
  const tps = TURNPOINTS || [];
  const peaks   = tps.filter(t => t.type === 'peak');
  const valleys = tps.filter(t => t.type === 'valley');
  const shifts  = tps.filter(t => t.type === 'shift');

  // 4 & 5. Strongest peak / valley
  const strongestOf = (arr) => arr.slice().sort((a, b) => (b.magnitude || 0) - (a.magnitude || 0))[0];
  const topPeak = strongestOf(peaks) || null;
  const topVal  = strongestOf(valleys) || null;

  // 6. Polarity (positive avg - negative avg over non-sparse chunks)
  let posSum = 0, negSum = 0, n = 0;
  SCORES.forEach(s => {
    if ((s.n_danmaku || 0) < 3) return;
    POSITIVE_DIMS.forEach(k => posSum += (s[k] || 0));
    NEGATIVE_DIMS.forEach(k => negSum += (s[k] || 0));
    n++;
  });
  const polarity = n ? ((posSum / n / 4) - (negSum / n / 4)) : 0;
  const polarityStr = (polarity >= 0 ? '+' : '') + polarity.toFixed(1);

  // Sparklines
  const buildSpark = (seq) => {
    const bars = seq.length > 16 ? sampleArray(seq, 16) : seq;
    const max  = Math.max(1, ...bars);
    return bars.map(v => {
      const h = Math.max(2, (v / max) * 18);
      return `<span class="${v === 0 ? 'zero' : ''}" style="height:${h.toFixed(1)}px"></span>`;
    }).join('');
  };
  const domSpark = buildSpark(SCORES.map(s => Math.max(0, Math.min(10, s[domKey] || 0))));
  const dmSpark  = buildSpark(SCORES.map(s => s.n_danmaku || 0));

  const winSec = SCORES[0] ? (SCORES[0].time_end - SCORES[0].time_start) : 30;

  grid.innerHTML = `
    <article class="vs-card vs-hero">
      <span class="vs-label">主导情绪 / DOMINANT
        <span class="vs-corner">${domDef.en}</span>
      </span>
      <span class="vs-num"><b>${domDef.zh}</b></span>
      <span class="vs-sub">全片均强 ${domAvg.toFixed(1)}/10 · 出现于 ${countedChunks} 段</span>
      <div class="vs-spark">${domSpark}</div>
    </article>
    <article class="vs-card">
      <span class="vs-label">弹幕总量 / DANMAKU
        <span class="vs-corner">${dur ? Math.round(total / dur * 60) : 0}/min</span>
      </span>
      <span class="vs-num">${total.toLocaleString()}<span class="unit">条</span></span>
      <span class="vs-sub">峰段 ${peakChunkN} 条 · ${winSec}s 窗口</span>
      <div class="vs-spark">${dmSpark}</div>
    </article>
    <article class="vs-card">
      <span class="vs-label">情绪转折 / TURNPOINTS
        <span class="vs-corner">N=${tps.length}</span>
      </span>
      <span class="vs-num">${tps.length}<span class="unit">个</span></span>
      <span class="vs-sub">峰 ${peaks.length} · 谷 ${valleys.length} · 反转 ${shifts.length}</span>
    </article>
    <article class="vs-card vs-clickable" ${topPeak ? `data-seek="${topPeak.time_start}"` : ''}>
      <span class="vs-label">最强峰值 / PEAK
        <span class="vs-corner">${topPeak ? topPeak.main_dimension.toUpperCase() : '—'}</span>
      </span>
      <span class="vs-num">${topPeak ? formatMMSS(topPeak.time_start) : '—'}</span>
      <span class="vs-sub">${topPeak ? '强度 ' + (topPeak.magnitude||0).toFixed(1) + ' · ' + escapeHtml((topPeak.description || '').slice(0, 24)) : '该视频无显著峰值'}</span>
    </article>
    <article class="vs-card vs-clickable" ${topVal ? `data-seek="${topVal.time_start}"` : ''}>
      <span class="vs-label">最低谷值 / VALLEY
        <span class="vs-corner">${topVal ? topVal.main_dimension.toUpperCase() : '—'}</span>
      </span>
      <span class="vs-num">${topVal ? formatMMSS(topVal.time_start) : '—'}</span>
      <span class="vs-sub">${topVal ? '强度 ' + (topVal.magnitude||0).toFixed(1) + ' · ' + escapeHtml((topVal.description || '').slice(0, 24)) : '该视频无显著谷值'}</span>
    </article>
    <article class="vs-card">
      <span class="vs-label">情绪极性 / POLARITY
        <span class="vs-corner">-10..+10</span>
      </span>
      <span class="vs-num ${polarity > 0 ? 'vs-pos' : (polarity < 0 ? 'vs-neg' : '')}">${polarityStr}</span>
      <span class="vs-sub">正向 − 负向 均值 · ${polarity > 0.5 ? '整体偏正' : polarity < -0.5 ? '整体偏负' : '中性平衡'}</span>
    </article>
  `;

  grid.querySelectorAll('.vs-clickable[data-seek]').forEach(el => {
    el.addEventListener('click', () => {
      const t = parseFloat(el.dataset.seek);
      if (Number.isFinite(t)) seekAll(t);
    });
  });
}

function sampleArray(arr, n) {
  if (arr.length <= n) return arr;
  const out = [];
  const step = arr.length / n;
  for (let i = 0; i < n; i++) {
    const start = Math.floor(i * step);
    const end = Math.floor((i + 1) * step);
    let max = 0;
    for (let j = start; j < end; j++) max = Math.max(max, arr[j]);
    out.push(max);
  }
  return out;
}

// ---------- v0.4.2: panel height sync (no overshoot below video) ----------
// Without this, the danmaku panel grows to its intrinsic height and pushes
// the layout way past the video bottom. Lock panel height to whatever
// video-wrapper currently renders at (responsive, aspect-ratio driven).
function syncPanelHeight() {
  const wrapper = document.getElementById('video-wrapper');
  const panel = document.getElementById('panel-root');
  if (!wrapper || !panel) return;

  const apply = () => {
    const r = wrapper.getBoundingClientRect();
    if (r.height > 100) {
      panel.style.height = Math.round(r.height) + 'px';
    }
  };
  apply();
  window.addEventListener('load', apply);
  window.addEventListener('resize', apply);
  if (typeof ResizeObserver !== 'undefined') {
    const ro = new ResizeObserver(apply);
    ro.observe(wrapper);
  }
}

// ---------- v0.4.2: best-effort bilibili iframe player progress listener ---
// Bilibili's official player iframe is cross-origin, so we cannot read
// `currentTime` directly. But the player does emit some `postMessage` events.
// We listen for any message originating from a bilibili origin and try to
// recover a `currentTime` (in seconds) under several known field names.
// If we get nothing, this is a no-op and we still rely on ECG hover/click.
function bindBilibiliPostMessage() {
  if (CONFIG.video_mode === 'local') return;  // local <video> already syncs
  window.addEventListener('message', ev => {
    try {
      if (!ev.origin || !/(^|\.)bilibili\.com$/.test(new URL(ev.origin).hostname)) return;
      const d = ev.data;
      if (!d) return;
      let t = null;
      if (typeof d === 'object') {
        if (typeof d.currentTime === 'number') t = d.currentTime;
        else if (typeof d.time === 'number') t = d.time;
        else if (typeof d.value === 'number' && d.event && /time|progress|play/i.test(d.event)) t = d.value;
        else if (d.data && typeof d.data === 'object') {
          if (typeof d.data.currentTime === 'number') t = d.data.currentTime;
          else if (typeof d.data.time === 'number') t = d.data.time;
        }
      } else if (typeof d === 'string') {
        // Some versions send `__playertime__:123.45`-style payloads.
        const m = d.match(/(?:time|progress)\D+(\d+(?:\.\d+)?)/i);
        if (m) t = parseFloat(m[1]);
      }
      if (t !== null && Number.isFinite(t) && t >= 0) {
        // Heuristic: bilibili sometimes ships ms instead of seconds.
        if (t > (META.duration_sec || 0) * 5 && META.duration_sec) t = t / 1000;
        updateVitalReadout(t, '播放中');
      }
    } catch { /* swallow */ }
  });
}

// ---------- bootstrap ----------
mountVideo();
if (SCORES.length > 0) {
  renderOverview();
  renderChart();
  renderWheel();
}
renderDanmakuList();
renderTurnpoints();
mountPanel();
if (SCORES.length > 0) renderVitalStats();
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
