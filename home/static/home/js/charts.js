// Tiny chart helpers (no libraries, works offline): line/area chart, bars, donut. Used by the admin pages.
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var COLORS = ['#2563EB', '#0E9F9A', '#D98A0B', '#6B4FE0', '#D63F66', '#14A06F'];

  function el(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function html(tag, cls, text, parent) {
    var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text;
    if (parent) parent.appendChild(n); return n;
  }
  function niceMax(v) {            // 4 grid steps with whole-number ticks
    if (v <= 4) return 4;
    var need = v / 4, p = Math.pow(10, Math.floor(Math.log10(need))), steps = [1, 2, 3, 4, 5, 6, 8, 10];
    for (var i = 0; i < steps.length; i++) if (steps[i] * p >= need) return steps[i] * p * 4;
    return 10 * p * 4;
  }
  function data(id) { var n = document.getElementById(id); return n ? JSON.parse(n.textContent) : null; }

  // ---------- Line / area chart with hover tooltip ----------
  function line(host, cfg) {
    host.innerHTML = '';
    var labels = cfg.labels, series = cfg.series;
    var W = Math.max(300, host.clientWidth), H = cfg.height || 270;
    var m = { l: 34, r: 14, t: 14, b: 28 }, iw = W - m.l - m.r, ih = H - m.t - m.b;
    var max = niceMax(Math.max.apply(null, [1].concat.apply([], series.map(function (s) { return s.data; }))));
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': cfg.label || 'Line chart' }, host);
    var defs = el('defs', {}, svg);
    var x = function (i) { return m.l + (labels.length < 2 ? iw / 2 : i * iw / (labels.length - 1)); };
    var y = function (v) { return m.t + ih - v * ih / max; };

    for (var g = 0; g <= 4; g++) {
      var gv = max * g / 4, gy = y(gv);
      el('line', { x1: m.l, x2: W - m.r, y1: gy, y2: gy, 'class': 'grid-l' }, svg);
      var t = el('text', { x: m.l - 8, y: gy + 4, 'text-anchor': 'end', 'class': 'axis' }, svg); t.textContent = Math.round(gv * 10) / 10;
    }
    var every = Math.ceil(labels.length / Math.max(2, Math.floor(iw / 62)));
    var lastShown = -999;
    labels.forEach(function (l, i) {
      var last = i === labels.length - 1;
      if (!(i % every === 0 || (last && i - lastShown >= every * 0.8))) return;
      if (last && i - lastShown < every * 0.8) return;
      lastShown = i;
      var tx = el('text', { x: x(i), y: H - 8, 'text-anchor': i === 0 ? 'start' : i === labels.length - 1 ? 'end' : 'middle', 'class': 'axis' }, svg); tx.textContent = l;
    });

    series.forEach(function (s, si) {
      var pts = s.data.map(function (v, i) { return [x(i), y(v)]; });
      // smooth path (monotone-ish via simple catmull-rom to bezier)
      var d = '';
      pts.forEach(function (p, i) {
        if (i === 0) { d = 'M' + p[0] + ',' + p[1]; return; }
        var p0 = pts[i - 2] || pts[i - 1], p1 = pts[i - 1], p2 = p, p3 = pts[i + 1] || p2;
        var c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
        var c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
        c1y = Math.min(Math.max(c1y, m.t), m.t + ih); c2y = Math.min(Math.max(c2y, m.t), m.t + ih);
        d += ' C' + c1x + ',' + c1y + ' ' + c2x + ',' + c2y + ' ' + p2[0] + ',' + p2[1];
      });
      if (si === 0 || series.length <= 2) {
        var gid = 'ag' + Math.random().toString(36).slice(2, 7);
        var lg = el('linearGradient', { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
        el('stop', { offset: 0, 'stop-color': s.color, 'stop-opacity': .22 }, lg); el('stop', { offset: 1, 'stop-color': s.color, 'stop-opacity': 0 }, lg);
        el('path', { d: d + ' L' + pts[pts.length - 1][0] + ',' + (m.t + ih) + ' L' + pts[0][0] + ',' + (m.t + ih) + ' Z', fill: 'url(#' + gid + ')', 'class': 'area' }, svg);
      }
      el('path', { d: d, fill: 'none', stroke: s.color, 'stroke-width': 2.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', pathLength: 1, 'class': 'draw' }, svg);
    });

    var guide = el('line', { y1: m.t, y2: m.t + ih, stroke: 'rgba(15,27,51,.25)', 'stroke-width': 1, opacity: 0 }, svg);
    var dots = series.map(function (s) { return el('circle', { r: 4.5, fill: '#fff', stroke: s.color, 'stroke-width': 2.5, opacity: 0 }, svg); });
    var tip = html('div', 'tip', null, host);
    var hit = el('rect', { x: m.l, y: m.t, width: iw, height: ih, fill: 'transparent' }, svg);
    function move(e) {
      var r = svg.getBoundingClientRect(), px = (e.clientX - r.left) * W / r.width;
      var i = Math.max(0, Math.min(labels.length - 1, Math.round((px - m.l) / (iw / Math.max(1, labels.length - 1)))));
      guide.setAttribute('x1', x(i)); guide.setAttribute('x2', x(i)); guide.setAttribute('opacity', 1);
      tip.innerHTML = '';
      html('b', '', labels[i], tip);
      series.forEach(function (s, si) {
        dots[si].setAttribute('cx', x(i)); dots[si].setAttribute('cy', y(s.data[i])); dots[si].setAttribute('opacity', 1);
        var row = html('div', '', null, tip), left = html('span', '', null, row);
        var sw = html('i', '', null, left); sw.style.background = s.color; left.appendChild(document.createTextNode(s.name));
        html('strong', '', s.data[i], row);
      });
      var tx = x(i) * r.width / W + 14; if (tx > r.width - 160) tx = x(i) * r.width / W - 160;
      tip.style.left = tx + 'px'; tip.style.top = '8px'; tip.classList.add('on');
    }
    function leave() { guide.setAttribute('opacity', 0); dots.forEach(function (d) { d.setAttribute('opacity', 0); }); tip.classList.remove('on'); }
    hit.addEventListener('mousemove', move); hit.addEventListener('mouseleave', leave);
    hit.addEventListener('touchstart', function (e) { move(e.touches[0]); }, { passive: true });
    hit.addEventListener('touchmove', function (e) { move(e.touches[0]); }, { passive: true });

    var lg2 = html('div', 'chart-legend', null, host);
    series.forEach(function (s) {
      var sp = html('span', '', null, lg2); var sw = html('i', '', null, sp); sw.style.background = s.color; sp.appendChild(document.createTextNode(s.name + ' (' + s.data.reduce(function (a, b) { return a + b; }, 0) + ')'));
    });
  }

  // ---------- Horizontal bars ----------
  function bars(host, items) {
    host.innerHTML = '';
    var max = Math.max.apply(null, [1].concat(items.map(function (i) { return i.value; })));
    if (!items.length) { html('div', 'chart-empty', 'No data yet.', host); return; }
    items.forEach(function (it, i) {
      var row = html('div', 'bar-row', null, host);
      var lab = html('span', '', it.label, row); lab.title = it.label;
      var track = html('div', 'track', null, row), fill = html('div', 'fill', null, track);
      fill.style.width = (it.value * 100 / max) + '%'; fill.style.background = it.color || COLORS[i % COLORS.length]; fill.style.animationDelay = (i * 70) + 'ms';
      html('b', '', it.value, row);
    });
  }

  // ---------- Donut ----------
  function donut(host, items, unit) {
    host.innerHTML = '';
    var total = items.reduce(function (a, b) { return a + b.value; }, 0);
    var wrap = html('div', 'donut-wrap', null, host), d = html('div', 'donut', null, wrap);
    var svg = el('svg', { viewBox: '0 0 100 100' }, d), R = 40, C = 2 * Math.PI * R, off = 0;
    el('circle', { cx: 50, cy: 50, r: R, stroke: 'rgba(15,27,51,.07)' }, svg);
    var segs = [];
    items.forEach(function (it, i) {
      var len = total ? it.value * C / total : 0, col = it.color || COLORS[i % COLORS.length];
      if (len <= 0) { segs.push(null); return; }
      var gap = items.filter(function (x) { return x.value > 0; }).length > 1 ? 1.2 : 0;
      var c = el('circle', { cx: 50, cy: 50, r: R, stroke: col, 'stroke-dasharray': Math.max(0, len - gap) + ' ' + (C - Math.max(0, len - gap)), 'stroke-dashoffset': -off, 'class': 'seg-c' }, svg);
      c.style.animationDelay = (i * 90) + 'ms'; segs.push(c); off += len;
    });
    var mid = html('div', 'mid', null, d); html('b', '', total, mid); html('span', '', unit || 'total', mid);
    var ul = html('ul', 'legend', null, wrap);
    items.forEach(function (it, i) {
      var li = html('li', '', null, ul), sw = html('i', '', null, li); sw.style.background = it.color || COLORS[i % COLORS.length];
      li.appendChild(document.createTextNode(it.label)); html('b', '', it.value, li);
      li.addEventListener('mouseenter', function () { d.classList.add('hov'); if (segs[i]) segs[i].classList.add('act'); });
      li.addEventListener('mouseleave', function () { d.classList.remove('hov'); if (segs[i]) segs[i].classList.remove('act'); });
    });
  }

  window.HubCharts = { line: line, bars: bars, donut: donut, data: data };
})();
