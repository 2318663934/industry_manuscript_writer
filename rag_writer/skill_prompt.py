#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SKILL.md 提示词构建器

将 SKILL.md 写作风格库注入 system prompt，让 LLM 直接
按照祝佳音/托马斯之颅双视角蒸馏的风格进行写作。
"""

import os
from pathlib import Path
from typing import Optional, Dict, List

from .prompt_engineering import KnowledgeContext, WritingTask, PromptBuilder


def load_skill_md(path: Optional[str] = None) -> str:
    """读取 SKILL.md 原文"""
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "SKILL.md",
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# 稿件类型→风格/模板推荐映射
TYPE_RECOMMENDATIONS = {
    "行业趋势":  {"style": "托马斯之颅", "templates": "B/G", "openings": "1/4/8", "endings": "3/4", "tone": "冷峻理性 + 数据驱动"},
    "财报分析":  {"style": "托马斯之颅", "templates": "B/G", "openings": "1/4",   "endings": "3/4", "tone": "数据对比 + 周期视角"},
    "深度人物":  {"style": "祝佳音",     "templates": "H/A", "openings": "3/5/6", "endings": "1/5", "tone": "人文关怀 + 故事驱动"},
    "热点评论":  {"style": "混合",       "templates": "B/I", "openings": "1/2/9", "endings": "2/7", "tone": "暴论开场 + 幽默收尾"},
    "游戏评测":  {"style": "祝佳音",     "templates": "D/A", "openings": "2/5/6", "endings": "1/5/6","tone": "体验驱动 + 夹叙夹议"},
    "从业者职场":{"style": "托马斯之颅", "templates": "C",   "openings": "7/8",   "endings": "3/4", "tone": "虚构叙事 + 多可能性"},
    "文化评论":  {"style": "祝佳音",     "templates": "F/E", "openings": "3/5/6", "endings": "1/2/5","tone": "考据癖 + 幽默感"},
    "市场数据":  {"style": "托马斯之颅", "templates": "G/B", "openings": "4/8",   "endings": "3/4", "tone": "数据对比 + 周期视角"},
    "突发热点":  {"style": "混合",       "templates": "I/B", "openings": "9/1/2", "endings": "2/7", "tone": "快节奏 + 精准判断"},
}


def build_skill_system_prompt(
    skill_content: str,
    article_type: Optional[str] = None,
) -> str:
    """
    将 SKILL.md 转为 system prompt

    Args:
        skill_content: SKILL.md 原文
        article_type: 稿件类型（行业趋势/游戏评测/...），用于高亮推荐

    Returns:
        完整的 system prompt
    """
    # 类型推荐提示
    type_hint = ""
    if article_type and article_type in TYPE_RECOMMENDATIONS:
        rec = TYPE_RECOMMENDATIONS[article_type]
        type_hint = f"""

---
## 本次任务类型推荐

根据稿件类型「{article_type}」，建议：
- **主风格**: {rec['style']}
- **推荐模板**: {rec['templates']}
- **推荐开篇策略**: {rec['openings']}
- **推荐结尾策略**: {rec['endings']}
- **情绪底色**: {rec['tone']}

请在上述推荐范围内随机选择具体模板/开篇/结尾，不要每次都用同一种。
"""

    return f"""你是一位职业游戏行业写手，拥有20年以上行业观察经验。你的写作风格融合了两位资深行业作者的精髓。

以下是你的写作风格库，你必须严格遵守其中的规则：

{skill_content}
{type_hint}

## 核心写作指令

1. **每次写作前先过决策清单**（见风格库中的「随机化决策清单」），在九个模板/九种开篇/七种结尾中各选一个，确保不重复使用上一篇文章的套路
2. **禁止 AI 套话**: 绝不使用"随着时代发展""众所周知""毋庸置疑""技术革命""行业突破"等空洞表述
3. **开头必须有钩子**: 从一个具体场景、数据、矛盾或反直觉判断切入，不要讲大道理
4. **结尾不过度升华**: 用淡出、回马枪、开放式问题或细节定格收尾，不要喊口号
5. **语言有颗粒度**: 祝佳音风格用"十分上等""透出一股邪气"这类词，托马斯风格用"方差""头部集中""认知错位"这类词。不要混成 bland 的中间状态
6. **真诚表达**: 不说自己不相信的话，不写 PR 话术

现在开始按照这个风格库写作。"""


def build_skill_user_prompt(
    topic: str,
    requirements: str = "",
    keywords: Optional[List[str]] = None,
    length: Optional[str] = None,
    background: str = "",
    knowledge_context: str = "",
) -> str:
    """
    构建 user prompt

    Args:
        topic: 话题/主题
        requirements: 具体要求
        keywords: 关键词列表
        length: 字数要求
        background: 背景信息
        knowledge_context: 格式化的知识上下文（由 PromptBuilder.build_knowledge_context 生成）

    Returns:
        完整的 user prompt
    """
    prompt = f"""## 写作任务

**话题/主题:** {topic}
"""

    if background:
        prompt += f"\n**背景信息:**\n{background}"

    if requirements:
        prompt += f"\n**具体要求:**\n{requirements}"

    if keywords:
        prompt += f"\n**关键词:** {', '.join(keywords)}"

    if length:
        prompt += f"\n**字数要求:** {length}"

    if knowledge_context:
        prompt += f"""

## 参考资料

以下是相关的参考资料，请结合这些内容进行写作。注意:
- 不要直接复制原文，用自己的话重新组织和表达
- 引用数据时注明来源
- 资料是素材，观点和判断要来自你自己

{knowledge_context}

## 写作要求

请根据以上任务和参考资料，运用你的写作风格库撰写一篇专业的游戏行业文章。

重要提醒:
1. 文章必须有明确、新颖的核心观点，不要做信息堆砌
2. 严格按照风格库中的模板结构组织文章
3. 开头要有钩子（不要从大道理讲起）
4. 语言要自然，有节奏感，像真人在说话
5. 写出你的真实判断——好就说好，不好就说不好
6. 直接输出文章内容，不要加"以下是文章"之类的引导语"""

    return prompt


class SkillPromptBuilder:
    """SKILL.md 提示词构建器（门面类）"""

    def __init__(self, skill_md_path: Optional[str] = None):
        self.skill_content = load_skill_md(skill_md_path)
        self._base_builder = PromptBuilder()

    def build_prompt(
        self,
        topic: str,
        requirements: str = "",
        keywords: Optional[List[str]] = None,
        length: Optional[str] = None,
        background: str = "",
        article_type: Optional[str] = None,
        knowledge_items: Optional[List[KnowledgeContext]] = None,
        max_knowledge_chars: Optional[int] = None,
    ) -> Dict[str, str]:
        """
        构建完整提示词

        Returns:
            {"system": ..., "user": ...}
        """
        # 构建知识上下文
        knowledge_context = ""
        if knowledge_items:
            knowledge_context = self._base_builder.build_knowledge_context(
                knowledge_items,
                max_chars=max_knowledge_chars,
            )

        return {
            "system": build_skill_system_prompt(self.skill_content, article_type),
            "user": build_skill_user_prompt(
                topic=topic,
                requirements=requirements,
                keywords=keywords,
                length=length,
                background=background,
                knowledge_context=knowledge_context,
            ),
        }
