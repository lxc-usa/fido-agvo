#!/usr/bin/env python3
"""生成带图表的 AVGO 日报页面并更新首页。

用法:
    python3 build_brief.py 2026-09-19

读取 tools/input/<date>.json（编辑性内容：要点、栏目、来源等），从 Yahoo Finance
拉取 AVGO 日线数据并计算均线/RSI，然后：
  1. 生成 briefs/<date>.html（含价格+均线/成交量/RSI 图表，Canvas 零依赖渲染）
  2. 更新 index.html 的"最新一期"区块（含迷你走势线）与历史归档列表
  3. 生成 charts/avgo-<date>.png（供聊天简报配图），并清理 14 天前的旧图
"""
import datetime
import glob
import html as htmlmod
import json
import os
import re
import sys
import urllib.request

SITE = os.path.expanduser("~/workspace/avgo-site")
TOOLS = os.path.join(SITE, "tools")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def fetch_daily():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/AVGO?interval=1d&range=1y"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    r = payload["chart"]["result"][0]
    ts = r["timestamp"]
    q = r["indicators"]["quote"][0]
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or []
    rows = []
    for i, t in enumerate(ts):
        dt = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date().isoformat()
        px = adj[i] if i < len(adj) and adj[i] else q["close"][i]
        if px is None:
            continue
        rows.append({
            "date": dt,
            "open": q["open"][i], "high": q["high"][i],
            "low": q["low"][i], "close": px, "volume": q["volume"][i],
        })
    return rows


def add_indicators(rows):
    closes = [r["close"] for r in rows]
    n = len(closes)

    def ma(k):
        out = []
        for i in range(n):
            out.append(round(sum(closes[i - k + 1:i + 1]) / k, 2) if i >= k - 1 else None)
        return out

    # RSI(14), Wilder 平滑
    rsi = [None] * n
    if n > 14:
        gains, losses = [], []
        for i in range(1, n):
            ch = closes[i] - closes[i - 1]
            gains.append(max(ch, 0.0))
            losses.append(max(-ch, 0.0))
        ag = sum(gains[:14]) / 14
        al = sum(losses[:14]) / 14
        rsi[14] = round(100.0 if al == 0 else 100 - 100 / (1 + ag / al), 1)
        for i in range(15, n):
            ag = (ag * 13 + gains[i - 1]) / 14
            al = (al * 13 + losses[i - 1]) / 14
            rsi[i] = round(100.0 if al == 0 else 100 - 100 / (1 + ag / al), 1)

    ma20, ma50, ma200 = ma(20), ma(50), ma(200)
    for i, r in enumerate(rows):
        r["ma20"] = ma20[i]
        r["ma50"] = ma50[i]
        r["ma200"] = ma200[i]
        r["rsi"] = rsi[i]
    return rows


def chart_json(rows):
    data = {
        "dates": [r["date"] for r in rows],
        "open": [round(r["open"], 2) if r["open"] else None for r in rows],
        "high": [round(r["high"], 2) if r["high"] else None for r in rows],
        "low": [round(r["low"], 2) if r["low"] else None for r in rows],
        "close": [round(r["close"], 2) for r in rows],
        "volume": [r["volume"] for r in rows],
        "ma20": [r["ma20"] for r in rows],
        "ma50": [r["ma50"] for r in rows],
        "ma200": [r["ma200"] for r in rows],
        "rsi": [r["rsi"] for r in rows],
    }
    return json.dumps(data, separators=(",", ":"))


