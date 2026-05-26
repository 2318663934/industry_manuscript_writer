#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Self-Reflection校验模块

让模型生成后，再审视自身的输出，检查策略的一致性、完整性、可执行性。
"""

import json
import re
from typing import List, Tuple, Optional, Dict, Any

from .models import (
    StrategyBlueprint,
    ReflectionResult,
    IssueItem,
)


# 校验提示词模板
REFLECTION_SYSTEM_PROMPT = """【角色定义】
你是一位资深编辑审核专家，负责校验策略蓝图的质量。

【校验维度】
1. 结构完整性：章节数量是否合理（3-5节），各节是否有实质内容
2. 逻辑一致性：节与节之间是否递进，与核心张力是否一致
3. 可执行性：策略描述是否具体可执行，避免空洞描述
4. 事实一致性：策略中的论点是否能被RAG上下文支撑（如果提供）
5. 创新性：是否有独特的切入角度

【输出标准】
仅输出JSON格式的校验结果：
- 如果通过校验：{"is_valid": true, "overall_score": 0.85, "confidence_adjustment": 0.05, "issues": [], "suggestions": []}
- 如果需要修改：{"is_valid": false, "overall_score": 0.6, "confidence_adjustment": -0.1, "issues": [{"issue_type": "...", "location": "...", "description": "...", "severity": "..."}], "suggestions": ["..."]}

注意：
- overall_score是0-1的综合评分
- confidence_adjustment是基于校验结果的置信度调整（-0.5到0.5）
- issues中每个问题需要包含issue_type/description/severity"""


class SelfReflectionValidator:
    """
    Self-Reflection校验机制

    原理：
    - 让模型生成后，再让模型审视自身的输出
    - 检查策略的一致性、完整性、可执行性
    - 发现问题则调整置信度或标记问题
    """

    def __init__(
        self,
        llm_client: Any,
        temperature: float = 0.3,
    ):
        """
        初始化校验器

        Args:
            llm_client: LLM客户端
            temperature: 校验用温度（较低以保证稳定性）
        """
        self.llm_client = llm_client
        self.temperature = temperature

    def validate(
        self,
        blueprint: StrategyBlueprint,
        rag_context: Optional[str] = None,
    ) -> ReflectionResult:
        """
        校验策略蓝图

        Args:
            blueprint: 待校验的策略蓝图
            rag_context: RAG上下文（用于事实一致性校验，可选）

        Returns:
            ReflectionResult: 校验结果
        """
        # 首先进行规则层检查
        rule_check_passed, rule_issues = self._rule_based_check(blueprint)

        if not rule_check_passed:
            # 规则检查失败，直接返回问题
            return ReflectionResult(
                is_valid=False,
                issues=rule_issues,
                suggestions=self._generate_suggestions(rule_issues),
                confidence_adjustment=-0.2,
                overall_score=0.4,
            )

        # LLM辅助校验
        try:
            return self._llm_validate(blueprint, rag_context)
        except Exception as e:
            # LLM校验失败，使用规则检查结果
            print(f"LLM校验失败: {e}，使用规则检查结果")
            return ReflectionResult(
                is_valid=len(rule_issues) == 0,
                issues=rule_issues,
                suggestions=self._generate_suggestions(rule_issues),
                confidence_adjustment=-0.1 if rule_issues else 0,
                overall_score=0.7 if not rule_issues else 0.5,
            )

    def _rule_based_check(
        self,
        blueprint: StrategyBlueprint,
    ) -> Tuple[bool, List[IssueItem]]:
        """
        基于规则的快速检查

        检查：
        1. 章节数量是否在3-5之间
        2. 核心张力是否为空
        3. 各节content_focus是否为空
        4. forbidden_patterns是否为空（警告）

        Returns:
            (是否通过, 问题列表)
        """
        issues = []

        # 检查章节数量
        if len(blueprint.sections) < 3:
            issues.append(IssueItem(
                issue_type="完整性",
                location="sections",
                description=f"章节数量不足：当前{len(blueprint.sections)}节，建议3-5节",
                severity="critical",
            ))
        elif len(blueprint.sections) > 6:
            issues.append(IssueItem(
                issue_type="完整性",
                location="sections",
                description=f"章节数量过多：当前{len(blueprint.sections)}节，建议不超过6节",
                severity="warning",
            ))

        # 检查核心张力
        if not blueprint.core_tension or len(blueprint.core_tension.strip()) < 5:
            issues.append(IssueItem(
                issue_type="完整性",
                location="core_tension",
                description="核心张力缺失或过于简短",
                severity="critical",
            ))

        # 检查各节content_focus
        for i, section in enumerate(blueprint.sections):
            if not section.content_focus or len(section.content_focus.strip()) < 5:
                issues.append(IssueItem(
                    issue_type="可执行性",
                    location=f"sections[{i}]",
                    description=f"章节'{section.title}'的content_focus缺失或过于简短",
                    severity="warning",
                ))

        # 检查forbidden_patterns（建议有）
        if not blueprint.forbidden_patterns:
            issues.append(IssueItem(
                issue_type="可执行性",
                location="forbidden_patterns",
                description="未指定禁止的套话模式，可能导致文章出现AI味",
                severity="info",
            ))

        return len([i for i in issues if i.severity == "critical"]) == 0, issues

    def _llm_validate(
        self,
        blueprint: StrategyBlueprint,
        rag_context: Optional[str] = None,
    ) -> ReflectionResult:
        """
        使用LLM进行深度校验

        Args:
            blueprint: 待校验的策略蓝图
            rag_context: RAG上下文

        Returns:
            ReflectionResult: 校验结果
        """
        # 构建校验提示词
        blueprint_json = json.dumps(blueprint.model_dump(), ensure_ascii=False, indent=2)

        user_prompt = f"""## 待校验策略蓝图

