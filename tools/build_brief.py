#!/usr/bin/env python3
"""生成带图表的 AVGO 日报页面并更新首页。

用法:
    python3 build_brief.py 2026-09-19

读取 tools/input/<date>.json（编辑性内容：要点、栏目、来源等），拉取 AVGO 日线数据（Nasdaq 官方历史接口打底，CNBC 实时行情补最新一根 K 线），然后：
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
    # 日线主体：Nasdaq 官方历史行情 API（免 key），返回倒序日线，解析后按日期正序排列。
    # 最新一根 K 线：Nasdaq 历史接口要美东过夜才更新，用 CNBC 实时行情接口补上
    # 当日（上一交易日）OHLCV，保证横幅价格与正文最新收盘一致。CNBC 失败则回退为纯日线。
    url = ("https://api.nasdaq.com/api/quote/AVGO/historical"
           "?assetclass=stocks&fromdate=2024-01-01&limit=9999")
    headers = dict(UA)
    headers["Accept"] = "application/json"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    rows_raw = payload["data"]["tradesTable"]["rows"]

    def num(v):
        if not v or v == "N/A":
            return None
        try:
            return float(str(v).replace("$", "").replace(",", ""))
        except (TypeError, ValueError):
            return None

    rows = []
    for r in rows_raw:
        px = num(r.get("close"))
        if px is None:
            continue
        m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", (r.get("date") or "").strip())
        if not m:
            continue
        vol = num(r.get("volume"))
        rows.append({
            "date": "%s-%s-%s" % (m.group(3), m.group(1), m.group(2)),
            "open": num(r.get("open")), "high": num(r.get("high")),
            "low": num(r.get("low")), "close": px,
            "volume": int(vol) if vol else 0,
        })
    rows.sort(key=lambda r: r["date"])
    if not rows:
        raise RuntimeError("Nasdaq 未返回 AVGO 日线数据")

    # 补最新一根 K 线
    try:
        qurl = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
                "?symbols=AVGO&requestMethod=quick&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
        qreq = urllib.request.Request(qurl, headers=UA)
        with urllib.request.urlopen(qreq, timeout=30) as qresp:
            q = json.loads(qresp.read().decode())["FormattedQuoteResult"]["FormattedQuote"][0]
        qm = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T.*", (q.get("last_time") or "").strip())
        qbar = {
            "date": "%s-%s-%s" % (qm.group(1), qm.group(2), qm.group(3)),
            "open": num(q.get("open")), "high": num(q.get("high")),
            "low": num(q.get("low")), "close": num(q.get("last")),
            "volume": int(num(q.get("volume")) or 0),
        }
        if qm and qbar["close"] and qbar["date"] > rows[-1]["date"]:
            rows.append(qbar)
    except Exception:
        pass
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

    # 编辑性文本（sections/items）同样支持 %%TOKEN%%，均线/价格/RSI 一律由脚本注入，
    # 禁止在 input JSON 里手写这些数字。可用 token：
    # %%PRICE%% %%CHANGE_PCT%% %%MA20%% %%MA50%% %%MA200%% %%RSI%%
    stat_tokens = {
        "%%PRICE%%": stats["price"],
        "%%CHANGE_PCT%%": stats["change_pct"],
        "%%MA20%%": stats["ma20"],
        "%%MA50%%": stats["ma50"],
        "%%MA200%%": stats["ma200"],
        "%%RSI%%": stats["rsi"],
    }

    # 各栏目锚点 id（供顶部导航跳转）
    section_anchors = {
        "📰 行情速览": "market",
        "🏢 基本面": "fundamentals",
        "🎯 分析师评级": "ratings",
        "📊 技术面": "technical",
        "💬 社交平台头条": "social",
        "👀 今日关注": "focus",
    }
    nav_items = []
    sections_html = []
    for sec in brief["sections"]:
        items = []
        for it in sec["items"]:
            for tok, val in stat_tokens.items():
                it = it.replace(tok, val)
            items.append("<li>%s</li>" % it)
        anchor = section_anchors.get(sec["title"], "")
        if anchor:
            nav_items.append('<a href="#%s">%s</a>' % (anchor, sec["title"]))
            sections_html.append(
                '<section class="brief-section" id="%s">\n<h3>%s</h3>\n<ul>\n%s\n</ul>\n</section>'
                % (anchor, sec["title"], "\n".join(items)))
        else:
            sections_html.append(
                '<section class="brief-section">\n<h3>%s</h3>\n<ul>\n%s\n</ul>\n</section>'
                % (sec["title"], "\n".join(items)))
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
        "%%SECTION_NAV%%": ('<nav class="section-nav">\n' + "\n".join(nav_items) + "\n</nav>"
                           if nav_items else ""),
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


def validate_brief(html, stats):
    """发布前数字一致性校验。

    1. 不允许残留未替换的 %%TOKEN%%（token 拼写错误等）。
    2. "均线/MA"附近（前后 30 字符）出现的美元金额，必须精确等于
       MA20/MA50/MA200 其中之一——这是之前手写"$380"代替 $368.59 的翻车点。
       开盘价、区间高低点、支撑阻力等其他数字不强制校验（由编辑负责）。
    返回错误列表，为空表示通过。
    """
    errors = []
    leftover = sorted(set(re.findall(r"%%[A-Z0-9_]+%%", html)))
    if leftover:
        errors.append("残留未替换 token: %s" % ", ".join(leftover))

    ma_vals = {round(float(stats["ma20"]), 2),
               round(float(stats["ma50"]), 2),
               round(float(stats["ma200"]), 2)}
    # 找"均线"或"MAxx"关键词位置
    kw_pos = [m.start() for m in re.finditer(r"均线|MA\s?20|MA\s?50|MA\s?200", html)]
    for m in re.finditer(r"\$(\d{1,4}(?:\.\d{1,2})?)", html):
        val = round(float(m.group(1)), 2)
        if val in ma_vals:
            continue
        # 是否在任一均线关键词附近
        if any(abs(m.start() - kp) < 40 for kp in kw_pos):
            errors.append(
                "均线附近的金额 $%s 与计算值 %s 不一致（疑似手写硬编码）"
                % (m.group(1), "/".join("$%.2f" % v for v in sorted(ma_vals))))
            break

    # RSI：正文若提到具体数值，必须与计算值一致（容差 0.2；70/30 为阈值线除外）
    rsi_val = float(stats["rsi"])
    for m in re.finditer(r"RSI(?:\(14\))?[^\d]{0,12}(\d{1,3}\.\d)", html):
        v = float(m.group(1))
        if abs(v - rsi_val) > 0.2 and v not in (70.0, 30.0):
            errors.append(
                "正文 RSI 数值 %.1f 与脚本计算值 %.1f 不一致" % (v, rsi_val))
    return errors


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
        "sources": ("行情、均线与 RSI 基于 Nasdaq 官方日线与 CNBC 最新行情计算，"
                    "数据截至 %s 美股收盘；" % last["date"]) + brief.get("sources_extra", ""),
    }
    print("最新: %s 收盘 $%s (%s), MA20 %s, RSI %s" % (
        last["date"], stats["price"], stats["change_pct"], stats["ma20"], stats["rsi"]))

    page = render_brief_page(date_str, brief, rows, stats)
    print("已生成:", page)

    with open(page, encoding="utf-8") as f:
        page_html = f.read()
    problems = validate_brief(page_html, stats)
    if problems:
        print("数字一致性校验失败，终止发布：", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        sys.exit(2)
    print("数字一致性校验通过")
    update_index(date_str, brief, rows, stats)
    print("已更新: index.html")
    png = make_chat_png(date_str, rows)
    print("已生成聊天配图:", png)
    print("STATS_JSON:" + json.dumps(stats))


if __name__ == "__main__":
    main()
