#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SkillAgent主类 - 写作策略智能体

扮演"策略导师/架构师"角色：
1. 接收话题 + RAG上下文
2. 检索相关策略案例（动态Few-shot）
3. 生成带策略依据的JSON蓝图
4. Self-Reflection校验
5. 输出可执行的写作指令
"""

import json
import re
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from .models import (
    StrategyBlueprint,
    StrategyCase,
    WritingInstructions,
    ReflectionResult,
)
from .case_base import CaseBaseManager
from .retriever import StrategyRetriever
from .reflection import SelfReflectionValidator
from .compiler import StrategyCompiler
from .prompts import (
    SkillPromptBuilder,
    format_rag_context_for_skill,
    format_case_for_few_shot,
)
from .config import get_skill_config
from ..llm_client import BaseLLMClient


class SkillAgent:
    """
    写作Skill智能体 - 策略导师/架构师

    核心职责：
    1. 接收话题 + RAG上下文
    2. 检索相关策略案例（动态Few-shot）
    3. 生成带策略依据的JSON蓝图
    4. Self-Reflection校验（可选）
    5. 调用StrategyCompiler转译为写作指令

    设计原则：
    - 策略与事实隔离：SkillAgent管"怎么写"，RAGWriter管"写什么"
    - JSON Schema强制约束：确保下游系统可解析
    - 置信度机制：低于阈值时自动重试或降级
    """

    def __init__(
        self,
        case_base: CaseBaseManager,
        llm_client: BaseLLMClient,
        retriever: Optional[StrategyRetriever] = None,
        temperature: float = 0.4,
        case_retrieval_top_k: int = 5,
        max_reflection_iterations: int = 2,
        min_confidence_threshold: float = 0.5,
        use_reflection: bool = True,
    ):
        """
        初始化SkillAgent

        Args:
            case_base: 策略案例库管理器
            llm_client: LLM客户端（复用rag_writer的）
            retriever: 策略案例检索器（若为None则创建）
            temperature: 策略生成温度，建议0.3~0.5
            case_retrieval_top_k: 检索策略案例数量
            max_reflection_iterations: 最大校验迭代次数
            min_confidence_threshold: 置信度阈值，低于此值将重试
            use_reflection: 是否启用Self-Reflection校验
        """
        self.case_base = case_base
        self.llm_client = llm_client
        self.retriever = retriever or StrategyRetriever(case_base, case_retrieval_top_k)
        self.prompt_builder = SkillPromptBuilder()

        self.temperature = temperature
        self.max_reflection_iterations = max_reflection_iterations
        self.min_confidence_threshold = min_confidence_threshold
        self.use_reflection = use_reflection

    def generate_blueprint(
        self,
        topic: str,
        rag_context: Dict[str, Any],
        content_type: Optional[str] = None,
        target_audience: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        use_reflection: Optional[bool] = None,
        background: Optional[str] = None,
        brainstorm_results: Optional[Dict[str, Any]] = None,
    ) -> StrategyBlueprint:
        """
        生成策略蓝图

        核心流程：
        1. 检索相关策略案例（用于Few-shot学习）
        2. 构建策略生成提示词（含背景、要求、优质文章学习）
        3. 调用LLM生成JSON蓝图
        4. Self-Reflection校验（可选）
        5. 返回最终策略蓝图

        Args:
            topic: 写作话题
            rag_context: RAG上下文（知识检索结果），格式：
                {
                    "knowledge": List[KnowledgeContext],
                    "topic": str,
                    "background": str,  # 背景信息
                    "requirements": str,  # 具体要求
                    ...
                }
            content_type: 内容类型（行业分析/趋势解读等）
            target_audience: 目标受众
            constraints: 额外约束条件（含article_count用于检索优质文章）
            use_reflection: 是否启用校验（None则使用默认）
            background: 背景信息（时事背景等）

        Returns:
            StrategyBlueprint: 结构化策略蓝图
        """
        start_time = time.time()
        config = get_skill_config()

        # 确定是否启用校验
        if use_reflection is None:
            use_reflection = self.use_reflection

        # 获取背景信息（优先从rag_context获取）
        if background is None:
            background = rag_context.get("background", "")

        # 获取具体要求
        requirements = rag_context.get("requirements", "")
        if constraints and "requirements" in constraints:
            requirements = constraints["requirements"]

        # 获取字数要求
        length = constraints.get("length") if constraints else None

        # 1. 检索相关策略案例（用于Few-shot示例）
        print(f"检索策略案例: {topic[:30]}...")
        similar_cases = self.retriever.retrieve(
            query=topic,
            top_k=config.case_retrieval_top_k,
        )

        # 格式化Few-shot案例——只提取框架级信息（切入/结构/递进方式），不包含写作手法细节
        few_shot_cases = []
        for case in similar_cases:
            annotation = case.annotation
            # 章节递进脉络
            section_flow = []
            if annotation.section_strategies:
                section_flow = [
                    f"{s.section_title}（{s.structural_approach}→聚焦「{s.content_focus}」）"
                    for s in annotation.section_strategies[:4]
                ]
            few_shot_cases.append({
                "title": case.title,
                "content_type": case.content_type,
                "core_tension": annotation.core_tension or "未标注",
                "opening_approach": annotation.opening_approach,
                "structural_pattern": annotation.structural_pattern,
                "section_flow": section_flow,
                "closing_approach": annotation.closing_approach,
                "target_audience": case.target_audience,
            })

        # 2. 构建RAG上下文字符串（用于事实支撑）
        knowledge = rag_context.get("knowledge", [])
        rag_text = format_rag_context_for_skill(knowledge, max_chars=6000)

        # 3. 获取检索文章数量（用于学习写作策略）
        article_count = 5
        if constraints and "article_count" in constraints:
            article_count = constraints["article_count"]

        # 4. 构建提示词（整合背景、要求、优质文章学习）
        prompt = self.prompt_builder.build_strategy_prompt(
            topic=topic,
            background=background,
            requirements=requirements,
            length=length,
            rag_context=rag_text,
            content_type=content_type,
            target_audience=target_audience,
            few_shot_cases=few_shot_cases if few_shot_cases else None,
            constraints=constraints,
            article_count=article_count,
            brainstorm_results=brainstorm_results,
        )

        # 5. 调用LLM生成
        print("生成策略蓝图...")
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                system_prompt=prompt["system"],
                user_prompt=prompt["user"],
                temperature=self.temperature,
                max_tokens=8000,  # DeepSeek最大支持8192
            )
        else:
            response = self.llm_client.generate(
                f"{prompt['system']}\n\n{prompt['user']}",
                temperature=self.temperature,
                max_tokens=8000,
            )

        # 6. 解析JSON（带重试回退机制）
        try:
            blueprint = self._parse_blueprint(response.content)
        except ValueError as e:
            # JSON解析失败，尝试用简化提示词重新生成
            print(f"蓝图解析失败: {e}，尝试简化版本...")
            simplified_prompt = self.prompt_builder.build_simple_strategy_prompt(
                topic=topic,
                background=background,
                requirements=requirements,
                rag_context=rag_text,
                content_type=content_type,
                target_audience=target_audience,
            )
            if hasattr(self.llm_client, 'generate_with_system'):
                response = self.llm_client.generate_with_system(
                    system_prompt=simplified_prompt["system"],
                    user_prompt=simplified_prompt["user"],
                    temperature=self.temperature,
                    max_tokens=8000,  # 减少token限制
                )
            else:
                response = self.llm_client.generate(
                    f"{simplified_prompt['system']}\n\n{simplified_prompt['user']}",
                    temperature=self.temperature,
                    max_tokens=8000,
                )
            blueprint = self._parse_blueprint(response.content)

        # 更新元数据
        blueprint.meta = {
            "agent_version": "1.0.0",
            "generation_time": time.time() - start_time,
            "temperature": self.temperature,
            "case_references": [c.case_id for c in similar_cases],
            "case_count": len(similar_cases),
            "background_used": bool(background),
        }

        # 7. Self-Reflection校验
        if use_reflection:
            blueprint = self._validate_and_refine(blueprint, rag_text, similar_cases)

        return blueprint

    def revise_blueprint(
        self,
        topic: str,
        rag_context: Dict[str, Any],
        original_blueprint: Dict[str, Any],
        user_feedback: str,
        revised_markdown: Optional[str] = None,
        content_type: Optional[str] = None,
        target_audience: Optional[str] = None,
        use_reflection: Optional[bool] = None,
        background: Optional[str] = None,
        requirements: Optional[str] = None,
    ) -> StrategyBlueprint:
        """
        基于原蓝图和用户反馈修订策略蓝图

        核心流程：
        1. 构建包含原蓝图的修订提示词
        2. 调用LLM生成修订后的JSON蓝图
        3. 返回最终策略蓝图

        Args:
            topic: 写作话题
            rag_context: RAG上下文（知识检索结果）
            original_blueprint: 原始策略蓝图字典
            user_feedback: 用户修改意见
            revised_markdown: 用户编辑后的蓝图文案（优先使用）
            content_type: 内容类型
            target_audience: 目标受众
            use_reflection: 是否启用校验
            background: 背景信息
            requirements: 具体要求

        Returns:
            StrategyBlueprint: 修订后的策略蓝图
        """
        start_time = time.time()
        config = get_skill_config()

        # 确定是否启用校验
        if use_reflection is None:
            use_reflection = self.use_reflection

        # 获取背景信息（优先从rag_context获取）
        if background is None:
            background = rag_context.get("background", "")

        # 获取具体要求
        if requirements is None:
            requirements = rag_context.get("requirements", "")

        # 1. 如果用户提供了编辑后的markdown，尝试直接解析为蓝图
        if revised_markdown:
            try:
                # 尝试从markdown中提取JSON并解析
                blueprint = self._parse_blueprint(revised_markdown)
                blueprint.meta = {
                    "agent_version": "1.0.0",
                    "generation_time": time.time() - start_time,
                    "temperature": self.temperature,
                    "revision": True,
                    "user_edited": True,
                    "original_blueprint_topic": original_blueprint.get("topic", "") if original_blueprint else "",
                }
                return blueprint
            except ValueError:
                # 解析失败，继续使用LLM生成
                print(f"蓝图文案解析失败，继续使用LLM生成...")

        # 2. 构建RAG上下文字符串
        knowledge = rag_context.get("knowledge", [])
        rag_text = format_rag_context_for_skill(knowledge, max_chars=6000)

        # 3. 如果没有有效反馈且没有编辑后的markdown，使用原蓝图（不做修改）
        if not user_feedback and not revised_markdown:
            if original_blueprint:
                try:
                    blueprint = StrategyBlueprint(**original_blueprint)
                    blueprint.meta = {
                        "agent_version": "1.0.0",
                        "generation_time": time.time() - start_time,
                        "revision": True,
                        "no_change": True,
                    }
                    return blueprint
                except Exception:
                    pass  # 继续正常流程

        # 4. 构建修订提示词
        prompt = self.prompt_builder.build_revision_prompt(
            topic=topic,
            original_blueprint=original_blueprint,
            user_feedback=user_feedback,
            rag_context=rag_text,
            content_type=content_type,
            target_audience=target_audience,
            background=background,
            requirements=requirements,
        )

        # 5. 调用LLM生成修订后的蓝图
        print("修订策略蓝图...")
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                system_prompt=prompt["system"],
                user_prompt=prompt["user"],
                temperature=self.temperature,
                max_tokens=8000,  # DeepSeek最大支持8192
            )
        else:
            response = self.llm_client.generate(
                f"{prompt['system']}\n\n{prompt['user']}",
                temperature=self.temperature,
                max_tokens=8000,  # DeepSeek最大支持8192
            )

        # 6. 解析JSON
        try:
            blueprint = self._parse_blueprint(response.content)
        except ValueError as e:
            # JSON解析失败，记录错误并重新生成（不做回退，因为有原蓝图参考）
            print(f"蓝图解析失败: {e}，使用原蓝图为基础进行修订...")
            import os
            debug_file = os.path.join(os.path.dirname(__file__), "parse_revision_debug.log")
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(f"原始蓝图: {json.dumps(original_blueprint, ensure_ascii=False)[:1000]}\n")
                f.write(f"\n用户反馈: {user_feedback}\n")
                f.write(f"\nLLM返回: {response.content[:3000]}\n")
            raise

        # 更新元数据
        blueprint.meta = {
            "agent_version": "1.0.0",
            "generation_time": time.time() - start_time,
            "temperature": self.temperature,
            "revision": True,
            "original_blueprint_topic": original_blueprint.get("topic", ""),
            "background_used": bool(background),
        }

        # 7. Self-Reflection校验（可选）
        if use_reflection:
            blueprint = self._validate_and_refine(blueprint, rag_text, [])

        return blueprint

    def _parse_blueprint(self, json_str: str) -> StrategyBlueprint:
        """
        解析策略蓝图JSON

        尝试多种解析策略，并对LLM输出进行数据清洗
        """
        text = json_str.strip()

        # 查找所有JSON代码块
        json_blocks = re.findall(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
        # 也添加纯JSON对象作为候选
        brace_start = text.find('{')
        if brace_start != -1:
            # 从第一个{开始，尝试找到完整的JSON
            for brace_end in range(len(text), brace_start, -1):
                candidate = text[brace_start:brace_end]
                try:
                    data = json.loads(candidate)
                    if "topic" in data and "sections" in data:
                        json_blocks.append(candidate)
                        break
                except json.JSONDecodeError:
                    continue

        # 尝试解析每个JSON块
        import os
        debug_file = os.path.join(os.path.dirname(__file__), "parse_debug2.log")
        parse_errors = []
        for i, json_text in enumerate(json_blocks):
            try:
                data = json.loads(json_text)
                data = self._clean_blueprint_data(data)
                return StrategyBlueprint(**data)
            except (json.JSONDecodeError, Exception) as e:
                parse_errors.append(f"Block {i}: {type(e).__name__}: {str(e)[:200]}")
                continue

        # 记录解析失败详情
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(f"JSON块数量: {len(json_blocks)}\n")
            for i, block in enumerate(json_blocks):
                f.write(f"\n=== Block {i} ===\n")
                f.write(block[:1500])
            f.write(f"\n\n解析错误:\n")
            for err in parse_errors:
                f.write(f"{err}\n")

        # 尝试修复被截断的JSON
        truncated_json = self._try_fix_truncated_json(text)
        if truncated_json:
            try:
                data = self._clean_blueprint_data(truncated_json)
                return StrategyBlueprint(**data)
            except Exception:
                pass

        # 所有解析都失败，写入日志文件用于调试
        import os
        debug_file = os.path.join(os.path.dirname(__file__), "parse_debug.log")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(f"JSON块数量: {len(json_blocks)}\n")
            f.write(f"JSON块内容: {json_blocks}\n")
            f.write(f"原始文本: {text[:3000]}\n")
        raise ValueError(f"无法解析策略蓝图JSON (共{len(json_blocks)}个JSON块)")

    def _try_fix_truncated_json(self, text: str) -> Optional[dict]:
        """
        尝试修复被截断的JSON

        常见截断情况：
        1. 字符串在引号前被截断
        2. 数组在闭合括号前被截断
        3. 对象在闭合大括号前被截断
        4. 字段在中间被截断（如 "title": "部分内容）
        """
        import re

        # 尝试找到JSON开始
        json_start = text.find('{')
        if json_start == -1:
            return None

        truncated = text[json_start:]

        # 首先检查基本完整性
        open_braces = truncated.count('{') - truncated.count('}')
        open_brackets = truncated.count('[') - truncated.count(']')

        # 如果花括号不匹配，先尝试补全花括号
        if open_braces > 0:
            truncated += '}' * open_braces
        if open_brackets > 0:
            # sections数组可能被截断，需要补全
            truncated += ']' * open_brackets

        # 策略1：如果最后一个字段是字符串且被截断，尝试找到最后一个完整的字段
        # 查找所有可能的截断点 - 优先匹配完整字段
        patterns_to_try = [
            # 在闭合括号处截断
            r'(.+\})\s*$',
            r'(.+\])\s*$',
            # 在逗号处截断（字段结束）
            r'(.+\},)\s*$',
        ]

        for pattern in patterns_to_try:
            match = re.search(pattern, truncated, re.DOTALL)
            if match:
                candidate = match.group(1)
                try:
                    data = json.loads(candidate)
                    if "topic" in data and "sections" in data:
                        return data
                except json.JSONDecodeError:
                    continue

        # 策略2：尝试修复被截断的字符串字段
        # 如果末尾是 "ti" 这样的截断内容，尝试找到最后一个完整的字符串值
        # 匹配 "field": "value" 或 "field": "value", 模式
        field_pattern = r'("[\w]+":\s*"[^"]*"),?\s*$'
        match = re.search(field_pattern, truncated, re.DOTALL)
        if match:
            # 找到最后一个完整字段，截断到此处
            fixed = truncated[:match.end()].rstrip()
            if fixed.endswith(','):
                fixed = fixed.rstrip(',') + '}'
            else:
                fixed = fixed + '"}'
            # 补全花括号
            open_br = fixed.count('{') - fixed.count('}')
            open_br += fixed.count('[') - fixed.count(']')
            if open_br > 0:
                fixed += '}' * open_br
            try:
                data = json.loads(fixed)
                if "topic" in data and "sections" in data:
                    return data
            except json.JSONDecodeError:
                pass

        # 策略3：尝试补全常见的截断模式
        # 如果以"开头但没有结束，尝试添加
        if truncated.rstrip().endswith('"') and truncated.count('"') % 2 == 1:
            # 奇数个引号，字符串未闭合
            truncated = truncated.rstrip() + '"}'

        # 尝试补全数组
        open_brackets = truncated.count('[') - truncated.count(']')
        open_braces = truncated.count('{') - truncated.count('}')
        if open_brackets > 0:
            truncated += ']' * open_brackets
        if open_braces > 0:
            truncated += '}' * open_braces

        try:
            data = json.loads(truncated)
            if "topic" in data and "sections" in data:
                return data
        except json.JSONDecodeError:
            pass

        # 策略4：暴力补全 - 从最后一个完整字段截断
        # 查找最后一个 "}," 或 "}]" 等完整字段结束标记
        last_field_end = truncated.rfind('"},')
        if last_field_end > 0:
            candidate = truncated[:last_field_end + 2] + ']}'
            try:
                data = json.loads(candidate)
                if "topic" in data and "sections" in data:
                    return data
            except json.JSONDecodeError:
                pass

        return None

    def _clean_blueprint_data(self, data: dict) -> dict:
        """
        清洗策略蓝图数据，修复LLM常见的格式问题
        """
        import re

        # 修复article_title：确保存在且非空
        if "article_title" not in data or not data["article_title"]:
            data["article_title"] = data.get("topic", "未命名")

        # 修复supporting_points：确保是列表且不为空
        if "supporting_points" not in data or not data["supporting_points"]:
            data["supporting_points"] = []
        elif not isinstance(data["supporting_points"], list):
            data["supporting_points"] = [str(data["supporting_points"])]

        # 修复sections中的字段类型问题
        if "sections" in data and isinstance(data["sections"], list):
            for index, section in enumerate(data["sections"]):
                if isinstance(section, dict):
                    # section_id: 确保存在（整数转字符串，或自动生成）
                    if "section_id" not in section:
                        # 自动生成 section_id: s1, s2, ...
                        section_num = index + 1
                        section["section_id"] = f"s{section_num}"
                    elif isinstance(section["section_id"], int):
                        section["section_id"] = f"s{section['section_id']}"

                    # length_ratio: "15%" -> 0.15，但 "0.3" -> 0.3（不是0.003）
                    if "length_ratio" in section:
                        lr = section["length_ratio"]
                        if isinstance(lr, str):
                            lr = lr.strip()
                            if "%" in lr:
                                # 百分比格式 "15%" -> 0.15
                                lr_match = re.match(r'([\d.]+)%', lr)
                                if lr_match:
                                    section["length_ratio"] = float(lr_match.group(1)) / 100
                                else:
                                    section["length_ratio"] = 0.2  # 默认值
                            else:
                                # 小数字符串 "0.3" -> 0.3
                                try:
                                    section["length_ratio"] = float(lr)
                                except ValueError:
                                    section["length_ratio"] = 0.2  # 默认值
                        elif isinstance(lr, (int, float)):
                            # 如果是整数如15，转为小数如0.15
                            if lr > 1:
                                section["length_ratio"] = lr / 100
                            # 如果已经是小数如0.15，保持不变

                    # content_focus: 修复空字符串
                    if "content_focus" in section and not section["content_focus"]:
                        section["content_focus"] = "待补充"
                    # structural_approach: 修复缺失问题（SectionStrategy的必需字段）
                    if "structural_approach" not in section or not section["structural_approach"]:
                        section["structural_approach"] = "递进式"
                    # transition_to_next: 修复None问题
                    if "transition_to_next" not in section:
                        section["transition_to_next"] = None
                    # case_references: 修复缺失问题
                    if "case_references" not in section:
                        section["case_references"] = []
                    # confidence: 修复缺失问题
                    if "confidence" not in section:
                        section["confidence"] = 0.7
                    # hook_content: 修复缺失问题（可选字段）
                    if "hook_content" not in section:
                        section["hook_content"] = None

        # 修复opening字段：确保OpeningStrategy的必需字段存在
        if "opening" in data and isinstance(data["opening"], dict):
            # 修复length_ratio格式问题
            if "length_ratio" in data["opening"]:
                lr = data["opening"]["length_ratio"]
                if isinstance(lr, str) and "%" in lr:
                    lr_match = re.match(r'([\d.]+)%?', lr)
                    if lr_match:
                        data["opening"]["length_ratio"] = f"{lr_match.group(1)}字内"
            # 修复lead_length缺失问题（OpeningStrategy的必需字段）
            if "lead_length" not in data["opening"] or not data["opening"]["lead_length"]:
                data["opening"]["lead_length"] = "100字内"
            # 修复case_references缺失问题（OpeningStrategy的必需字段）
            if "case_references" not in data["opening"]:
                data["opening"]["case_references"] = []
            # 修复hook_content缺失问题
            if "hook_content" not in data["opening"] or not data["opening"]["hook_content"]:
                data["opening"]["hook_content"] = data["opening"].get("approach", "待补充")

        # 修复closing字段：确保ClosingStrategy的必需字段存在
        if "closing" in data and isinstance(data["closing"], dict):
            # 修复ending_length缺失问题（ClosingStrategy的必需字段）
            if "ending_length" not in data["closing"] or not data["closing"]["ending_length"]:
                data["closing"]["ending_length"] = "150字内"
            # 修复key_takeaway缺失问题
            if "key_takeaway" not in data["closing"] or not data["closing"]["key_takeaway"]:
                data["closing"]["key_takeaway"] = "待总结核心观点"
            # 修复approach缺失问题
            if "approach" not in data["closing"] or not data["closing"]["approach"]:
                data["closing"]["approach"] = "总结要点"
            # 修复case_references缺失问题
            if "case_references" not in data["closing"]:
                data["closing"]["case_references"] = []

        # 修复core_tension为空的问题
        if "core_tension" not in data or not data["core_tension"]:
            data["core_tension"] = "待确定"

        # 修复writing_tone：只取第一个有效的枚举值
        valid_tones = {"professional", "casual", "authoritative", "analytical", "narrative"}
        if "writing_tone" in data:
            tone = data["writing_tone"]
            if isinstance(tone, str):
                # 处理 "authoritative+analytical" 这种多值情况
                tone = tone.lower().split("+")[0].strip()
                if tone not in valid_tones:
                    tone = "analytical"  # 默认值
                data["writing_tone"] = tone

        # 修复target_audience：列表转为字符串
        if "target_audience" in data:
            ta = data["target_audience"]
            if isinstance(ta, list):
                data["target_audience"] = "、".join(str(x) for x in ta)
            elif not isinstance(ta, str):
                data["target_audience"] = str(ta)

        # 修复sections截断问题：如果sections缺少结尾，尝试补全
        if "sections" in data and isinstance(data["sections"], list):
            last_section = data["sections"][-1] if data["sections"] else None
            if last_section and isinstance(last_section, dict):
                # 检查sections是否被截断（最后section缺少closing）
                if "closing" not in last_section:
                    last_section["closing"] = {
                        "approach": "总结要点",
                        "summary": "总结全文核心观点",
                        "call_to_action": "无"
                    }

        return data

    def _validate_and_refine(
        self,
        blueprint: StrategyBlueprint,
        rag_context: str,
        similar_cases: List[StrategyCase],
    ) -> StrategyBlueprint:
        """
        Self-Reflection校验并优化策略蓝图

        Args:
            blueprint: 待校验的策略蓝图
            rag_context: RAG上下文
            similar_cases: 参考的策略案例

        Returns:
            校验后的策略蓝图
        """
        validator = SelfReflectionValidator(self.llm_client)

        for iteration in range(self.max_reflection_iterations):
            result = validator.validate(blueprint, rag_context)

            if result.is_valid:
                # 更新置信度
                blueprint.confidence = min(
                    blueprint.confidence + result.confidence_adjustment,
                    1.0
                )
                print(f"策略蓝图校验通过，置信度: {blueprint.confidence:.2f}")
                break

            # 校验失败，根据建议优化
            print(f"策略蓝图需要优化 (迭代 {iteration + 1}/{self.max_reflection_iterations})")
            print(f"问题: {result.issues}")

            if iteration < self.max_reflection_iterations - 1:
                # 应用优化建议重新生成
                blueprint = self._regenerate_with_feedback(
                    blueprint, result, rag_context
                )
            else:
                # 达到最大迭代次数，降低置信度标记
                print("达到最大校验迭代，标记置信度降低")
                blueprint.confidence = min(blueprint.confidence * 0.8, 0.5)

        return blueprint

    def _regenerate_with_feedback(
        self,
        blueprint: StrategyBlueprint,
        reflection_result: ReflectionResult,
        rag_context: str,
    ) -> StrategyBlueprint:
        """
        根据校验反馈重新生成策略蓝图

        Args:
            blueprint: 原蓝图
            reflection_result: 校验结果
            rag_context: RAG上下文

        Returns:
            重新生成的策略蓝图
        """
        # 构建反馈提示
        issues_text = "\n".join([
            f"- {issue.description}" for issue in reflection_result.issues
        ])
        suggestions_text = "\n".join([
            f"- {s}" for s in reflection_result.suggestions
        ])

        feedback_prompt = f"""请根据以下校验反馈优化策略蓝图：

