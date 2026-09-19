/* 顶栏滚动行为：往下滚隐藏，往上滚显示 */
(function () {
  var header = document.querySelector('.site-header');
  if (!header) return;

  var lastY = window.scrollY || window.pageYOffset;
  var ticking = false;
  var THRESHOLD = 8;  // 滚动超过这点距离才触发，避免轻微抖动
  var TOP_ZONE = 80;  // 页面顶部区域内始终显示

  function onScroll() {
    var y = window.scrollY || window.pageYOffset;
    var dy = y - lastY;
    lastY = y;
    if (Math.abs(dy) < THRESHOLD) { ticking = false; return; }

    var menuOpen = header.classList.contains('nav-open');
    if (y <= TOP_ZONE || menuOpen) {
      // 回到顶部或移动端菜单正打开时：始终显示
      header.classList.remove('header-hidden');
    } else if (dy > 0) {
      header.classList.add('header-hidden');    // 往下滚 → 隐藏
    } else {
      header.classList.remove('header-hidden'); // 往上滚 → 显示
    }
    ticking = false;
  }

  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
})();