```json
{blueprint_json}
```

"""

        if rag_context:
            user_prompt += f"""
## RAG上下文（用于事实一致性检查）

{rag_context}

**注意**：如果RAG上下文不足以支撑某论点，请标记为事实一致性问题。

"""

        # 调用LLM
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                system_prompt=REFLECTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=self.temperature,
            )
        else:
            response = self.llm_client.generate(
                f"{REFLECTION_SYSTEM_PROMPT}\n\n{user_prompt}",
                temperature=self.temperature,
            )

        # 解析结果
        return self._parse_result(response.content, blueprint)

    def _parse_result(
        self,
        result_text: str,
        original_blueprint: StrategyBlueprint,
    ) -> ReflectionResult:
        """解析LLM校验结果"""
        text = result_text.strip()

        # 尝试提取JSON
        try:
            # 直接解析
            data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取代码块
            json_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    data = None
            else:
                # 尝试提取{ ... }
                brace_start = text.find('{')
                brace_end = text.rfind('}')
                if brace_start != -1 and brace_end > brace_start:
                    try:
                        data = json.loads(text[brace_start:brace_end + 1])
                    except json.JSONDecodeError:
                        data = None
                else:
                    data = None

        if data is None:
            raise ValueError(f"无法解析校验结果: {result_text[:200]}")

        # 构建结果
        issues = []
        for issue_data in data.get("issues", []):
            issues.append(IssueItem(**issue_data))

        return ReflectionResult(
            is_valid=data.get("is_valid", False),
            issues=issues,
            suggestions=data.get("suggestions", []),
            confidence_adjustment=data.get("confidence_adjustment", 0),
            overall_score=data.get("overall_score", 0.5),
        )

    def _generate_suggestions(self, issues: List[IssueItem]) -> List[str]:
        """根据问题生成修改建议"""
        suggestions = []

        for issue in issues:
            if issue.issue_type == "完整性":
                if "章节数量" in issue.description:
                    suggestions.append("建议调整章节数量至3-5节之间")
            elif issue.issue_type == "可执行性":
                if "content_focus" in issue.description:
                    suggestions.append("请为各章节补充具体的content_focus描述")
            elif issue.issue_type == "一致性":
                suggestions.append("请检查章节之间的逻辑递进关系")

        return suggestions


def quick_validate(blueprint: StrategyBlueprint) -> Tuple[bool, List[str]]:
    """
    快速校验（仅规则检查，不调用LLM）

    Args:
        blueprint: 策略蓝图

    Returns:
        (是否通过, 问题描述列表)
    """
    validator = SelfReflectionValidator(llm_client=None)
    passed, issues = validator._rule_based_check(blueprint)
    return passed, [i.description for i in issues]
