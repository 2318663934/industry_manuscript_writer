# Industry Manuscript Writer — RAG+SkillAgent 智能写作平台

基于 RAG（检索增强生成）+ SkillAgent（策略智能体）的行业稿件智能写作系统。支持从多源爬虫采集、Milvus 向量检索、策略案例匹配到高质量文章生成的全流程自动化。

## 架构概览

```
┌──────────────────────────────────────────────────────┐
│                    Web 服务层                          │
│   port 5000: 5 步向导（头脑风暴→蓝图→大纲→写作）        │
│   port 5004: SKILL.md 轻量写作（单页直出）              │
│   反馈协同入库 UI: blueprint/outline 反馈区 "📌 标记" 按钮 │
└──────────┬──────────────────────┬────────────────────┘
           │                      │
┌──────────▼──────────┐  ┌───────▼────────────────────┐
│   SkillAgent         │  │   StyleInjector             │
│   策略导师/架构师      │  │   风格注入器                  │
│   · 案例检索(Few-shot)│  │   · SKILL.md 颗粒度提取       │
│   · JSON 蓝图生成     │  │   · 句式/开篇/结尾/反模式注入   │
│   · Self-Reflection  │  │   · 双风格融合                 │
└──────────┬──────────┘  └───────┬────────────────────┘
           │                      │
┌──────────▼──────────────────────▼────────────────────┐
│   混合检索层 (Hybrid Retrieval)  ⭐ 2026-06 新增          │
│   ┌─────────────────────────┐  ┌──────────────────┐  │
│   │ WikiProductBackend       │  │  Milvus RAG       │  │
│   │ (调本机 LLM-Wiki 知识库)  │  │  (产品分析报告 433 篇)│  │
│   │ · HTTP 调本机 :8088      │──▶  fallback / hybrid│  │
│   │ · 精确路径快查 0.5s      │  │  (LAN 局域网部署)  │  │
│   │ · 6 产品结构化数据 4353md│  └──────────────────┘  │
│   └─────────────────────────┘                          │
│   知识库模式: rag / wiki / hybrid (默认)               │
└──────────┬───────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────┐
│   用户反馈协同入库 ⭐ 2026-06 新增                        │
│   · FeedbackCapture: LLM 实时识别 7 种反馈类型          │
│   · 事实类 → 走 ingest 管道 (写 wiki / 99-待审)         │
│   · 偏好类 → 写 state/feedback_log.jsonl                │
│   · 端点: /api/feedback/{capture,confirm,list}         │
└──────────┬───────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────┐
│                   RAG 检索层                           │
│   · Milvus 向量检索 (120+ 行业文章)                     │
│   · BM25 全文检索                                       │
│   · Hybrid 混合检索                                     │
│   · 补充资料加载 (TXT/DOCX/PDF/Excel/微信链接)           │
└──────────┬───────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────┐
│                   数据采集层                            │
│   · 触乐(chuapp) / 知乎 / 搜狗 / GameLook 多源爬虫      │
│   · HTML→JSON 结构化解析                                │
│   · 自动向量化存入 Milvus                                │
└──────────────────────────────────────────────────────┘

外部依赖:
┌──────────────────────────────────────────────────────┐
│  本机 (LAN) Wiki API Server (端口 8088)                │
│  · 复用 deepsearch 项目 wiki/ 知识库 (4353 md)          │
│  · Bearer token 鉴权 + 60 req/min/IP 限速              │
│  · 精确路径快查 EXACT_PATH_RULES, 命中率 70%+           │
│  · 配套: e:/评论写手 / e:/行业稿件写作 共享              │
└──────────────────────────────────────────────────────┘
```

## 核心模块

| 模块 | 路径 | 说明 |
|------|------|------|
| **rag_writer** | `rag_writer/` | RAG 写作引擎核心 |
| **spider** | `spider/` | 行业文章爬虫集群 |
| **skill_agent** | `rag_writer/skill_agent/` | 写作策略智能体 |
| **strategy_cases** | `strategy_cases/` | 策略案例库（100+ 篇标注） |
| **milvus** | `milvus/` | Milvus Docker 部署配置 |

## 快速开始

### 1. 环境要求

- Python 3.10+
- Docker（运行 Milvus 向量数据库）
- Git

### 2. 安装依赖

```bash
# 克隆仓库
git clone git@github.com:xiaobaiaigroup/industry_manuscript_writer.git
cd industry_manuscript_writer

# 安装 RAG 写作系统依赖
pip install -r rag_writer/requirements.txt

# 安装爬虫依赖（可选）
pip install -r spider/requirements.txt
```

