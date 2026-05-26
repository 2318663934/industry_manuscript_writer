#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
写作Skill智能体模块

扮演"策略导师/架构师"角色，通过策略案例库学习优质文章的写作方法，
为RAG写作系统提供结构化的写作策略指导。
"""

from .models import (
    StrategyBlueprint,
    StrategyCase,
    SectionStrategy,
    OpeningStrategy,
    ClosingStrategy,
    WritingTone,
    ReflectionResult,
    WritingInstructions,
)
from .agent import SkillAgent
from .case_base import CaseBaseManager
from .compiler import StrategyCompiler
from .annotator import StrategyAnnotator, batch_annotate

__all__ = [
    # 核心数据模型
    "StrategyBlueprint",
    "StrategyCase",
    "SectionStrategy",
    "OpeningStrategy",
    "ClosingStrategy",
    "WritingTone",
    "ReflectionResult",
    "WritingInstructions",
    # 核心类
    "SkillAgent",
    "CaseBaseManager",
    "StrategyCompiler",
    # 标注工具
    "StrategyAnnotator",
    "batch_annotate",
]
