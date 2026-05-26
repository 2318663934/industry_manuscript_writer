#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风格注入器 — 从 SKILL.md 提取可迁移的颗粒度元素

只注入句式特征、开篇/结尾策略、语气光谱、反模式，
不注入用词偏好（保持行业稿件的正式感）。
"""

import os
from pathlib import Path
from typing import Optional

# 模块级缓存
_skill_content_cache: Optional[str] = None
_style_injection_cache: Optional[str] = None


def load_skill_md(path: Optional[str] = None) -> str:
    """读取 SKILL.md 原文（带缓存）"""
    global _skill_content_cache
    if _skill_content_cache is not None:
        return _skill_content_cache
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "SKILL.md",
        )
    with open(path, "r", encoding="utf-8") as f:
        _skill_content_cache = f.read()
    return _skill_content_cache


def get_style_injection() -> str:
    """返回风格注入文本（带缓存）"""
    global _style_injection_cache
    if _style_injection_cache is not None:
        return _style_injection_cache

    skill = load_skill_md()

    # 解析 SKILL.md 章节
    sections = _parse_skill_sections(skill)

    opening = sections.get("开篇策略库", "")
    closing = sections.get("结尾策略库", "")
    syntax = sections.get("句式特征", "")
    tone = sections.get("语气光谱", "")
    anti = sections.get("反模式", "")

    # 将 Markdown 表格转为更紧凑的 prose 格式，方便 LLM 理解
    injection = f"""
## 写作风格精细指导

以下指导来自经过 385 篇行业文章蒸馏的写作风格库。请严格遵守。

### 语气要求

行业稿件需要在「正式专业」和「自然可读」之间找到平衡。避免两种极端：
- 不要过于口语化、随意（不像聊天，像在发表见解）
- 不要过于学术化、僵硬（像在说话，不像在读论文）

理想状态是：**像资深从业者在行业会议上跟你边喝咖啡边分析问题**——有观点、有数据、有人味。

{tone}

---

### 句式和节奏

{syntax}

核心原则：
- 长短句结合，制造阅读节奏
- 主动句为主，减少被动语态
- 一段话不要以相同的词开头
- 段落之间要有逻辑咬合，不要像拼贴的

---

### 开篇策略（9选1，随机化，不要每次用同一种）

{opening}

关键：开头必须有「钩子」——不管是数据、场景、反直觉判断还是细节，必须在 3 秒内抓住读者。**严禁以「随着……」「近年来……」「在当今时代……」开头。**

---

### 结尾策略（7选1，随机化）

{closing}

关键：结尾不要强行升华、不要喊口号、不要用「综上所述」、不要回到大道理上。好的结尾是「上一个段落自然的终点」。

---

### 禁止的写法和语言

{anti}

额外强调以下 AI 套话，**绝对不能出现**：
- 「随着时代的发展」「近年来」「众所周知」「毋庸置疑」
- 「技术革命」「行业突破」「重磅发布」「战略布局」
- 「我们应该……」「企业必须……」「必须指出的是……」
- 「总而言之」「综上所述」「毋庸置疑的是」
- 「小编」「笔者」「让我们……」
"""
    _style_injection_cache = injection
    return injection


def _parse_skill_sections(content: str) -> dict:
    """解析 SKILL.md 中的关键章节"""
    sections = {}
    current_section = None
    current_lines = []

    target_headers = {
        "### 语气光谱": "语气光谱",
        "### 开篇策略库": "开篇策略库",
        "### 结尾策略库": "结尾策略库",
        "### 句式特征": "句式特征",
        "## 🚫 反模式": "反模式",
    }

    for line in content.split("\n"):
        # 检查是否进入目标章节
        matched = None
        for header, name in target_headers.items():
            if line.strip().startswith(header):
                matched = name
                break

        if matched:
            if current_section and current_lines:
                sections[current_section] = "\n".join(current_lines)
            current_section = matched
            current_lines = []
            continue

        # 遇到新的一级/二级标题时退出当前章节
        if current_section and (line.startswith("## ") or line.startswith("# ")):
            # 但不要被 ### 子标题打断
            if not line.startswith("### "):
                sections[current_section] = "\n".join(current_lines)
                current_section = None
                current_lines = []
                continue

        if current_section:
            current_lines.append(line)

    # 最后一个 section
    if current_section and current_lines:
        sections[current_section] = "\n".join(current_lines)

    return sections
