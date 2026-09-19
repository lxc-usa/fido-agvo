/* AVGO 每日追踪 — 配色模式切换（浅色 / 深色 / 系统配色），零依赖
 * <html data-theme="light|dark"> 决定实际配色；
 * data-theme-mode 记录用户选择（light/dark/system），用于按钮高亮。
 * <head> 内的内联小脚本已在首屏前设置好 data-theme，避免闪烁；
 * 本文件负责按钮交互、持久化与跟随系统变化。
 */
(function () {
  "use strict";

  var KEY = "avgo-theme";

  function getMode() {
    try { return localStorage.getItem(KEY) || "system"; }
    catch (e) { return "system"; }
  }

  /* 把用户选择解析为实际生效的 light/dark */
  function resolve(mode) {
    if (mode === "dark" || mode === "light") return mode;
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
    return "light";
  }

  function fireChange() {
    var ev;
    try { ev = new CustomEvent("avgo-theme-change"); }
    catch (e) {
      ev = document.createEvent("Event");
      ev.initEvent("avgo-theme-change", false, false);
    }
    document.dispatchEvent(ev);
  }

  function paint() {
    var mode = getMode();
    var btns = document.querySelectorAll("[data-theme-btn]");
    for (var i = 0; i < btns.length; i++) {
      var on = btns[i].getAttribute("data-theme-btn") === mode;
      btns[i].classList.toggle("active", on);
      if (on) btns[i].setAttribute("aria-pressed", "true");
      else btns[i].removeAttribute("aria-pressed");
    }
  }

  function apply(mode) {
    try { localStorage.setItem(KEY, mode); } catch (e) {}
    document.documentElement.setAttribute("data-theme", resolve(mode));
    document.documentElement.setAttribute("data-theme-mode", mode);
    paint();
    fireChange(); /* 通知 charts.js 用新配色重绘 */
  }

  var btns = document.querySelectorAll("[data-theme-btn]");
  for (var i = 0; i < btns.length; i++) {
    (function (b) {
      b.addEventListener("click", function () { apply(b.getAttribute("data-theme-btn")); });
    })(btns[i]);
  }

  /* 兜底：若 head 内联脚本未执行（如被禁用），这里补上初始配色 */
  if (!document.documentElement.getAttribute("data-theme")) {
    var _m = getMode();
    document.documentElement.setAttribute("data-theme", resolve(_m));
    document.documentElement.setAttribute("data-theme-mode", _m);
  }
  paint();

  /* 系统配色变化时，若用户选的是“系统配色”则自动跟随 */
  if (window.matchMedia) {
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    var onChange = function () {
      if (getMode() === "system") {
        document.documentElement.setAttribute("data-theme", resolve("system"));
        fireChange();
      }
    };
    if (mq.addEventListener) mq.addEventListener("change", onChange);
    else if (mq.addListener) mq.addListener(onChange);
  }
})();