### 3. 启动 Milvus

```bash
cd milvus
docker-compose up -d
```

### 4. 配置环境变量

```bash
cp rag_writer/.env.example rag_writer/.env
# 编辑 .env 文件，填入 LLM API Key 等配置
```

主要配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM__PROVIDER` | LLM 提供商 | `openai`（兼容协议） |
| `LLM__MODEL` | 模型名称 | `deepseek-v4-pro` |
| `LLM__API_KEY` | API 密钥 | 从环境变量读取 |
| `LLM__BASE_URL` | API 端点 | `https://api.deepseek.com` |
| `MILVUS__HOST` | Milvus 地址 | `localhost` |
| `MILVUS__PORT` | Milvus 端口 | `19530` |

### 5. 启动服务

```bash
# 启动主 RAG 写作服务 (port 5000)
python rag_writer/start_server.py

# 启动 SKILL.md 轻量写作服务 (port 5004)
python rag_writer/start_skill_server.py
```

浏览器访问：
- **http://localhost:5000** — 5 步向导完整流程
- **http://localhost:5004** — SKILL.md 风格单页写作

## 使用流程

### 完整 5 步向导 (port 5000)

```
Step 1: 填写任务 → 输入话题、要求、关键词、补充资料
  ├─ "进行头脑风暴" → Step 2
  └─ "直接生成策略蓝图" → Step 3（跳过头脑风暴）

Step 2: 头脑风暴 → AI 多角度发散，用户选择切入角度

Step 3: 策略蓝图审核 → 审阅/修改/回退 JSON 策略蓝图

Step 4: 大纲审核 → 审阅/修改文章大纲

Step 5: 生成文章 → 基于大纲+RAG素材输出完整文章
```

### 轻量写作 (port 5004)

```
填写表单 → 选择稿件类型 → 可选补充资料 → 一键出文章
```

使用 SKILL.md 风格库（祝佳音 278 篇 + 托马斯之颅 107 篇蒸馏）直接约束 LLM 写作风格。

## SKILL.md 写作风格库

`SKILL.md` 是基于两位职业游戏行业作者（触乐祝佳音 278 篇、知乎托马斯之颅 107 篇）写作风格蒸馏的风格指令集，包含：

- **9 种结构模板**（纵深分析/暴论开篇/虚构叙事/体验笔记/荒诞批判/考据深挖/历史回顾/对话访谈/快评段子）
- **9 种开篇策略** + **7 种结尾策略**
- **双视角写作 DNA**（用词偏好、句式特征、心智模型）
- **反模式/通用禁忌**（杜绝 AI 套话）

SKILL.md 通过 `style_injector.py` 已将句式、开篇/结尾策略、语气光谱、反模式注入到 RAG 系统的所有 prompt 构建点。

## 支持的 LLM

| 提供商 | 标识 | 说明 |
|--------|------|------|
| DeepSeek | `openai` (兼容) | 默认，base_url 指向 api.deepseek.com |
| OpenAI | `openai` | 原生 API |
| Claude | `claude` | Anthropic 原生 SDK |
| 硅基流动 | `siliconflow` | 国产模型聚合 |
| 智谱 | `zhipu` | GLM 系列 |
| MiniMax | `minimax` | MiniMax-M2 系列 |

在 `.env` 中修改 `LLM__PROVIDER` 和 `LLM__BASE_URL` 即可切换。

## 混合检索: LLM-Wiki + Milvus RAG (2026-06 新增)

行业稿件写作系统在头脑风暴阶段需要紧贴产品信息 (6 个游戏产品的结构化数据), 既保留原 Milvus 产品信息库作为兜底, 又支持切换到本机 LLM-Wiki 知识库 (基于 `e:/deepsearch/wiki/`, 4353 个 md, 6 产品)。

### 3 种模式

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| `rag` | 纯 Milvus (原行为) | 服务器无 Wiki API 访问能力 |
| `wiki` | 纯 LLM-Wiki (强制本机) | 数据迁移期, 验证 Wiki 覆盖度 |
| `hybrid` (默认) | Wiki 优先, 失败/空降级 RAG | **推荐**, 兼顾速度与可靠性 |

### 配置

```bash
# 复制模板
cp rag_writer/.env.wiki.template rag_writer/.env

# 编辑 .env 关键项:
WIKI_API_URL=http://192.168.x.x:8088       # 本机 IP
WIKI_API_KEY=deepsearch123
WIKI__KNOWLEDGE_MODE=hybrid                # rag / wiki / hybrid
WIKI__TIMEOUT_SEC=60
```