def render_brief_page(date_str, brief, rows, stats):
    with open(os.path.join(TOOLS, "brief_template.html"), encoding="utf-8") as f:
        tpl = f.read()

    sections_html = []
    for sec in brief["sections"]:
        items = "\n".join("<li>%s</li>" % it for it in sec["items"])
        sections_html.append(
            '<section class="brief-section">\n<h3>%s</h3>\n<ul>\n%s\n</ul>\n</section>'
            % (sec["title"], items))
    key_points = "\n".join("<li>%s</li>" % kp for kp in brief["key_points"])
    ref_links = brief.get("ref_links", [])[:10]  # 最多 10 条，只列主要的
    if ref_links:
        ref_html = "\n".join(
            '<li><a href="%s" target="_blank" rel="noopener">%s</a></li>'
            % (htmlmod.escape(l["url"], quote=True), htmlmod.escape(l["title"]))
            for l in ref_links)
    else:
        ref_html = "<li>本期暂无外部参考链接，数据来源见下方说明。</li>"

    token_map = {
        "%%DATE%%": date_str,
        "%%WEEKDAY%%": WEEKDAYS[datetime.date.fromisoformat(date_str).weekday()],
        "%%CUTOFF%%": stats["cutoff"],
        "%%PRICE%%": stats["price"],
        "%%CHANGE_PCT%%": stats["change_pct"],
        "%%CHANGE_CLASS%%": stats["change_class"],
        "%%MA20%%": stats["ma20"],
        "%%MA50%%": stats["ma50"],
        "%%MA200%%": stats["ma200"],
        "%%RSI%%": stats["rsi"],
        "%%RATING%%": brief.get("rating", "未确认"),
        "%%RATING_CLASS%%": brief.get("rating_class", "neutral"),
        "%%TARGET%%": brief.get("target_avg", "未确认"),
        "%%KEY_POINTS%%": key_points,
        "%%SECTIONS%%": "\n\n".join(sections_html),
        "%%SOURCES%%": stats["sources"],
        "%%REF_LINKS%%": ref_html,
        "%%CHART_JSON%%": chart_json(rows),
    }
    for tok, val in token_map.items():
        tpl = tpl.replace(tok, val)
    out = os.path.join(SITE, "briefs", date_str + ".html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(tpl)
    return out


def update_index(date_str, brief, rows, stats):
    path = os.path.join(SITE, "index.html")
    with open(path, encoding="utf-8") as f:
        html = f.read()

    spark = json.dumps([round(r["close"], 2) for r in rows[-66:]], separators=(",", ":"))
    key_points = "\n".join("        <li>%s</li>" % kp for kp in brief["key_points"])
    latest = """<section id="latest">
    <div class="section-head">
      <h2>最新一期</h2>
      <span class="date-tag">%s · 数据截至 %s 美股收盘</span>
    </div>
    <article class="brief-card featured">
      <div class="price-row">
        <div class="price num">$%s</div>
        <div class="change %s">%s</div>
      </div>
      <div class="spark-wrap"><canvas class="sparkline" data-spark="spark-latest"></canvas></div>
      <script type="application/json" id="spark-latest">%s</script>
      <ul class="key-points">
%s
      </ul>
      <a class="btn" href="briefs/%s.html">阅读完整日报 →</a>
    </article>
  </section>""" % (date_str, stats["cutoff"], stats["price"], stats["change_class"],
                   stats["change_pct"], spark, key_points, date_str)

    html = re.sub(
        r"<!-- ═══ 最新一期：每日更新时修改本区块 ═══ -->.*?<!-- ═══ 最新一期结束 ═══ -->",
        "<!-- ═══ 最新一期：每日更新时修改本区块 ═══ -->\n" + latest +
        "\n  <!-- ═══ 最新一期结束 ═══ -->",
        html, flags=re.DOTALL)

    if 'data-date="%s"' % date_str not in html:
        card = """      <a class="archive-card" href="briefs/%s.html" data-date="%s">
        <span class="archive-date">%s</span>
        <span class="archive-title">%s</span>
        <span class="archive-arrow">→</span>
      </a>
""" % (date_str, date_str, date_str, brief["archive_title"])
        html = html.replace(
            "<!-- ═══ 归档列表：新增日报时在此处最上方添加一条卡片 ═══ -->\n",
            "<!-- ═══ 归档列表：新增日报时在此处最上方添加一条卡片 ═══ -->\n" + card,
            1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def make_chat_png(date_str, rows):
    """生成供聊天简报配图的深色 PNG（价格+均线/成交量）。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = rows[-130:]
    dates = [r["date"][5:].replace("-", "/") for r in rows]
    closes = [r["close"] for r in rows]
    vols = [r["volume"] or 0 for r in rows]
    opens = [r["open"] or 0 for r in rows]

    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 6), gridspec_kw={"height_ratios": [3, 1]},
        facecolor="#0a0e15")
    for ax in (ax1, ax2):
        ax.set_facecolor("#0a0e15")
        ax.tick_params(colors="#8b99b0", labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#1f2b40")

    x = range(len(rows))
    ax1.plot(x, closes, color="#5b8cff", lw=1.8, label="收盘价")
    for key, color, label in (("ma20", "#f0b90b", "MA20"), ("ma50", "#16c784", "MA50"),
                              ("ma200", "#b07cff", "MA200")):
        ys = [r[key] for r in rows]
        ax1.plot(x, ys, color=color, lw=1.1, label=label)
    ax1.set_title("AVGO 价格走势与均线（近6个月）", color="#e9eef6", fontsize=13, pad=10)
    ax1.legend(facecolor="#121a29", edgecolor="#1f2b40", labelcolor="#e9eef6",
               fontsize=9, loc="upper left")
    ax1.grid(color="#1c2740", lw=0.6, alpha=0.8)

    colors = ["#16c784" if c >= o else "#ea3943" for c, o in zip(closes, opens)]
    ax2.bar(x, vols, color=colors, width=1.0, alpha=0.8)
    ax2.set_title("成交量", color="#e9eef6", fontsize=11, pad=8)
    ax2.ticklabel_format(style="plain", axis="y")

    step = max(1, len(rows) // 6)
    ticks = list(range(0, len(rows), step))
    for ax in (ax1, ax2):
        ax.set_xticks(ticks)
        ax.set_xticklabels([dates[i] for i in ticks], rotation=0)

    fig.tight_layout(pad=2.0)
    outdir = os.path.join(SITE, "charts")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "avgo-%s.png" % date_str)
    fig.savefig(out, dpi=110, facecolor="#0a0e15", bbox_inches="tight")
    plt.close(fig)

    # 清理 14 天前的旧图
    cutoff = datetime.date.today() - datetime.timedelta(days=14)
    for p in glob.glob(os.path.join(outdir, "avgo-*.png")):
        m = re.search(r"avgo-(\d{4}-\d{2}-\d{2})\.png$", p)
        if m and datetime.date.fromisoformat(m.group(1)) < cutoff:
            os.remove(p)
    return out


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", sys.argv[1]):
        print("用法: python3 build_brief.py YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)
    date_str = sys.argv[1]
    inp = os.path.join(TOOLS, "input", date_str + ".json")
    if not os.path.exists(inp):
        print("缺少输入文件: %s" % inp, file=sys.stderr)
        sys.exit(1)
    with open(inp, encoding="utf-8") as f:
        brief = json.load(f)

    print("拉取 AVGO 日线数据…")
    rows = add_indicators(fetch_daily())
    last = rows[-1]
    prev = rows[-2]
    chg = (last["close"] / prev["close"] - 1) * 100
    lo20 = min(r["close"] for r in rows[-20:])
    hi20 = max(r["close"] for r in rows[-20:])
    stats = {
        "cutoff": last["date"],
        "price": "%.2f" % last["close"],
        "change_pct": "%+.1f%%" % chg,
        "change_class": "up" if chg >= 0 else "down",
        "ma20": "%.2f" % last["ma20"],
        "ma50": "%.2f" % last["ma50"],
        "ma200": "%.2f" % last["ma200"],
        "rsi": "%.1f" % last["rsi"],
        "range20": "%.2f – %.2f" % (lo20, hi20),
        "volume": last["volume"],
        "sources": ("行情、均线与 RSI 基于 Yahoo Finance AVGO 日线数据（复权价）计算，"
                    "数据截至 %s 美股收盘；" % last["date"]) + brief.get("sources_extra", ""),
    }
    print("最新: %s 收盘 $%s (%s), MA20 %s, RSI %s" % (
        last["date"], stats["price"], stats["change_pct"], stats["ma20"], stats["rsi"]))

    page = render_brief_page(date_str, brief, rows, stats)
    print("已生成:", page)
    update_index(date_str, brief, rows, stats)
    print("已更新: index.html")
    png = make_chat_png(date_str, rows)
    print("已生成聊天配图:", png)
    print("STATS_JSON:" + json.dumps(stats))


if __name__ == "__main__":
    main()
