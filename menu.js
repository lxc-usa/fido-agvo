/* 移动端汉堡菜单：小屏幕下导航折叠，点击展开/收起 */
(function () {
  var header = document.querySelector('.site-header');
  var btn = document.querySelector('.menu-toggle');
  var nav = document.getElementById('site-nav');
  if (!header || !btn || !nav) return;

  function setOpen(open) {
    header.classList.toggle('nav-open', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    btn.setAttribute('aria-label', open ? '关闭菜单' : '打开菜单');
  }

  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    setOpen(!header.classList.contains('nav-open'));
  });

  // 点菜单里的链接后自动收起
  nav.addEventListener('click', function (e) {
    if (e.target.closest('a')) setOpen(false);
  });

  // 点页面其他地方收起
  document.addEventListener('click', function (e) {
    if (header.classList.contains('nav-open') && !header.contains(e.target)) setOpen(false);
  });

  // Esc 收起
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') setOpen(false);
  });
})();
