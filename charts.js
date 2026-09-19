/* AVGO 每日追踪 — 零依赖 Canvas 图表库
 * 包含：价格+均线主图、成交量副图、RSI 副图、首页迷你线
 * 数据通过 <script type="application/json"> 嵌入，canvas 用 data-* 属性引用
 */
(function () {
  "use strict";

  /* 图表颜色跟随 CSS 变量（浅色/深色主题自适应）；取不到时回退为深色值 */
  function cssVar(name) {
    if (typeof getComputedStyle !== "function") return "";
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return v ? v.trim() : "";
  }
  function themeColors() {
    function pick(name, fallback) { var v = cssVar(name); return v || fallback; }
    return {
      grid: pick("--chart-grid", "#1c2740"),
      text: pick("--chart-text", "#8b99b0"),
      price: pick("--chart-price", "#5b8cff"),
      ma20: pick("--chart-ma20", "#f0b90b"),
      ma50: pick("--chart-ma50", "#16c784"),
      ma200: pick("--chart-ma200", "#b07cff"),
      up: pick("--chart-up", "#16c784"),
      down: pick("--chart-down", "#ea3943"),
      last: pick("--chart-last", "#e9eef6"),
      rsi: pick("--chart-rsi", "#5b8cff"),
      rsiHot: pick("--chart-rsi-hot", "#ea3943"),
      rsiCool: pick("--chart-rsi-cool", "#16c784"),
      cross: pick("--chart-cross", "rgba(233,238,246,0.35)")
    };
  }

  var PRICE_WIN = 130;  // 主图显示最近约 6 个月交易日
  var SPARK_WIN = 66;   // 首页迷你线约 3 个月

  function $(id) { return document.getElementById(id); }

  function getData(canvas, attr) {
    var el = $(canvas.getAttribute(attr));
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  /* 按 devicePixelRatio 适配 canvas，返回绘图上下文与 CSS 尺寸 */
  function fit(canvas) {
    var dpr = window.devicePixelRatio || 1;
    var w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return null;
    var W = Math.round(w * dpr), H = Math.round(h * dpr);
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    var ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return { ctx: ctx, w: w, h: h };
  }

  function fmtDate(s) { return s ? s.slice(5).replace("-", "/") : ""; } // MM/DD

  function fmtVol(v) {
    if (v == null) return "--";
    if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(0) + "K";
    return "" + v;
  }

  /* 折线：自动跳过 null 断点 */
  function drawLine(ctx, ys, X, Y, color, width) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width || 1.6;
    ctx.lineJoin = "round";
    ctx.beginPath();
    var started = false;
    for (var i = 0; i < ys.length; i++) {
      if (ys[i] == null) { started = false; continue; }
      var px = X(i), py = Y(ys[i]);
      if (!started) { ctx.moveTo(px, py); started = true; }
      else { ctx.lineTo(px, py); }
    }
    ctx.stroke();
  }

  /* 好看的 Y 轴刻度 */
  function yTicks(lo, hi, n) {
    if (!(hi > lo)) hi = lo + 1;
    var span = hi - lo, raw = span / n;
    var mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var norm = raw / mag, step;
    if (norm < 1.5) step = 1; else if (norm < 3.5) step = 2; else if (norm < 7.5) step = 5; else step = 10;
    step *= mag;
    var out = [], v;
    for (v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(v);
    return out;
  }

  function axisStyle(ctx) {
    ctx.font = "10px -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif";
    ctx.textBaseline = "middle";
  }

  function crosshair(ctx, box, hl, color) {
    if (hl < 0) return;
    var x = box.padL + box.iw * (box.m === 1 ? 0.5 : hl / (box.m - 1));
    ctx.save();
    ctx.strokeStyle = color || "rgba(128,128,128,0.35)";
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(x, box.padT);
    ctx.lineTo(x, box.padT + box.ih);
    ctx.stroke();
    ctx.restore();
  }

  /* 每个 canvas 只绑定一次 pointer 事件；box/redraw/tipHtml 每次重绘时更新 */
  function ensureTip(canvas) {
    if (canvas._tipOn) return;
    canvas._tipOn = true;
    var wrap = canvas.parentNode;
    var tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    wrap.appendChild(tip);
    var cur = -1;
    canvas.addEventListener("pointermove", function (e) {
      var box = canvas._chartBox;
      if (!box) return;
      var r = canvas.getBoundingClientRect();
      var x = (e.clientX - r.left - box.padL) / box.iw * (box.m - 1);
      var idx = Math.round(x);
      if (idx < 0) idx = 0;
      if (idx > box.m - 1) idx = box.m - 1;
      if (idx !== cur && canvas._chartRedraw) { cur = idx; canvas._chartRedraw(idx); }
      var px = box.padL + box.iw * (box.m === 1 ? 0.5 : idx / (box.m - 1));
      tip.innerHTML = canvas._chartTipHtml(idx);
      tip.hidden = false;
      var tw = tip.offsetWidth, th = tip.offsetHeight;
      var left = px + 14;
      if (left + tw > box.w - 4) left = px - tw - 14;
      tip.style.left = left + "px";
      tip.style.top = Math.max(4, r.height / 2 - th / 2) + "px";
    });
    canvas.addEventListener("pointerleave", function () {
      cur = -1; tip.hidden = true;
      if (canvas._chartRedraw) canvas._chartRedraw(-1);
    });
  }

  /* ═══════════ 主图：收盘价 + MA20/50/200 ═══════════ */
  function priceChart(canvas, D, hl) {
    var THEME = themeColors();
    var f = fit(canvas); if (!f) return;
    var ctx = f.ctx, W = f.w, H = f.h;
    var n = D.close.length, s = Math.max(0, n - PRICE_WIN);
    var dates = D.dates.slice(s), close = D.close.slice(s);
    var ma20 = D.ma20.slice(s), ma50 = D.ma50.slice(s), ma200 = D.ma200.slice(s);
    var m = close.length;
    var padL = 6, padR = 54, padT = 10, padB = 22;
    var iw = W - padL - padR, ih = H - padT - padB;
    var lo = Infinity, hi = -Infinity, i, j, v;
    [close, ma20, ma50, ma200].forEach(function (arr) {
      for (j = 0; j < arr.length; j++) {
        v = arr[j];
        if (v != null) { if (v < lo) lo = v; if (v > hi) hi = v; }
      }
    });
    var pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
    function X(k) { return padL + (m === 1 ? iw / 2 : k / (m - 1) * iw); }
    function Y(val) { return padT + ih - (val - lo) / (hi - lo) * ih; }

    axisStyle(ctx);
    yTicks(lo, hi, 5).forEach(function (t) {
      var yy = Y(t);
      ctx.strokeStyle = THEME.grid; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(W - padR, yy); ctx.stroke();
      ctx.fillStyle = THEME.text;
      ctx.fillText(t.toFixed(0), W - padR + 6, yy);
    });
    ctx.fillStyle = THEME.text;
    var step = Math.max(1, Math.ceil(m / 6));
    for (i = 0; i < m; i += step) ctx.fillText(fmtDate(dates[i]), X(i) - 15, H - 10);

    drawLine(ctx, ma200, X, Y, THEME.ma200, 1.2);
    drawLine(ctx, ma50, X, Y, THEME.ma50, 1.2);
    drawLine(ctx, ma20, X, Y, THEME.ma20, 1.2);
    drawLine(ctx, close, X, Y, THEME.price, 1.8);

    var last = close[m - 1];
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = THEME.last; ctx.globalAlpha = 0.5; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, Y(last)); ctx.lineTo(W - padR, Y(last)); ctx.stroke();
    ctx.restore();
    ctx.fillStyle = THEME.last;
    ctx.fillText(last.toFixed(2), W - padR + 6, Y(last) - 9);

    var box = { padL: padL, padT: padT, iw: iw, ih: ih, m: m, w: W };
    crosshair(ctx, box, hl == null ? -1 : hl, THEME.cross);
    canvas._chartBox = box;
    canvas._chartRedraw = function (h) { priceChart(canvas, D, h); };
    canvas._chartTipHtml = function (idx) {
      var gi = s + idx;
      var c = D.close[gi], pc = gi > 0 ? D.close[gi - 1] : null;
      var chg = pc ? (c / pc - 1) * 100 : null;
      var cls = chg == null ? "" : (chg >= 0 ? "t-up" : "t-down");
      var chgTxt = chg == null ? "--" : (chg >= 0 ? "+" : "") + chg.toFixed(2) + "%";
      function mv(arr, name) {
        var val = arr[gi];
        return val == null ? "" : "<div>" + name + " <b>" + val.toFixed(2) + "</b></div>";
      }
      return "<div class='tt-date'>" + D.dates[gi] + "</div>" +
        "<div>收盘 <b>$" + c.toFixed(2) + "</b> <span class='" + cls + "'>" + chgTxt + "</span></div>" +
        mv(D.ma20, "MA20") + mv(D.ma50, "MA50") + mv(D.ma200, "MA200");
    };
    ensureTip(canvas);
  }

  /* ═══════════ 副图：成交量 ═══════════ */
  function volumeChart(canvas, D, hl) {
    var THEME = themeColors();
    var f = fit(canvas); if (!f) return;
    var ctx = f.ctx, W = f.w, H = f.h;
    var n = D.close.length, s = Math.max(0, n - PRICE_WIN);
    var dates = D.dates.slice(s), vol = D.volume.slice(s),
        open = D.open.slice(s), close = D.close.slice(s);
    var m = vol.length;
    var padL = 6, padR = 54, padT = 8, padB = 20;
    var iw = W - padL - padR, ih = H - padT - padB;
    var vmax = 0, i;
    for (i = 0; i < m; i++) if (vol[i] != null && vol[i] > vmax) vmax = vol[i];
    vmax = vmax || 1;
    function X(k) { return padL + (m === 1 ? iw / 2 : k / (m - 1) * iw); }
    var bw = Math.max(1, iw / m * 0.7);
    for (i = 0; i < m; i++) {
      if (vol[i] == null) continue;
      var hh = vol[i] / vmax * ih;
      ctx.fillStyle = close[i] >= open[i] ? "rgba(22,199,132,0.75)" : "rgba(234,57,67,0.75)";
      ctx.fillRect(X(i) - bw / 2, padT + ih - hh, bw, hh);
    }
    axisStyle(ctx);
    ctx.fillStyle = THEME.text;
    ctx.fillText(fmtVol(vmax), W - padR + 6, padT + 6);
    var step = Math.max(1, Math.ceil(m / 6));
    for (i = 0; i < m; i += step) ctx.fillText(fmtDate(dates[i]), X(i) - 15, H - 9);
    var box = { padL: padL, padT: padT, iw: iw, ih: ih, m: m, w: W };
    crosshair(ctx, box, hl == null ? -1 : hl, THEME.cross);
    canvas._chartBox = box;
    canvas._chartRedraw = function (h) { volumeChart(canvas, D, h); };
    canvas._chartTipHtml = function (idx) {
      var gi = s + idx;
      return "<div class='tt-date'>" + D.dates[gi] + "</div>" +
        "<div>成交量 <b>" + fmtVol(D.volume[gi]) + "</b></div>";
    };
    ensureTip(canvas);
  }

  /* ═══════════ 副图：RSI(14) ═══════════ */
  function rsiChart(canvas, D, hl) {
    var THEME = themeColors();
    var f = fit(canvas); if (!f) return;
    var ctx = f.ctx, W = f.w, H = f.h;
    var n = D.rsi.length, s = Math.max(0, n - PRICE_WIN);
    var dates = D.dates.slice(s), rsi = D.rsi.slice(s);
    var m = rsi.length;
    var padL = 6, padR = 54, padT = 8, padB = 20;
    var iw = W - padL - padR, ih = H - padT - padB;
    function X(k) { return padL + (m === 1 ? iw / 2 : k / (m - 1) * iw); }
    function Y(val) { return padT + ih - val / 100 * ih; }
    axisStyle(ctx);
    [[70, THEME.rsiHot, "超买 70"], [50, THEME.grid, "50"], [30, THEME.rsiCool, "超卖 30"]].forEach(function (L) {
      var yy = Y(L[0]);
      ctx.save();
      ctx.setLineDash(L[0] === 50 ? [2, 4] : [4, 4]);
      ctx.strokeStyle = L[1]; ctx.lineWidth = 1; ctx.globalAlpha = L[0] === 50 ? 0.8 : 0.6;
      ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(W - padR, yy); ctx.stroke();
      ctx.restore();
      ctx.fillStyle = THEME.text;
      ctx.fillText(L[2], W - padR + 6, yy);
    });
    drawLine(ctx, rsi, X, Y, THEME.rsi, 1.6);
    var lastV = null, i;
    for (i = m - 1; i >= 0; i--) { if (rsi[i] != null) { lastV = rsi[i]; break; } }
    if (lastV != null) {
      ctx.fillStyle = THEME.last;
      ctx.fillText(lastV.toFixed(1), W - padR + 6, Y(lastV) - 9);
    }
    ctx.fillStyle = THEME.text;
    var step = Math.max(1, Math.ceil(m / 6));
    for (i = 0; i < m; i += step) ctx.fillText(fmtDate(dates[i]), X(i) - 15, H - 9);
    var box = { padL: padL, padT: padT, iw: iw, ih: ih, m: m, w: W };
    crosshair(ctx, box, hl == null ? -1 : hl, THEME.cross);
    canvas._chartBox = box;
    canvas._chartRedraw = function (h) { rsiChart(canvas, D, h); };
    canvas._chartTipHtml = function (idx) {
      var gi = s + idx, val = D.rsi[gi];
      return "<div class='tt-date'>" + D.dates[gi] + "</div>" +
        "<div>RSI(14) <b>" + (val == null ? "--" : val.toFixed(1)) + "</b></div>";
    };
    ensureTip(canvas);
  }

  /* ═══════════ 首页迷你线 ═══════════ */
  function sparkline(canvas) {
    var THEME = themeColors();
    var data = getData(canvas, "data-spark");
    var f = fit(canvas); if (!f || !data) return;
    var ctx = f.ctx, W = f.w, H = f.h;
    var closes = data.slice(Math.max(0, data.length - SPARK_WIN));
    var m = closes.length; if (!m) return;
    var lo = Math.min.apply(null, closes), hi = Math.max.apply(null, closes);
    var pad = (hi - lo) * 0.15 || 1; lo -= pad; hi += pad;
    function X(k) { return m === 1 ? W / 2 : k / (m - 1) * W; }
    function Y(v) { return 4 + (H - 8) - (v - lo) / (hi - lo) * (H - 8); }
    var up = closes[m - 1] >= closes[0];
    var col = up ? THEME.up : THEME.down;
    var grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, up ? "rgba(22,199,132,0.30)" : "rgba(234,57,67,0.30)");
    grad.addColorStop(1, "rgba(0,0,0,0)");
    ctx.beginPath();
    for (var i = 0; i < m; i++) {
      if (i === 0) ctx.moveTo(X(i), Y(closes[i]));
      else ctx.lineTo(X(i), Y(closes[i]));
    }
    ctx.strokeStyle = col; ctx.lineWidth = 1.8; ctx.lineJoin = "round"; ctx.stroke();
    ctx.lineTo(X(m - 1), H); ctx.lineTo(X(0), H); ctx.closePath();
    ctx.fillStyle = grad; ctx.fill();
    ctx.beginPath();
    ctx.arc(X(m - 1), Y(closes[m - 1]), 2.6, 0, Math.PI * 2);
    ctx.fillStyle = col; ctx.fill();
  }

  /* ═══════════ 初始化 ═══════════ */
  var redrawFns = [];
  function init() {
    document.querySelectorAll("canvas[data-price]").forEach(function (cv) {
      var D = getData(cv, "data-price"); if (!D) return;
      var draw = function () { priceChart(cv, D, -1); };
      redrawFns.push(draw); draw();
    });
    document.querySelectorAll("canvas[data-volume]").forEach(function (cv) {
      var D = getData(cv, "data-volume"); if (!D) return;
      var draw = function () { volumeChart(cv, D, -1); };
      redrawFns.push(draw); draw();
    });
    document.querySelectorAll("canvas[data-rsi]").forEach(function (cv) {
      var D = getData(cv, "data-rsi"); if (!D) return;
      var draw = function () { rsiChart(cv, D, -1); };
      redrawFns.push(draw); draw();
    });
    document.querySelectorAll("canvas[data-spark]").forEach(function (cv) {
      var draw = function () { sparkline(cv); };
      redrawFns.push(draw); draw();
    });

    /* 配色切换（theme.js 触发）时用新主题颜色重绘所有图表 */
    document.addEventListener("avgo-theme-change", function () {
      redrawFns.forEach(function (fn) { fn(); });
    });

    var t = null;
    function onResize() {
      if (t) clearTimeout(t);
      t = setTimeout(function () { redrawFns.forEach(function (fn) { fn(); }); }, 150);
    }
    if (window.ResizeObserver) {
      var seen = [];
      var ro = new ResizeObserver(onResize);
      document.querySelectorAll("canvas[data-price],canvas[data-volume],canvas[data-rsi],canvas[data-spark]")
        .forEach(function (cv) {
          var p = cv.parentNode;
          if (p && seen.indexOf(p) < 0) { seen.push(p); ro.observe(p); }
        });
    } else {
      window.addEventListener("resize", onResize);
      window.addEventListener("orientationchange", onResize);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
