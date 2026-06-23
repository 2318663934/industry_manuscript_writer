# Industry Manuscript Writer — RAG+SkillAgent 智能写作平台

基于 RAG（检索增强生成）+ SkillAgent（策略智能体）的行业稿件智能写作系统。支持从多源爬虫采集、Milvus 向量检索、策略案例匹配到高质量文章生成的全流程自动化。

## 架构概览

```
┌──────────────────────────────────────────────────────┐
│                    Web 服务层                          │
│   port 5000: 5 步向导（头脑风暴→蓝图→大纲→写作）        │
│   port 5004: SKILL.md 轻量写作（单页直出）              │
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
│   ├── config.py               # 系统配置
│   ├── web_demo.py             # 主 Web 服务 (port 5000)
│   ├── skill_web.py            # SKILL 写作服务 (port 5004)
│   ├── start_server.py         # 主服务启动脚本
│   ├── start_skill_server.py   # SKILL 服务启动脚本
│   ├── skill_agent/            # 策略智能体
│   │   ├── agent.py            # SkillAgent 主类
│   │   ├── compiler.py         # 蓝图→写作指令编译器
│   │   ├── prompts.py          # Skill 提示词
│   │   ├── case_base.py        # 策略案例库管理
│   │   ├── retriever.py        # 案例检索
│   │   ├── models.py           # 数据模型（Blueprint等）
│   │   └── reflection.py       # Self-Reflection 校验
│   ├── templates/
│   │   └── index.html          # 5 步向导前端
│   └── examples/               # 使用示例
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
