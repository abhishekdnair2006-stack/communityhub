// CommunityHub UI helpers: profile menu, mobile menu, 3D card tilt, hero scene, toasts, tabs, photo preview, count-up.
(function () {
  var still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Mobile menu
  var nav = document.getElementById('nav'), toggle = document.querySelector('.nav-toggle');
  if (toggle && nav) toggle.addEventListener('click', function () { nav.classList.toggle('open'); });

  // Profile dropdown (avatar circle, top right)
  var btn = document.getElementById('menu-btn'), menu = document.getElementById('menu');
  if (btn && menu) {
    function setMenu(open) {
      menu.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    btn.addEventListener('click', function (e) { e.stopPropagation(); setMenu(!menu.classList.contains('open')); });
    document.addEventListener('click', function (e) { if (!menu.contains(e.target)) setMenu(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { setMenu(false); btn.focus(); } });
  }

  // Toasts
  document.querySelectorAll('.toast').forEach(function (t) {
    t.addEventListener('click', function () { t.remove(); });
    setTimeout(function () { t.remove(); }, 6000);
  });

  if (!still) {
    // 3D tilt with a soft light that follows the mouse
    document.querySelectorAll('.tilt, .product, .kpi, .card.tile').forEach(function (el) {
      el.classList.add('tilt');
      el.addEventListener('mousemove', function (e) {
        var r = el.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        el.style.setProperty('--mx', (x * 100) + '%'); el.style.setProperty('--my', (y * 100) + '%');
        el.style.transform = 'perspective(900px) rotateY(' + ((x - .5) * 8) + 'deg) rotateX(' + (-(y - .5) * 8) + 'deg) translateY(-4px)';
      });
      el.addEventListener('mouseleave', function () { el.style.transform = ''; });
    });

    // Hero 3D scene follows the mouse
    var scene = document.querySelector('.scene'), stack = document.querySelector('.stack3d');
    if (scene && stack) {
      scene.addEventListener('mousemove', function (e) {
        var r = scene.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
        stack.style.transform = 'rotateX(' + (14 - y * 22) + 'deg) rotateY(' + (-22 + x * 34) + 'deg)';
      });
      scene.addEventListener('mouseleave', function () { stack.style.transform = ''; });
    }
  }

  // Count-up for dashboard numbers
  if (!still) {
    document.querySelectorAll('.kpi b').forEach(function (b) {
      var txt = b.textContent.trim();
      if (!/^\d{1,7}$/.test(txt)) return;
      var end = parseInt(txt, 10), t0 = null;
      if (end < 2) return;
      function step(t) {
        if (t0 === null) t0 = t;
        var k = Math.min(1, (t - t0) / 800); b.textContent = Math.round(end * (1 - Math.pow(1 - k, 3)));
        if (k < 1) requestAnimationFrame(step);
      }
      b.textContent = '0'; requestAnimationFrame(step);
    });
  }

  // Segmented tabs
  var segs = document.querySelectorAll('.seg button'), panes = document.querySelectorAll('[data-pane]');
  if (segs.length) {
    function show(name) {
      segs.forEach(function (b) { b.classList.toggle('on', b.dataset.tab === name); });
      panes.forEach(function (p) { p.hidden = p.dataset.pane !== name; });
    }
    segs.forEach(function (b) { b.addEventListener('click', function () { show(b.dataset.tab); }); });
    show(segs[0].dataset.tab);
  }

  // Live preview of a chosen profile photo
  var file = document.querySelector('input[type=file][data-preview]');
  if (file) {
    var target = document.querySelector(file.dataset.preview);
    file.addEventListener('change', function () {
      if (!file.files[0] || !target) return;
      var url = URL.createObjectURL(file.files[0]);
      target.innerHTML = '<img alt="" src="' + url + '">';
    });
  }
})();
