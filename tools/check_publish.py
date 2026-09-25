#!/usr/bin/env python3
"""发布后主备站健康检查。

用法:
    python3 check_publish.py 2026-09-25

依次检查 Cloudflare Pages（主）与 GitHub Pages 经自定义域名的备份站：
  1. briefs/<date>.html 在两站都返回 200
  2. 两站关键内容一致（顶部价格/均线/RSI 统计区提取对比）
  3. 考虑 CDN 同步延迟，最多轮询约 10 分钟；超时或不一致则 exit 1
"""
import re
import sys
import time
import urllib.request

SITES = {
    "cloudflare": "https://avgo.pages.dev/briefs/%s.html",
    "github": "https://avgo.lxc.one/briefs/%s.html",
}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
TIMEOUT = 30
DEADLINE_S = 600
POLL_S = 45


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def key_stats(html):
    """提取顶部统计区的关键数字，用于主备站一致性对比。"""
    stats = {}
    for label, pat in (
        ("price", r'<div class="price num">\$([\d.]+)</div>'),
        ("ma20", r'20 日均线</div><div class="value num neutral">\$([\d.]+)</div>'),
        ("ma50", r'50 日均线</div><div class="value num neutral">\$([\d.]+)</div>'),
        ("ma200", r'200 日均线</div><div class="value num neutral">\$([\d.]+)</div>'),
        ("rsi", r'RSI\(14\)</div><div class="value num neutral">([\d.]+)</div>'),
    ):
        m = re.search(pat, html)
        stats[label] = m.group(1) if m else None
    return stats


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", sys.argv[1]):
        print("用法: python3 check_publish.py YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)
    date_str = sys.argv[1]

    pages = {}
    deadline = time.time() + DEADLINE_S
    while time.time() < deadline:
        ok = True
        for name, tmpl in SITES.items():
            if name in pages:
                continue
            url = tmpl % date_str
            try:
                status, html = fetch(url)
            except Exception as e:
                print("[%s] 拉取失败: %s，重试…" % (name, e))
                ok = False
                continue
            if status != 200 or len(html) < 5000:
                print("[%s] HTTP %s / 内容过短，重试…" % (name, status))
                ok = False
                continue
            pages[name] = html
            print("[%s] 200 OK (%d 字节)" % (name, len(html)))
        if ok and len(pages) == len(SITES):
            break
        time.sleep(POLL_S)

    if len(pages) != len(SITES):
        missing = [n for n in SITES if n not in pages]
        print("FAIL: 以下站点超时未就绪: %s" % ", ".join(missing), file=sys.stderr)
        sys.exit(1)

    s_cf, s_gh = key_stats(pages["cloudflare"]), key_stats(pages["github"])
    print("cloudflare:", s_cf)
    print("github:    ", s_gh)
    diffs = [k for k in s_cf if s_cf[k] != s_gh[k]]
    if diffs:
        print("FAIL: 主备站关键数字不一致: %s" % ", ".join(diffs), file=sys.stderr)
        sys.exit(1)
    if any(v is None for v in s_cf.values()):
        print("FAIL: 未能从页面提取完整统计数字", file=sys.stderr)
        sys.exit(1)
    print("OK: 主备站均可访问且关键数字一致")


if __name__ == "__main__":
    main()