原始话题: {blueprint.topic}

校验发现的问题：
{issues_text}

修改建议：
{suggestions_text}

请生成优化后的策略蓝图（JSON格式），确保：
1. 解决上述问题
2. 保持原有的核心张力
3. 保持合理的章节结构
"""

        # 调用LLM重新生成
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                system_prompt="你是一个专业的写作策略优化专家。",
                user_prompt=feedback_prompt,
                temperature=self.temperature,
                max_tokens=8000,  # DeepSeek最大支持8192
            )
        else:
            response = self.llm_client.generate(
                f"你是一个专业的写作策略优化专家。\n\n{feedback_prompt}",
                temperature=self.temperature,
                max_tokens=8000,  # DeepSeek最大支持8192
            )

        # 解析新蓝图
        import os
        debug_file = os.path.join(os.path.dirname(__file__), "parse_debug.log")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(f"[_regenerate_with_feedback]\nLLM返回: {response.content[:3000]}\n")
        return self._parse_blueprint(response.content)

    def compile_to_instructions(
        self,
        blueprint: StrategyBlueprint,
        rag_context: Dict[str, Any],
    ) -> WritingInstructions:
        """
        将策略蓝图编译为写作指令

        核心职责：
        - 将JSON蓝图转为RAGWriter可用的完整提示词
        - 保持"策略"与"事实"的清晰分离

        Args:
            blueprint: 策略蓝图
            rag_context: RAG上下文（事实内容）

        Returns:
            WritingInstructions: 可执行的写作指令
        """
        compiler = StrategyCompiler(self.llm_client, temperature=self.temperature)
        return compiler.compile(blueprint, rag_context)

    def write_with_blueprint(
        self,
        topic: str,
        rag_context: Dict[str, Any],
        content_type: Optional[str] = None,
        target_audience: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        compile_only: bool = False,
    ) -> Dict[str, Any]:
        """
        完整的写作策略流程

        Args:
            topic: 写作话题
            rag_context: RAG上下文
            content_type: 内容类型
            target_audience: 目标受众
            constraints: 额外约束
            compile_only: 是否仅返回指令（True）或包含蓝图（False）

        Returns:
            {
                "blueprint": StrategyBlueprint,
                "instructions": WritingInstructions,
                "case_references": [...],
            }
        """
        # 1. 生成策略蓝图
        blueprint = self.generate_blueprint(
            topic=topic,
            rag_context=rag_context,
            content_type=content_type,
            target_audience=target_audience,
            constraints=constraints,
        )

        result = {
            "blueprint": blueprint,
            "case_references": blueprint.meta.get("case_references", []),
        }

        # 2. 编译为写作指令
        instructions = self.compile_to_instructions(blueprint, rag_context)
        result["instructions"] = instructions

        if compile_only:
            return result

        return result

    def get_case_base_stats(self) -> Dict[str, Any]:
        """获取案例库统计信息"""
        return self.case_base.get_collection_stats()
