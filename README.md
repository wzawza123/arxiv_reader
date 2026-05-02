# arXiv Daily Reader

每天自动拉取 arXiv 新论文，用 LLM (NVIDIA NIM) 翻译摘要 / 自动打 tag / 阅读总结，用 Docling 提取论文 figure；前端按 **未分类 / 待阅读 / 已读 / 不感兴趣** 四态分流，单机本地小工具。

---

## 目录

- [核心流水线](#核心流水线)
- [项目结构](#项目结构)
- [安装](#安装)
- [配置](#配置)
- [启动](#启动)
- [使用流程](#使用流程)
- [API](#api)
- [失败排查](#失败排查)
- [范围外](#范围外)

---

## 核心流水线

```
APScheduler (daily cron)            Frontend "Mark To Read"
        │                                    │
        ▼                                    ▼
arxiv_fetch.fetch_subscriptions     enqueue_heavy_for_to_read
        │                                    │
        ▼                                    ▼
   new Paper rows  ──────────────►   summarize  +  extract_figures
   (status=new)                       (PDF + 3 次 LLM 问答)   (PDF + Docling)
        │
        ▼
enqueue_light_for_new_paper
        │
        ▼
  translate (摘要中译)  +  auto_tag (LLM 自动维护 tag 库)
```

- **拉取**（自动 / 手动）：仅做轻量处理 — 摘要中文翻译 + LLM 自动打 tag。
- **被人工标记为「待阅读」** 之后才进重处理 — 基于 PDF 正文依次执行 3 次 LLM 问答，生成三段中文阅读总结 + Docling figure 提取。
- 翻译 / tag / 总结 / figure 任务都持久化到 `jobs` 表；进程重启会自动把 `running` 重置为 `pending` 后重新入队。

阅读总结由 LLM 按以下三段依次询问并输出：
1. **这篇论文尝试解决什么问题** — 每个问题后用 `→` 给出本文的结论 / 方法。
2. **关键 Insight 表** — markdown 表格，列：主题 / 内容 / 出处段落。
3. **后续工作头脑风暴** — 3-5 条可执行 follow-up，每条含现状、方案、风险。

---

## 项目结构

```
arxiv_read/
├── backend/                          FastAPI + SQLite + APScheduler
│   ├── app/
│   │   ├── main.py                   入口（lifespan 启 worker / scheduler / 重新入队）
│   │   ├── config.py                 pydantic-settings
│   │   ├── db.py                     SQLAlchemy session
│   │   ├── models.py                 Paper / Tag / Subscription / Figure / Job
│   │   ├── schemas.py                Pydantic v2
│   │   ├── routers/                  papers / subscriptions / tags / jobs
│   │   ├── services/                 nvidia_llm / arxiv_fetch / translator / tagger / summarizer / figure_extractor
│   │   ├── workers/                  queue (asyncio) + scheduler (APScheduler)
│   │   └── prompts/                  translate / tag / summarize 模板
│   ├── data/                         SQLite + PDFs + figures（git 忽略）
│   ├── requirements.txt
│   └── .env.example
└── frontend/                         React 18 + Vite 5 + TypeScript + Tailwind
    └── src/
        ├── api/client.ts             axios 客户端 + 全部类型
        ├── components/               PaperCard / MarkdownView / TagBadge
        └── pages/                    Inbox / ToRead / Read / NotInterested / PaperDetail / Settings / Jobs
```

---

## 安装

环境：conda 环境 `agent`（路径 `/opt/data/private/envs/agent`，由 mamba 管理），Node 18+。

```bash
# Backend Python deps
/opt/data/private/envs/agent/bin/pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

---

## 配置

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env
```

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `NVIDIA_API_KEY` | — | **必填**，NVIDIA NIM API Key |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | OpenAI-compatible base URL |
| `LLM_MODEL` | `meta/llama-3.3-70b-instruct` | NIM 上的模型名 |
| `LLM_TEMPERATURE` | `0.2` | |
| `LLM_MAX_TOKENS` | `4096` | |
| `DB_PATH` | `./data/arxiv.db` | SQLite 路径（相对 backend/） |
| `DATA_DIR` | `./data` | PDF / figure 根目录 |
| `FETCH_CRON_HOUR` / `_MINUTE` | `9` / `0` | 每日拉取时间（服务器本地时区） |
| `WORKER_CONCURRENCY` | `2` | 后台 worker 数量 |
| `SUMMARY_PDF_MAX_CHARS` | `60000` | LLM 总结时从 PDF 正文抽取的最大字符数 |
| `FETCH_MAX_RESULTS_PER_QUERY` | `50` | 每个订阅最多拉多少条 |
| `FETCH_LOOKBACK_DAYS` | `2` | 仅保留近 N 天发表的论文；作为设置页未配置时的默认值 |
| `FETCH_CATEGORY_PREFIX` | `cs.` | 默认只保留该 arXiv 大类下的论文；`cs.` 表示 Computer Science |

---

## 启动

```bash
# 1) 后端
cd backend
/opt/data/private/envs/agent/bin/uvicorn app.main:app --reload --port 8000
```

冒烟检查：

```bash
curl http://127.0.0.1:8000/api/health
# {"ok":true,"model":"meta/llama-3.3-70b-instruct"}
```

```bash
# 2) 前端
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5173`。Vite 自动把 `/api` 与 `/figures` 代理到 `127.0.0.1:8000`，无需 CORS。

生产构建：`npm run build` → `frontend/dist/`，可由 nginx / 任何静态服务器托管。

---

## 使用流程

1. **设置** 页：添加订阅，例如：
   - `category = cs.CV`
   - `category = cs.LG`
   - `keyword = diffusion model`
   关键词订阅默认会限制在 `FETCH_CATEGORY_PREFIX=cs.` 对应的 Computer Science 大类下。
2. **任务** 页：点 “Fetch Now” 立即触发一次拉取（约 30s），或等每日 cron。
3. **Inbox** 浏览新论文：自动出现中文摘要 + 自动 tag chips。
4. 对感兴趣的点 **待阅读** → 后台立即跑基于 PDF 正文的 3 次 LLM 总结问答 + Docling figure 提取。
5. **待阅读 → 论文详情**：左侧 markdown 三段总结，右侧 figure 缩略图。
6. 看完打 **已读** / 失去兴趣打 **不感兴趣** 归档。

---

## API

| Method | Path | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/papers?status=&tag=&q=&page=&page_size=` | 论文列表（按 status/tag/搜索词过滤） |
| `GET` | `/api/papers/{id}` | 论文详情（含 figure / 三段 md） |
| `PATCH` | `/api/papers/{id}` | 改 `status` 或 `tag_ids`；`status` 切到 `to_read` 自动入重处理队列 |
| `POST` | `/api/papers/{id}/reprocess?stage=translate\|tag\|summary\|figures` | 手动重跑某一阶段 |
| `GET` | `/api/papers/stats/counts` | 各 status 计数（首页 nav 角标） |
| `GET` `POST` | `/api/subscriptions` | 订阅列表 / 新建 |
| `PATCH` `DELETE` | `/api/subscriptions/{id}` | 修改 / 删除 |
| `GET` `PATCH` | `/api/settings/fetch` | 查看 / 修改拉取窗口天数 |
| `GET` | `/api/tags` | tag 库 + 每个 tag 的论文数 |
| `PATCH` `DELETE` | `/api/tags/{id}` | 重命名 / 删除（级联清 PaperTag） |
| `GET` | `/api/jobs?status=&limit=` | 后台任务列表（前端任务页 5s 轮询） |
| `POST` | `/api/jobs/fetch` | 立即拉取（同步，会阻塞 ~30s） |
| `GET` | `/figures/{rel_path}` | 提取后的 figure（StaticFiles） |

cURL 示例：

```bash
# 加一个分类订阅
curl -X POST http://127.0.0.1:8000/api/subscriptions \
  -H 'content-type: application/json' \
  -d '{"kind":"category","value":"cs.CV","enabled":true}'

# 立刻拉一次
curl -X POST http://127.0.0.1:8000/api/jobs/fetch

# 标记 paper_id=42 为待阅读（自动入重处理队列）
curl -X PATCH http://127.0.0.1:8000/api/papers/42 \
  -H 'content-type: application/json' \
  -d '{"status":"to_read"}'
```

---

## 失败排查

- **翻译 / 自动 tag / 总结 失败**：去 **任务** 页查看 `failed` 行的 `error` 列。最常见是 `NVIDIA_API_KEY` 未配 / 速率限制 / 模型名拼错。可在论文详情页点 “重跑：xxx”。
- **figure 提取失败**：通常是 PDF 下载超时或 Docling 解析失败。可在详情页点 “重跑：Figures”。
- **Docling 首次启动较慢**：会在线下载 layout / OCR 模型权重，首次跑 figure 提取会需要一两分钟。
- **fetch 没拉到论文**：检查订阅是否 `enabled`、`FETCH_LOOKBACK_DAYS` 是否过短、arxiv 是否对你的网络可达。
- **进程崩溃 / kill -9**：`pending` 与 `running` 任务在下次 `uvicorn` 启动时会自动重新入队。

---

## 范围外

- 多用户 / 鉴权
- 全文翻译（当前仅摘要 + LLM 三段总结）
- 向量检索 / RAG
- Docker 化与远程部署