### 启动本机 Wiki API Server

```bash
# 在 e:/deepsearch 目录 (本机):
python wiki_api_server.py --host 0.0.0.0 --port 8088 --api-key deepsearch123
```

### 接口 (drop-in 替代 `ProductKnowledgeBase`)

```python
# 原 RAG 模式:
from product_retriever import ProductKnowledgeBase
kb = ProductKnowledgeBase()
results = kb.search("李白 1 技能", product="honor_of_kings", top_k=5)

# 新 Wiki 模式 (无需 import 改):
from rag_writer.wiki_product_backend import WikiProductBackend
backend = WikiProductBackend()
results = backend.search("李白 1 技能", product="honor_of_kings", top_k=5)
# 两种接口完全一致: search(query, product, top_k) -> List[Dict]
# 返回字段: product / product_display / id / title / url / source / date
#         / content_text / content_length / distance
```

### 端点: `/api/brainstorm` 改造

- 接收 `user_feedback` (用户反馈) 和 `brainstorm_history` (多轮历史)
- 调 hybrid 检索, 返回 `product_context` 字符串
- 自动调 `/api/feedback/capture` 检测本轮反馈是否有入库价值, 附 `feedback_preview` 给前端

### 性能

| 查询 | Wiki 命中 | 耗时 |
|------|---------|-----:|
| 洛克 星光对决 | 3 条 | 0.55s ⚡ |
| 王者世界 东方曜 | 3 条 | 0.46s ⚡ |
| 王者 李白 (Wiki 空) | RAG 兜底 3 条 | 1.2s |

精确路径快查命中率 70%+, 命中时跳过 ReAct < 0.01s 返回。

## 用户反馈协同入库 (2026-06 新增)

由于稿件写作系统涉及大量用户交互 (头脑风暴多轮 / 蓝图审核 / 大纲反馈), 用户对产品事实的纠正、对写作风格的偏好、对选题方向的调整, 都可被 LLM 实时识别, 经用户确认后入库 (走 ingest 管道) 或写日志。

### 反馈类型 (7 种)

| Type | 目标 | 示例 |
|------|------|------|
| `fact_correction` | wiki | "李白 1 技能是 8 秒, 不是 12 秒" |
| `fact_supplement` | wiki | "李白还有彩蛋台词'将进酒, 杯莫停'" |
| `fact_contradiction_flag` | wiki (高优) | "这段完全错了, 李白根本不是 X" |
| `style_preference` | log | "下次写作更口语化一点" |
| `topic_pivot` | log | "换个角度, 聊 MMORPG 经济系统" |
| `quality_rating` | log | "5 分, 但开头太长" |
| `none` | (忽略) | "好的, 继续" / "看下个角度" |

### 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/feedback/capture` | POST | LLM 实时识别用户消息, 返回 preview |
| `/api/feedback/confirm` | POST | 用户确认入库: 走 ingest 或写 log |
| `/api/feedback/list` | GET | 调试: 看 preview + log |

### UI 触发点

| 位置 | 按钮 | 阶段 |
|------|------|------|
| `blueprintFeedbackInput` 旁 | 📌 标记为反馈 (入库 wiki) | Step 2 蓝图审核 |
| `feedbackInput` 旁 | 同上 | Step 3 大纲审核 |
| `/api/brainstorm` 自动 | response 附 `feedback_preview` | 头脑风暴阶段 |

### 入库流程

```
用户输入反馈 (textarea)
    ↓ 点 "📌 标记为反馈" 按钮
    ↓ JS: fetch('/api/feedback/capture')
    ↓ LLM (本地 Qwen) 0.5s 识别
    ↓ 显示 badge: "事实纠正 · conf=0.95 · 目标: ingest → wiki"
    ↓ 弹 Modal, 显示候选 facts (可编辑 JSON)
    ↓ 用户点 "✅ 确认入库"
    ↓ fetch('/api/feedback/confirm') → ingest_one()
    ├─ 事实类: 走 ingest 管道 (合成 raw/ + LLM 抽 + 置信度门控)
    │         ├─ ≥0.7 → 直接入 wiki 主版
    │         ├─ 冲突 → 入 99-待审 (符合 CLAUDE.md §6)
    │         └─ 0.4-0.7 → 入 99-待审
    └─ 偏好类: 写 state/feedback_log.jsonl
```

