#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG写作系统

基于检索增强生成的行业稿件写作系统
"""

from .config import settings, Settings
from .document_parser import parse_document, extract_topic_from_text, DocumentParserFactory
from .retriever import VectorRetriever, TextRetriever, HybridRetriever
from .prompt_engineering import (
    PromptBuilder, FewShotPromptBuilder, DeepBriefPromptBuilder,
    DeepArticlePromptBuilder, OutlinePromptBuilder, WritingTask, KnowledgeContext,
    OutlineSection
)
from .llm_client import create_llm_client, LLMClientFactory, BaseLLMClient
from .engine import RAGWriter, create_writer, WritingResult, OutlineResult
from .supplementary_loader import (
    SupplementaryMaterial, SupplementaryLoader, load_supplementary_materials
)

__version__ = "0.1.0"

__all__ = [
    # 配置
    "settings",
    "Settings",
    # 文档解析
    "parse_document",
    "extract_topic_from_text",
    "DocumentParserFactory",
    # 检索
    "VectorRetriever",
    "TextRetriever",
    "HybridRetriever",
    # 提示词
    "PromptBuilder",
    "FewShotPromptBuilder",
    "DeepBriefPromptBuilder",
    "DeepArticlePromptBuilder",
    "OutlinePromptBuilder",
    "WritingTask",
    "KnowledgeContext",
    "OutlineSection",
    # LLM
    "create_llm_client",
    "LLMClientFactory",
    "BaseLLMClient",
    # 引擎
    "RAGWriter",
    "create_writer",
    "WritingResult",
    "OutlineResult",
    # 补充资料
    "SupplementaryMaterial",
    "SupplementaryLoader",
    "load_supplementary_materials",
]
