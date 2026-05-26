#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StrategyCompiler模块 - 策略蓝图编译为写作指令

将JSON蓝图转译为RAGWriter可用的完整提示词
"""

from typing import Dict, Any, List, Union

from ..prompt_engineering import KnowledgeContext
from ..style_injector import get_style_injection
from .models import (
    StrategyBlueprint,
    WritingInstructions,
    SectionInstruction,
    WritingTone,
)


class StrategyCompiler:
    """
    策略蓝图编译为写作指令

    核心职责：
    - 将JSON蓝图转为RAGWriter可用的完整提示词
    - 保持"策略"与"事实"的清晰分离
    - 策略层（SkillAgent）管"怎么写"
    - 事实层（RAGWriter）管"写什么"
    """

    def __init__(
        self,
        llm_client: Any = None,
        temperature: float = 0.4,
    ):
        """
        初始化编译器

        Args:
            llm_client: LLM客户端（编译不涉及LLM调用，可选）
            temperature: 生成温度（保留参数兼容性）
        """
        self.llm_client = llm_client
        self.temperature = temperature

    def compile(
        self,
        blueprint: StrategyBlueprint,
        rag_context: Dict[str, Any],
    ) -> WritingInstructions:
        """
        编译策略蓝图为写作指令

        Args:
            blueprint: 策略蓝图（来自SkillAgent）
            rag_context: RAG上下文（来自RAGWriter.retrieve_knowledge）
                格式: {"knowledge": List[KnowledgeContext], ...}

        Returns:
            WritingInstructions: 可执行的写作指令
        """
        # 构建分节指令
        section_instructions = []
        for section in blueprint.sections:
            instruction_text = self._build_section_instruction(
                section, blueprint, rag_context
            )
            section_instructions.append(SectionInstruction(
                section_id=section.section_id,
                title=section.title,
                instruction_text=instruction_text,
                key_points=[section.content_focus],
                style_reminders=[section.style_guidance],
            ))

        # 构建完整写作指令
        instruction_text = self._build_full_instruction(blueprint, rag_context)

        # 构建风格约束
        style_constraints = {
            "tone": blueprint.writing_tone.value,
            "forbidden_patterns": blueprint.forbidden_patterns,
            "global_notes": blueprint.global_style_notes,
        }

        return WritingInstructions(
            topic=blueprint.topic,
            content_type=blueprint.content_type,
            target_audience=blueprint.target_audience,
            core_tension=blueprint.core_tension,
            writing_tone=blueprint.writing_tone,
            instruction_text=instruction_text,
            section_instructions=section_instructions,
            style_constraints=style_constraints,
            rag_context=rag_context,
            case_references=blueprint.case_references,
        )

    def _build_section_instruction(
        self,
        section,
        blueprint: StrategyBlueprint,
        rag_context: Dict[str, Any],
    ) -> str:
        """为单个Section生成具体写作指令"""
        knowledge = rag_context.get("knowledge", [])

        # 构建引用提示
        ref_hints = []
        for i, item in enumerate(knowledge[:3], 1):  # 最多引用3个
            # 处理KnowledgeContext对象或字典
            if hasattr(item, 'content'):
                item_content = getattr(item, 'content', '')[:100]
                item_title = getattr(item, 'title', '未知')
            elif isinstance(item, dict):
                item_content = item.get('content', '')[:100]
                item_title = item.get('title', '未知')
            else:
                item_content = str(item)[:100]
                item_title = '未知'
            ref_hints.append(f"- 【参考资料{i}】{item_title}: {item_content}...")

        instruction = f"""### {section.title}

**写作手法**: {section.structural_approach}
**内容要点**: {section.content_focus}
**风格要求**: {section.style_guidance}
**字数分配**: 约占全文{section.length_ratio:.0%}

**参考素材**:
{(chr(10).join(ref_hints)) if ref_hints else "（无参考素材，请基于话题自行发挥）"}

