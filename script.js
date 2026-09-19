/* AVGO 每日追踪 — 归档按日期筛选（原生 JS，无依赖） */
(function () {
  var input = document.getElementById("archive-filter");
  var clearBtn = document.getElementById("archive-clear");
  var list = document.getElementById("archive-list");
  var empty = document.getElementById("archive-empty");
  if (!input || !list) return;

  /* 日期框占位提示：平时显示"请选择日期"，聚焦后切换为原生日期选择器 */
  input.addEventListener("focus", function () { input.type = "date"; });
  input.addEventListener("blur", function () { if (!input.value) input.type = "text"; });

  function applyFilter() {
    var q = (input.value || "").trim();
    var visible = 0;
    var cards = list.querySelectorAll(".archive-card");
    for (var i = 0; i < cards.length; i++) {
      var hit = !q || (cards[i].getAttribute("data-date") || "").indexOf(q) !== -1;
      cards[i].style.display = hit ? "" : "none";
      if (hit) visible++;
    }
    if (empty) empty.hidden = visible > 0;
  }

  input.addEventListener("input", applyFilter);
  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      input.value = "";
      applyFilter();
      input.focus();
    });
  }
})();