### 端到端验证结果

| 场景 | LLM 识别 | 实际入库 |
|------|---------|---------|
| "李白 1 技能是 8 秒, 不是 12 秒" | fact_correction, conf=0.92 | `wiki/honor_of_kings/20-英雄/李白.md` (走 ingest) |
| "下次写作更口语化, 短句多" | style_preference, conf=0.95 | `feedback_log.jsonl` 第 1 行 |
| "好的, 继续" | none, conf=1.0 | 不入库 (正确) |
| "换个角度, 聊 MMORPG 经济" | topic_pivot, conf=0.95 | `feedback_log.jsonl` 第 2 行 |
| "李白 1 技能冷却 8 秒, 你说错了" (含主版) | fact_correction | 冲突门控 → `99-待审/李白-append-...md` |

## 爬虫模块

支持多源行业文章采集：

| 爬虫 | 文件 | 数据源 |
|------|------|--------|
| 触乐 | `spider/chuapp_spider.py` | 祝佳音 278 篇文章 |
| 知乎 | `spider/zhihu_spider.py` | 托马斯之颅 107 篇回答/专栏 |
| 搜狗 | `spider/sougou_*.py` | 微信公众号文章搜索 |
| GameLook | `spider/gamelook_spider.py` | 游戏行业媒体 |

采集数据自动存入 `spider/data/`，可通过 `spider/vectorize_to_milvus.py` 向量化入 Milvus。

## 项目结构

```
industry_manuscript_writer/
├── README.md
├── SKILL.md                    # 双视角蒸馏写作风格库
├── start.bat / stop.bat        # 服务启停脚本
├── rag_writer/                 # RAG 写作引擎
│   ├── engine.py               # 核心引擎（RAGWriter）
│   ├── retriever.py            # Milvus/文本/混合检索
│   ├── prompt_engineering.py   # 提示词工程（含 DeepBrief）
│   ├── style_injector.py       # SKILL.md 风格注入器
│   ├── skill_prompt.py         # SKILL.md 完整 prompt 构建
│   ├── llm_client.py           # 多 LLM 客户端
│   ├── supplementary_loader.py # 补充资料加载器
│   ├── config.py               # 系统配置 (含 WikiConfig)
│   ├── web_demo.py             # 主 Web 服务 (port 5000, 含 /api/feedback/* 3 端点)
│   ├── skill_web.py            # SKILL 写作服务 (port 5004)
│   ├── start_server.py         # 主服务启动脚本
│   ├── start_skill_server.py   # SKILL 服务启动脚本
│   ├── wiki_product_backend.py # ⭐ Wiki drop-in 后端 (替代 ProductKnowledgeBase)
│   ├── feedback_capture.py     # ⭐ 用户反馈捕获 + LLM 提取 + ingest 协同入库
│   ├── .env.wiki.template      # ⭐ Wiki 配置模板
│   ├── skill_agent/            # 策略智能体
│   │   ├── agent.py            # SkillAgent 主类
│   │   ├── compiler.py         # 蓝图→写作指令编译器
│   │   ├── prompts.py          # Skill 提示词
│   │   ├── case_base.py        # 策略案例库管理
│   │   ├── retriever.py        # 案例检索
│   │   ├── models.py           # 数据模型（Blueprint等）
│   │   └── reflection.py       # Self-Reflection 校验
│   ├── templates/
│   │   └── index.html          # 5 步向导前端 (含反馈协同入库 UI)
│   └── examples/               # 使用示例
├── state/                      # 运行时状态 (部分入 git, 部分 .gitignore)
│   ├── feedback_log.jsonl      # ⭐ 用户反馈偏好日志 (累计, 不入 git)
│   └── feedback_preview_cache.json # ⭐ preview 缓存 (不入 git)
├── spider/                     # 爬虫集群
│   ├── main.py                 # 爬虫入口
│   ├── config.py               # 爬虫配置
│   ├── storage.py              # 数据存储
│   ├── vectorize_to_milvus.py  # 向量化入库
│   └── data/                   # 采集数据
├── strategy_cases/             # 策略案例库
│   └── annotations/            # 100+ 篇标注框架
└── milvus/
    └── docker-compose.yml      # Milvus 部署
```

## 命令行使用

```bash
# 一键写作
python -m rag_writer.cli "你的话题" --top-k 5 --show-sources

# 从文件写作
python -m rag_writer.cli "requirement.docx" --file

# 流式输出
python -m rag_writer.cli "你的话题" --stream
```

## License

Internal Use