**过渡处理**: {section.transition_to_next or "自然衔接"}
"""
        return instruction

    def _build_full_instruction(
        self,
        blueprint: StrategyBlueprint,
        rag_context: Dict[str, Any],
    ) -> str:
        """构建完整写作指令"""
        knowledge = rag_context.get("knowledge", [])

        # 参考素材摘要——只列标题来源，不展示全文（全文留到写作阶段）
        ref_parts = []
        for i, item in enumerate(knowledge, 1):
            if isinstance(item, KnowledgeContext):
                ref_parts.append(f"- 【参考资料{i}】{item.title} | {item.author} | {item.date}")
            else:
                ref_parts.append(f"- 【参考资料{i}】{item.get('title', '未知')} | {item.get('author', '未知')} | {item.get('date', '未知')}")

        ref_text = "\n".join(ref_parts) if ref_parts else "（无参考素材，将基于话题自行发挥）"

        # 格式化禁止模式
        forbidden_text = "\n".join([f"- {p}" for p in blueprint.forbidden_patterns]) if blueprint.forbidden_patterns else "- 无特殊禁止模式"

        # 格式化风格注意事项
        notes_text = "\n".join([f"- {n}" for n in blueprint.global_style_notes]) if blueprint.global_style_notes else "- 无特殊要求"

        title = blueprint.article_title or blueprint.topic
        instruction = f"""## 文章标题

**{title}**

---

## 写作任务

**话题**: {blueprint.topic}
**内容类型**: {blueprint.content_type}
**目标受众**: {blueprint.target_audience}
**核心张力**: {blueprint.core_tension}
**写作基调**: {blueprint.writing_tone.value}

---

## 参考素材

{ref_text or "（无参考素材，请基于话题自行发挥）"}

---

## 写作指导

**开篇策略**：
- 方式: {blueprint.opening.approach}
- 钩子: {blueprint.opening.hook_content}
- 长度: {blueprint.opening.lead_length}

**禁止的套话**：
{forbidden_text}

**风格注意事项**：
{notes_text}

---

## 章节结构

请按以下章节结构撰写文章：

"""

        for section in blueprint.sections:
            instruction += f"""### {section.section_id}. {section.title}
- 结构手法: {section.structural_approach}
- 内容重点: {section.content_focus}
- 风格: {section.style_guidance}
- 字数占比: {section.length_ratio:.0%}
- 过渡: {section.transition_to_next or "自然衔接"}

"""

        instruction += f"""---

## 收尾策略

- 方式: {blueprint.closing.approach}
- 核心收获: {blueprint.closing.key_takeaway}
- 长度: {blueprint.closing.ending_length}

---

请直接输出完整文章内容，不要加"以下是文章"之类的引导语。
"""

        return instruction

    def compile_to_prompt(
        self,
        blueprint: StrategyBlueprint,
        rag_context: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        编译为system和user提示词格式

        供RAGWriter直接使用

        Args:
            blueprint: 策略蓝图
            rag_context: RAG上下文

        Returns:
            {"system": ..., "user": ...}
        """
        instruction = self.compile(blueprint, rag_context)

        system_prompt = f"""你是一位资深的行业内容创作者，擅长撰写专业、有深度且读起来自然的行业分析文章。

写作基调：{blueprint.writing_tone.value}

你的写作风格:
- 专业但不晦涩，用通俗易懂的语言解释专业概念
- 有自己独立的观点和见解，不做简单的信息堆砌
- 善于使用具体案例、数据和故事来支撑观点
- 文章结构清晰，逻辑连贯，段落之间过渡自然
- 语言有节奏感，长短句结合，读起来不枯燥

禁止的套话模式：
{forbidden_text}

请严格按照以下章节结构和写作指导撰写文章。"""

        system_prompt += get_style_injection()

        return {
            "system": system_prompt,
            "user": instruction.instruction_text,
        }
