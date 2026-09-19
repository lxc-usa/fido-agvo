# AVGO 每日追踪

每日更新的 Broadcom (NASDAQ: AVGO) 中文投资资讯站。
纯静态网站，零依赖、无构建工具，可直接用 GitHub Pages 托管。

## 文件结构

```
avgo-site/
├── index.html # 首页：站点头部、最新一期简报、历史归档列表
├── styles.css # 全站样式（深色金融风格、响应式）
├── script.js # 原生 JS：归档按日期筛选
├── briefs/
│ └── 2026-09-19.html # 每日简报页模板（含样例日报）
└── README.md # 本文件
```

## 如何新增一篇日报

假设今天要发布 2026-09-20 的日报：

1. **复制模板文件**
```bash
cp briefs/2026-09-19.html briefs/2026-09-20.html
```

2. **编辑新文件**（`briefs/2026-09-20.html`）：
- 修改 `<title>` 和 hero 区的简报日期、数据截止时间；
- 更新价格、均线、RSI 等数字；
- 按六个栏目填写内容；
- 更新底部的"数据来源与时间"标注；
- "不构成投资建议"声明已内置，无需改动。

3. **更新首页**（`index.html`）：
- 在 `<!-- ═══ 最新一期... ═══ -->` 区块内，把日期标签、价格、涨跌幅、要点列表和"阅读完整日报"链接换成新一期的；
- 在 `<!-- ═══ 归档列表... ═══ -->` 注释下方、现有卡片**上方**添加一条新卡片：
```html
<a class="archive-card" href="briefs/2026-09-20.html" data-date="2026-09-20">
<span class="archive-date">2026-09-20</span>
<span class="archive-title">一句话摘要（收盘价/涨跌幅/当日最大看点）</span>
<span class="archive-arrow">→</span>
</a>
```
- 注意 `data-date` 必须与文件名日期一致，否则日期筛选会失效。

4. 提交并推送，GitHub Pages 会自动重新部署。

## 本地预览

```bash
cd ~/workspace/avgo-site
python3 -m http.server 8000
# 浏览器打开 http://localhost:8000
```

也可以直接用浏览器打开 `index.html` 文件（`file://` 协议下页面可正常显示；
归档日期筛选功能同样可用）。

## 部署到 GitHub Pages

1. 在 GitHub 新建仓库（例如 `avgo-daily`），把本目录所有文件推到 `main` 分支根目录；
2. 仓库 Settings → Pages → Source 选择 "Deploy from a branch"，分支选 `main`、目录选 `/ (root)`；
3. 保存后等待 1–2 分钟，即可通过 `https://<用户名>.github.io/<仓库名>/` 访问。

## 约定

- 所有数据必须注明来源与时间；无法验证的内容标注"未确认"，不编造。
- 每篇简报页底部保留"数据来源与时间"标注和"不构成投资建议"声明。
- 不要在仓库中存放任何密钥、账号密码或个人信息。
