#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG写作引擎 - 主流程编排
"""
import json
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterator
from dataclasses import dataclass, asdict
from datetime import datetime

# 设置HuggingFace镜像（解决网络下载模型问题）
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')

from sentence_transformers import SentenceTransformer

from .config import settings
from .document_parser import parse_document, extract_topic_from_text
from .retriever import VectorRetriever, TextRetriever, HybridRetriever, KnowledgeItem
from .prompt_engineering import (
    PromptBuilder, FewShotPromptBuilder, DeepBriefPromptBuilder,
    DeepArticlePromptBuilder, WritingTask, KnowledgeContext
)
from .llm_client import create_llm_client, BaseLLMClient
from .style_injector import get_style_injection
from .supplementary_loader import (
    SupplementaryMaterial, SupplementaryLoader, load_supplementary_materials
)


@dataclass
class WritingResult:
    """写作结果"""
    article: str
    topic: str
    model: str
    knowledge_count: int
    knowledge_sources: List[Dict[str, str]]
    usage: Dict[str, int]
    generation_time: float
    raw_response: Optional[Dict[str, Any]] = None
    supplementary_count: int = 0
    supplementary_sources: List[Dict[str, str]] = None

    def __post_init__(self):
        if self.supplementary_sources is None:
            self.supplementary_sources = []


@dataclass
class OutlineSection:
    """大纲章节结构"""
    title: str
    description: str
    citations: List[Dict[str, str]]
    word_count_estimate: int


@dataclass
class OutlineResult:
    """大纲生成结果"""
    outline: str  # 完整大纲（Markdown格式）
    sections: List[OutlineSection]
    title: str  # 文章标题
    topic: str  # 话题
    model: str  # 使用的模型
    knowledge_sources: List[Dict[str, str]]
    supplementary_sources: List[Dict[str, str]]
    usage: Dict[str, int]
    generation_time: float
    raw_response: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.supplementary_sources is None:
            self.supplementary_sources = []


class RAGWriter:
    """RAG写作引擎"""

    def __init__(
        self,
        articles_json: Optional[str] = None,
        use_few_shot: bool = False,
        deep_brief: bool = False,
        llm_provider: Optional[str] = None,
        embedding_model_name: Optional[str] = None,
    ):
        """
        初始化RAG写作引擎

        Args:
            articles_json: 文章JSON文件路径（用于全文检索和获取完整文章内容）
            use_few_shot: 是否使用Few-shot提示词
            deep_brief: 是否使用B端深度稿件提示词工程
            llm_provider: LLM提供商
            embedding_model_name: Embedding模型名称
        """
        self._embedding_model = None
        self._embedding_model_name = embedding_model_name or settings.embedding.model_name
        self.deep_brief = deep_brief
        self.use_few_shot = use_few_shot
        self.articles_json = articles_json

        # 初始化向量检索器（传入articles_json以获取完整文章内容）
        self.vector_retriever = VectorRetriever(articles_json=articles_json)

        # 初始化文本检索器（如果提供了文章数据）
        self.text_retriever = None
        if articles_json:
            from .retriever import load_articles_from_json
            articles = load_articles_from_json(articles_json)
            if articles:
                self.text_retriever = TextRetriever(articles)

        # 初始化混合检索器
        self.hybrid_retriever = None
        if self.text_retriever:
            self.hybrid_retriever = HybridRetriever(
                self.vector_retriever,
                self.text_retriever,
                articles_json=articles_json,
            )

        # 初始化提示词构建器
        if deep_brief:
            self.prompt_builder = DeepBriefPromptBuilder()
        elif use_few_shot:
            self.prompt_builder = FewShotPromptBuilder()
        else:
            self.prompt_builder = PromptBuilder()

        # 初始化LLM客户端
        self.llm_client = create_llm_client(llm_provider)

    @property
    def embedding_model(self) -> SentenceTransformer:
        """获取Embedding模型（懒加载）"""
        if self._embedding_model is None:
            print(f"加载Embedding模型: {self._embedding_model_name}...")
            self._embedding_model = SentenceTransformer(self._embedding_model_name)
            print("Embedding模型加载完成")
        return self._embedding_model

    def check_status(self) -> Dict[str, Any]:
        """检查系统状态"""
        status = {
            "embedding_model": self._embedding_model_name,
            "embedding_loaded": self._embedding_model is not None,
            "llm_provider": settings.llm.provider,
            "llm_model": settings.llm.model,
        }

        # Milvus状态
        try:
            milvus_stats = self.vector_retriever.get_collection_stats()
            status["milvus"] = milvus_stats
        except Exception as e:
            status["milvus"] = {"error": str(e)}

        # 文本检索状态
        if self.text_retriever:
            status["text_retriever"] = {
                "articles_count": len(self.text_retriever.articles)
            }
        else:
            status["text_retriever"] = {"status": "not_configured"}

        return status

    def retrieve_knowledge(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_hybrid: bool = True,
    ) -> List[KnowledgeContext]:
        """
        检索相关知识

        Args:
            query: 查询文本
            top_k: 召回数量
            use_hybrid: 是否使用混合检索

        Returns:
            知识上下文列表
        """
        if top_k is None:
            top_k = settings.milvus.top_k

        if use_hybrid and self.hybrid_retriever:
            # 混合检索
            print(f"使用混合检索，查询: {query[:50]}...")
            results = self.hybrid_retriever.search(
                query,
                self.embedding_model,
                top_k=top_k,
            )
        else:
            # 仅向量检索
            print(f"使用向量检索，查询: {query[:50]}...")
            results = self.vector_retriever.search_by_text(
                query,
                self.embedding_model,
                top_k=top_k,
            )

        # 转换为KnowledgeContext
        knowledge_items = []
        for res in results:
            if isinstance(res, KnowledgeItem):
                # 向量检索结果
                item = KnowledgeContext(
                    title=res.title,
                    url=res.url,
                    author=res.author,
                    date=res.date,
                    content=res.content or "",  # 现在应该包含完整内容
                )
            else:
                # 混合检索结果 - 使用完整内容而不是content_preview
                item = KnowledgeContext(
                    title=res.get('title', ''),
                    url=res.get('url', ''),
                    author=res.get('author', ''),
                    date=res.get('date', ''),
                    content=res.get('content', ''),  # 完整内容
                )
            knowledge_items.append(item)

        print(f"检索到 {len(knowledge_items)} 条相关知识")
        return knowledge_items

    def write(
        self,
        topic: str,
        requirements: str = "",
        keywords: Optional[List[str]] = None,
        style: Optional[str] = None,
        length: Optional[str] = None,
        knowledge: Optional[List[KnowledgeContext]] = None,
        target_audience: Optional[str] = None,
        perspective: Optional[str] = None,
        top_k: Optional[int] = None,
        supplementary_sources: Optional[List[str]] = None,
        **llm_kwargs,
    ) -> WritingResult:
        """
        执行写作任务

        Args:
            topic: 话题/主题
            requirements: 具体要求
            keywords: 关键词列表
            style: 写作风格
            length: 字数要求
            knowledge: 知识上下文（如果不提供则自动检索）
            target_audience: 目标受众（deep_brief模式）
            perspective: 内容站位（deep_brief模式）
            top_k: 检索知识数量
            supplementary_sources: 补充资料列表，可以是:
                - 文件路径 (TXT, DOCX, PDF, Excel)
                - URL链接 (微信文章等)
                - 纯文本内容
            **llm_kwargs: 传递给LLM的其他参数

        Returns:
            写作结果
        """
        start_time = time.time()

        # 如果没有提供知识，自动检索
        if knowledge is None:
            # 构建检索查询（只用 topic 和 keywords，不含 requirements，避免需求文件内容干扰搜索）
            search_query = f"{topic} {' '.join(keywords or [])}"
            knowledge = self.retrieve_knowledge(search_query, top_k=top_k)

        # 加载补充资料
        supplementary_materials = []
        if supplementary_sources:
            print(f"加载 {len(supplementary_sources)} 份补充资料...")
            loader = SupplementaryLoader()
            supplementary_materials = loader.load(supplementary_sources)
            print(f"补充资料加载完成: {len(supplementary_materials)} 份")

            # 将补充资料转换为KnowledgeContext并合并
            for mat in supplementary_materials:
                knowledge.append(mat.to_knowledge_context())

        # 构建写作任务
        task = WritingTask(
            topic=topic,
            requirements=requirements,
            keywords=keywords or [],
            style=style,
            length=length,
            target_audience=target_audience,
            perspective=perspective,
        )

        # 构建提示词
        if self.deep_brief:
            # deep_brief模式：使用深度Brief构建器
            prompt = self.prompt_builder.build_deep_brief_prompt(task, knowledge)
        else:
            prompt = self.prompt_builder.build_prompt(task, knowledge)

        # 调用LLM生成
        print("正在生成内容...")
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                prompt["system"],
                prompt["user"],
                **llm_kwargs,
            )
        else:
            combined_prompt = f"{prompt['system']}\n\n{prompt['user']}"
            response = self.llm_client.generate(combined_prompt, **llm_kwargs)

        generation_time = time.time() - start_time

        # 构建来源信息（区分数据库检索和补充资料）
        # knowledge包含两部分：数据库检索结果 + 补充资料
        # 需要区分它们
        db_knowledge_count = len(knowledge) - len(supplementary_materials) if supplementary_materials else len(knowledge)

        # 分离数据库来源和补充资料来源
        db_sources = []
        supp_sources = []

        if db_knowledge_count > 0 and knowledge:
            for k in knowledge[:db_knowledge_count]:
                db_sources.append({
                    "title": k.title,
                    "author": k.author,
                    "date": k.date,
                    "url": k.url,
                })

        if supplementary_materials:
            for mat in supplementary_materials:
                supp_sources.append({
                    "title": mat.title,
                    "author": mat.author,
                    "date": mat.date,
                    "url": mat.source if mat.source_type == 'url' else '',
                    "source": mat.source,
                    "source_type": mat.source_type,
                })

        all_sources = db_sources + supp_sources

        return WritingResult(
            article=response.content,
            topic=topic,
            model=response.model,
            knowledge_count=len(knowledge),
            knowledge_sources=all_sources,
            usage=response.usage,
            generation_time=generation_time,
            raw_response=response.raw_response,
            supplementary_count=len(supplementary_materials),
            supplementary_sources=supp_sources,
        )

    def generate_deep_brief(
        self,
        topic: str,
        requirements: str = "",
        keywords: Optional[List[str]] = None,
        length: Optional[str] = None,
        knowledge: Optional[List[KnowledgeContext]] = None,
        target_audience: Optional[str] = None,
        perspective: Optional[str] = None,
        min_dimensions: int = 5,
        top_k: Optional[int] = None,
        supplementary_sources: Optional[List[str]] = None,
        **llm_kwargs,
    ) -> WritingResult:
        """
        生成深度Brief（而非直接写文章）

        Args:
            topic: 话题/主题
            requirements: 具体要求
            keywords: 关键词列表
            length: 字数要求
            knowledge: 知识上下文（如果不提供则自动检索）
            target_audience: 目标受众
            perspective: 内容站位
            min_dimensions: 最少发散维度数（默认5）
            top_k: 检索知识数量
            supplementary_sources: 补充资料列表
            **llm_kwargs: 传递给LLM的其他参数

        Returns:
            包含深度Brief的写作结果
        """
        start_time = time.time()

        # 如果没有提供知识，自动检索（只用 topic 和 keywords，不含 requirements）
        if knowledge is None:
            search_query = f"{topic} {' '.join(keywords or [])}"
            knowledge = self.retrieve_knowledge(search_query, top_k=top_k)

        # 加载补充资料
        supplementary_materials = []
        if supplementary_sources:
            print(f"加载 {len(supplementary_sources)} 份补充资料...")
            loader = SupplementaryLoader()
            supplementary_materials = loader.load(supplementary_sources)
            print(f"补充资料加载完成: {len(supplementary_materials)} 份")

            for mat in supplementary_materials:
                knowledge.append(mat.to_knowledge_context())

        # 构建写作任务
        task = WritingTask(
            topic=topic,
            requirements=requirements,
            keywords=keywords or [],
            length=length,
            target_audience=target_audience,
            perspective=perspective,
            min_dimensions=min_dimensions,
        )

        # 使用DeepBriefPromptBuilder构建提示词
        deep_brief_builder = DeepBriefPromptBuilder()
        prompt = deep_brief_builder.build_deep_brief_prompt(task, knowledge)

        print("正在生成深度Brief...")
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                prompt["system"],
                prompt["user"],
                **llm_kwargs,
            )
        else:
            combined_prompt = f"{prompt['system']}\n\n{prompt['user']}"
            response = self.llm_client.generate(combined_prompt, **llm_kwargs)

        generation_time = time.time() - start_time

        # 构建来源信息
        db_knowledge_count = len(knowledge) - len(supplementary_materials) if supplementary_materials else len(knowledge)

        db_sources = []
        supp_sources = []

        if db_knowledge_count > 0 and knowledge:
            for k in knowledge[:db_knowledge_count]:
                db_sources.append({
                    "title": k.title,
                    "author": k.author,
                    "date": k.date,
                    "url": k.url,
                })

        if supplementary_materials:
            for mat in supplementary_materials:
                supp_sources.append({
                    "title": mat.title,
                    "author": mat.author,
                    "date": mat.date,
                    "url": mat.source if mat.source_type == 'url' else '',
                    "source": mat.source,
                    "source_type": mat.source_type,
                })

        all_sources = db_sources + supp_sources

        return WritingResult(
            article=response.content,
            topic=topic,
            model=response.model,
            knowledge_count=len(knowledge),
            knowledge_sources=all_sources,
            usage=response.usage,
            generation_time=generation_time,
            raw_response=response.raw_response,
            supplementary_count=len(supplementary_materials),
            supplementary_sources=supp_sources,
        )

    def write_from_file(
        self,
        file_path: str,
        **kwargs,
    ) -> WritingResult:
        """
        从文件执行写作任务

        Args:
            file_path: 文件路径（.txt 或 .docx）
            **kwargs: 其他写作参数

        Returns:
            写作结果
        """
        print(f"解析文件: {file_path}")
        content = parse_document(file_path)

        # 提取话题信息
        topic_info = extract_topic_from_text(content)

        print(f"提取话题: {topic_info['topic'][:100]}...")
        print(f"关键词: {topic_info['keywords']}")

        return self.write(
            topic=topic_info['topic'],
            keywords=topic_info['keywords'],
            **kwargs,
        )

    def revise(
        self,
        article: str,
        requirements: str,
        **llm_kwargs,
    ) -> str:
        """
        修改文章

        Args:
            article: 原文
            requirements: 修改要求
            **llm_kwargs: 其他参数

        Returns:
            修改后的文章
        """
        prompt = self.prompt_builder.build_revision_prompt(article, requirements)

        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                prompt["system"],
                prompt["user"],
                **llm_kwargs,
            )
        else:
            combined_prompt = f"{prompt['system']}\n\n{prompt['user']}"
            response = self.llm_client.generate(combined_prompt, **llm_kwargs)

        return response.content

    def write_stream(
        self,
        topic: str,
        requirements: str = "",
        keywords: Optional[List[str]] = None,
        **llm_kwargs,
    ) -> Iterator[str]:
        """
        流式写作

        Args:
            topic: 话题/主题
            requirements: 具体要求
            keywords: 关键词列表
            **llm_kwargs: 其他参数

        Yields:
            生成的文本片段
        """
        # 检索知识（只用 topic 和 keywords，不含 requirements）
        search_query = f"{topic} {' '.join(keywords or [])}"
        knowledge = self.retrieve_knowledge(search_query)

        # 构建写作任务
        task = WritingTask(
            topic=topic,
            requirements=requirements,
            keywords=keywords or [],
        )

        # 构建提示词
        prompt = self.prompt_builder.build_prompt(task, knowledge)
        combined_prompt = f"{prompt['system']}\n\n{prompt['user']}"

        # 流式生成
        for chunk in self.llm_client.generate_stream(combined_prompt, **llm_kwargs):
            yield chunk

    def generate_outline(
        self,
        topic: str,
        requirements: str = "",
        keywords: Optional[List[str]] = None,
        length: Optional[str] = None,
        knowledge: Optional[List[KnowledgeContext]] = None,
        target_audience: Optional[str] = None,
        perspective: Optional[str] = None,
        min_dimensions: int = 5,
        top_k: Optional[int] = None,
        supplementary_sources: Optional[List[str]] = None,
        **llm_kwargs,
    ) -> OutlineResult:
        """
        生成文章大纲

        Args:
            topic: 话题/主题
            requirements: 具体要求
            keywords: 关键词列表
            length: 字数要求
            knowledge: 知识上下文（如果不提供则自动检索）
            target_audience: 目标受众
            perspective: 内容站位
            min_dimensions: 最少发散维度数（默认5）
            top_k: 检索知识数量
            supplementary_sources: 补充资料列表
            **llm_kwargs: 传递给LLM的其他参数

        Returns:
            大纲生成结果
        """
        start_time = time.time()

        # 如果没有提供知识，自动检索（只用 topic 和 keywords，不含 requirements）
        if knowledge is None:
            search_query = f"{topic} {' '.join(keywords or [])}"
            knowledge = self.retrieve_knowledge(search_query, top_k=top_k)

        # 加载补充资料
        supplementary_materials = []
        if supplementary_sources:
            print(f"加载 {len(supplementary_sources)} 份补充资料...")
            loader = SupplementaryLoader()
            supplementary_materials = loader.load(supplementary_sources)
            print(f"补充资料加载完成: {len(supplementary_materials)} 份")

            for mat in supplementary_materials:
                knowledge.append(mat.to_knowledge_context())

        # 构建写作任务
        task = WritingTask(
            topic=topic,
            requirements=requirements,
            keywords=keywords or [],
            length=length,
            target_audience=target_audience,
            perspective=perspective,
            min_dimensions=min_dimensions,
        )

        # 使用OutlinePromptBuilder构建提示词
        from .prompt_engineering import OutlinePromptBuilder
        outline_builder = OutlinePromptBuilder()
        prompt = outline_builder.build_outline_prompt(task, knowledge)

        print("正在生成大纲...")
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                prompt["system"],
                prompt["user"],
                **llm_kwargs,
            )
        else:
            combined_prompt = f"{prompt['system']}\n\n{prompt['user']}"
            response = self.llm_client.generate(combined_prompt, **llm_kwargs)

        generation_time = time.time() - start_time

        # 解析大纲章节
        sections = outline_builder.parse_outline_sections(response.content)

        # 提取文章标题
        title = topic
        if "【文章标题】" in response.content:
            title_line = [l for l in response.content.split('\n') if '【文章标题】' in l]
            if title_line:
                title = title_line[0].split('】', 1)[-1].strip()

        # 构建来源信息
        db_knowledge_count = len(knowledge) - len(supplementary_materials) if supplementary_materials else len(knowledge)

        db_sources = []
        supp_sources = []

        if db_knowledge_count > 0 and knowledge:
            for k in knowledge[:db_knowledge_count]:
                db_sources.append({
                    "title": k.title,
                    "author": k.author,
                    "date": k.date,
                    "url": k.url,
                })

        if supplementary_materials:
            for mat in supplementary_materials:
                supp_sources.append({
                    "title": mat.title,
                    "author": mat.author,
                    "date": mat.date,
                    "url": mat.source if mat.source_type == 'url' else '',
                    "source": mat.source,
                    "source_type": mat.source_type,
                })

        all_sources = db_sources + supp_sources

        return OutlineResult(
            outline=response.content,
            sections=sections,
            title=title,
            topic=topic,
            model=response.model,
            knowledge_sources=all_sources,
            supplementary_sources=supp_sources,
            usage=response.usage,
            generation_time=generation_time,
            raw_response=response.raw_response,
        )

    def revise_outline(
        self,
        original_outline: str,
        feedback: str = "",
        revised_outline: Optional[str] = None,
        knowledge: Optional[List[KnowledgeContext]] = None,
        supplementary_sources: Optional[List[str]] = None,
        **llm_kwargs,
    ) -> OutlineResult:
        """
        修订大纲

        Args:
            original_outline: 原大纲
            feedback: 用户修改意见
            revised_outline: 直接编辑的大纲（优先于feedback）
            knowledge: 知识上下文
            supplementary_sources: 补充资料列表
            **llm_kwargs: 传递给LLM的其他参数

        Returns:
            修订后的大纲结果
        """
        start_time = time.time()

        # 如果直接提供了编辑后的大纲，不需要调用LLM
        if revised_outline:
            from .prompt_engineering import OutlinePromptBuilder
            outline_builder = OutlinePromptBuilder()
            sections = outline_builder.parse_outline_sections(revised_outline)

            # 提取标题
            title = "未命名"
            if "【文章标题】" in revised_outline:
                title_line = [l for l in revised_outline.split('\n') if '【文章标题】' in l]
                if title_line:
                    title = title_line[0].split('】', 1)[-1].strip()

            return OutlineResult(
                outline=revised_outline,
                sections=sections,
                title=title,
                topic="",
                model=self.llm_client.model if hasattr(self.llm_client, 'model') else "unknown",
                knowledge_sources=[],
                supplementary_sources=[],
                usage={},
                generation_time=time.time() - start_time,
            )

        # 加载补充资料以获取知识上下文
        supplementary_materials = []
        if supplementary_sources:
            loader = SupplementaryLoader()
            supplementary_materials = loader.load(supplementary_sources)

            if knowledge is None:
                knowledge = []
            for mat in supplementary_materials:
                knowledge.append(mat.to_knowledge_context())

        # 使用OutlinePromptBuilder构建修订提示词
        from .prompt_engineering import OutlinePromptBuilder
        outline_builder = OutlinePromptBuilder()
        prompt = outline_builder.build_revision_prompt(original_outline, feedback, knowledge or [])

        print("正在修订大纲...")
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                prompt["system"],
                prompt["user"],
                **llm_kwargs,
            )
        else:
            combined_prompt = f"{prompt['system']}\n\n{prompt['user']}"
            response = self.llm_client.generate(combined_prompt, **llm_kwargs)

        generation_time = time.time() - start_time

        # 解析大纲章节
        sections = outline_builder.parse_outline_sections(response.content)

        # 提取文章标题
        title = "未命名"
        if "【文章标题】" in response.content:
            title_line = [l for l in response.content.split('\n') if '【文章标题】' in l]
            if title_line:
                title = title_line[0].split('】', 1)[-1].strip()

        # 构建来源信息
        supp_sources = []
        if supplementary_materials:
            for mat in supplementary_materials:
                supp_sources.append({
                    "title": mat.title,
                    "author": mat.author,
                    "date": mat.date,
                    "url": mat.source if mat.source_type == 'url' else '',
                    "source": mat.source,
                    "source_type": mat.source_type,
                })

        return OutlineResult(
            outline=response.content,
            sections=sections,
            title=title,
            topic="",
            model=response.model,
            knowledge_sources=[],
            supplementary_sources=supp_sources,
            usage=response.usage,
            generation_time=generation_time,
            raw_response=response.raw_response,
        )

    def write_from_outline(
        self,
        outline: str,
        topic: str,
        supplementary_sources: Optional[List[str]] = None,
        **llm_kwargs,
    ) -> WritingResult:
        """
        根据大纲写文章

        Args:
            outline: 确认的大纲
            topic: 话题/主题
            supplementary_sources: 补充资料列表
            **llm_kwargs: 传递给LLM的其他参数

        Returns:
            写作结果
        """
        start_time = time.time()

        # 检索RAG知识素材（用于写作阶段的全文参考）
        print(f"检索相关知识素材...")
        knowledge = self.retrieve_knowledge(topic, top_k=5)

        # 加载补充资料
        supplementary_materials = []
        if supplementary_sources:
            print(f"加载 {len(supplementary_sources)} 份补充资料...")
            loader = SupplementaryLoader()
            supplementary_materials = loader.load(supplementary_sources)
            print(f"补充资料加载完成: {len(supplementary_materials)} 份")
            for mat in supplementary_materials:
                knowledge.append(mat.to_knowledge_context())

        # 构建系统提示词
        system_prompt = """你是一位资深的行业内容创作者，擅长撰写专业、有深度且读起来自然的行业分析文章。

你的写作风格:
- 专业但不晦涩，用通俗易懂的语言解释专业概念
- 有自己独立的观点和见解，不做简单的信息堆砌
- 善于使用具体案例、数据和故事来支撑观点
- 文章结构清晰，逻辑连贯，段落之间过渡自然
- 语言有节奏感，长短句结合，读起来不枯燥

写作原则:
1. 避免AI常见的空洞套话（如"随着时代发展"、"众所周知"、"毋庸置疑"等）
2. 避免每句话都以"我们"开头
3. 避免重复使用相同的句式结构
4. 主动句为主，减少被动语态
5. 可以适当使用口语化表达和过渡词（如"话说回来"、"更重要的是"、"说起来"）
6. 避免文章开头就讲大道理，从具体案例或场景切入"""

        system_prompt += get_style_injection()

        # 构建用户提示词
        user_prompt = f"""## 文章大纲

请严格按照以下大纲撰写文章：

{outline}

## 写作要求

1. **文章必须以标题开头**：使用大纲中给出的"文章标题"作为全文标题，以`# `格式作为第一行
2. **严格按照大纲结构写作**，不要偏离主题
3. **每个章节都要有实质性内容**，避免空洞
4. **引用资料时要标注来源**，并在文末列出参考来源
5. **语言要自然流畅**，避免AI套话
6. **字数分配要合理**，体现内容重要性差异

请直接输出完整文章内容（以标题开头），不要加"以下是文章"之类的引导语。"""

        # 添加RAG检索到的知识素材全文（供写作时学习参考）
        if knowledge:
            from .prompt_engineering import PromptBuilder
            kb_builder = PromptBuilder()
            kb_text = kb_builder.build_knowledge_context(knowledge, max_chars=10000)
            if kb_text:
                user_prompt += f"\n\n## 参考素材全文（学习写作手法和细节）\n\n{kb_text}\n"

        print("正在根据大纲生成文章...")
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                system_prompt,
                user_prompt,
                **llm_kwargs,
            )
        else:
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self.llm_client.generate(combined_prompt, **llm_kwargs)

        generation_time = time.time() - start_time

        # 构建来源信息
        supp_sources = []
        if supplementary_materials:
            for mat in supplementary_materials:
                supp_sources.append({
                    "title": mat.title,
                    "author": mat.author,
                    "date": mat.date,
                    "url": mat.source if mat.source_type == 'url' else '',
                    "source": mat.source,
                    "source_type": mat.source_type,
                })

        return WritingResult(
            article=response.content,
            topic=topic,
            model=response.model,
            knowledge_count=0,
            knowledge_sources=[],
            usage=response.usage,
            generation_time=generation_time,
            raw_response=response.raw_response,
            supplementary_count=len(supplementary_materials),
            supplementary_sources=supp_sources,
        )

    def write_from_blueprint(
        self,
        blueprint,
        knowledge: Optional[List[KnowledgeContext]] = None,
        **llm_kwargs,
    ) -> WritingResult:
        """
        基于策略蓝图写作

        核心流程:
        1. 如果未提供knowledge，自动检索RAG上下文
        2. 使用StrategyCompiler将蓝图转为写作指令
        3. 调用LLM生成文章

        Args:
            blueprint: 策略蓝图（来自SkillAgent.generate_blueprint()）
            knowledge: RAG上下文（如果为None则自动检索）
            **llm_kwargs: 其他LLM参数

        Returns:
            WritingResult: 写作结果
        """
        from .skill_agent.compiler import StrategyCompiler

        start_time = time.time()

        # 获取RAG上下文
        if knowledge is None:
            search_query = blueprint.topic if hasattr(blueprint, 'topic') else str(blueprint)
            knowledge = self.retrieve_knowledge(search_query)

        # 构建RAG上下文格式
        rag_context = {
            "knowledge": knowledge,
            "topic": blueprint.topic if hasattr(blueprint, 'topic') else "",
            "content_type": blueprint.content_type if hasattr(blueprint, 'content_type') else "",
        }

        # 编译策略蓝图为写作指令
        compiler = StrategyCompiler(
            llm_client=self.llm_client,
            temperature=llm_kwargs.get("temperature", 0.5),
        )

        instructions = compiler.compile(blueprint, rag_context)

        # 构建提示词
        system_prompt = f"""你是一位资深的行业内容创作者，擅长撰写专业、有深度且读起来自然的行业分析文章。

写作基调：{blueprint.writing_tone.value if hasattr(blueprint, 'writing_tone') else 'analytical'}

你的写作风格:
- 专业但不晦涩，用通俗易懂的语言解释专业概念
- 有自己独立的观点和见解，不做简单的信息堆砌
- 善于使用具体案例、数据和故事来支撑观点
- 文章结构清晰，逻辑连贯，段落之间过渡自然
- 语言有节奏感，长短句结合，读起来不枯燥

禁止的套话模式：
{chr(10).join([f"- {p}" for p in (blueprint.forbidden_patterns or [])])}

风格注意事项：
{(chr(10).join([f"- {n}" for n in (blueprint.global_style_notes or [])])) if hasattr(blueprint, 'global_style_notes') else "- 无特殊要求"}

请严格按照以下章节结构和写作指导撰写文章。文章必须以标题（使用`# `格式）开头。"""

        system_prompt += get_style_injection()

        user_prompt = instructions.instruction_text

        # 调用LLM
        print("正在基于策略蓝图生成文章...")
        if hasattr(self.llm_client, 'generate_with_system'):
            response = self.llm_client.generate_with_system(
                system_prompt,
                user_prompt,
                temperature=llm_kwargs.get("temperature", 0.5),
            )
        else:
            response = self.llm_client.generate(
                f"{system_prompt}\n\n{user_prompt}",
                temperature=llm_kwargs.get("temperature", 0.5),
            )

        generation_time = time.time() - start_time

        # 构建来源信息
        knowledge_sources = []
        for k in knowledge:
            knowledge_sources.append({
                "title": k.title,
                "author": k.author,
                "date": k.date,
                "url": k.url,
            })

        return WritingResult(
            article=response.content,
            topic=blueprint.topic if hasattr(blueprint, 'topic') else "",
            model=response.model,
            knowledge_count=len(knowledge),
            knowledge_sources=knowledge_sources,
            usage=response.usage,
            generation_time=generation_time,
            raw_response=response.raw_response,
        )

    def create_skill_agent(self, case_base_path: str = "./strategy_cases"):
        """
        创建SkillAgent实例（复用RAGWriter的LLM客户端和Embedding模型）

        Args:
            case_base_path: 策略案例库路径

        Returns:
            SkillAgent实例
        """
        from .skill_agent import SkillAgent, CaseBaseManager

        # 创建案例库管理器
        case_base = CaseBaseManager(
            base_path=case_base_path,
            milvus_client=None,  # 将使用默认连接
            embedding_model=self.embedding_model,
        )

        # 创建SkillAgent
        return SkillAgent(
            case_base=case_base,
            llm_client=self.llm_client,
            temperature=0.4,
            use_reflection=False,  # 暂时禁用reflection以避免token限制问题
        )


def create_writer(
    articles_json: Optional[str] = None,
    **kwargs,
) -> RAGWriter:
    """
    创建RAG写作引擎（便捷函数）

    Args:
        articles_json: 文章JSON文件路径
        **kwargs: 其他参数

    Returns:
        RAGWriter实例
    """
    return RAGWriter(articles_json=articles_json, **kwargs)


# 命令行入口
def main():
    import argparse

    parser = argparse.ArgumentParser(description="RAG写作引擎")
    parser.add_argument("input", help="输入文件路径或话题")
    parser.add_argument("--file", action="store_true", help="input是文件路径")
    parser.add_argument("--articles", "-a", help="文章JSON文件路径")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--provider", "-p", help="LLM提供商")
    parser.add_argument("--few-shot", action="store_true", help="使用Few-shot提示词")
    parser.add_argument("--top-k", type=int, default=5, help="检索数量")
    parser.add_argument("--show-sources", action="store_true", help="显示知识来源")
    parser.add_argument("--stream", action="store_true", help="流式输出")

    args = parser.parse_args()

    # 创建写作引擎
    writer = create_writer(
        articles_json=args.articles,
        use_few_shot=args.few_shot,
        llm_provider=args.provider,
    )

    # 检查状态
    print("=" * 50)
    print("系统状态检查")
    print("=" * 50)
    status = writer.check_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    print()

    # 确定输入方式
    if args.file:
        topic = args.input
        topic_info = extract_topic_from_text(parse_document(topic))
        topic = topic_info['topic']
        keywords = topic_info['keywords']
        print(f"从文件解析话题: {topic[:100]}...")
        print(f"关键词: {keywords}")
    else:
        topic = args.input
        keywords = None

    # 执行写作
    if args.stream:
        print("=" * 50)
        print("开始生成文章（流式）")
        print("=" * 50)
        for chunk in writer.write_stream(topic, keywords=keywords):
            print(chunk, end="", flush=True)
        print()
    else:
        result = writer.write(topic, keywords=keywords, top_k=args.top_k)

        print("=" * 50)
        print("生成完成")
        print("=" * 50)
        print(f"话题: {result.topic}")
        print(f"模型: {result.model}")
        print(f"知识来源: {result.knowledge_count}条")
        print(f"生成时间: {result.generation_time:.2f}秒")
        print(f"Token用量: {result.usage}")

        if args.show_sources:
            print("\n--- 知识来源 ---")
            for i, src in enumerate(result.knowledge_sources, 1):
                print(f"{i}. {src['title']}")
                print(f"   {src['author']} | {src['date']}")
                print(f"   {src['url']}")

        print("\n" + "=" * 50)
        print("生成的文章")
        print("=" * 50)
        print(result.article)

        # 保存到文件
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(f"# {result.topic}\n\n")
                f.write(result.article)
                f.write(f"\n\n---\n知识来源:\n")
                for i, src in enumerate(result.knowledge_sources, 1):
                    f.write(f"{i}. {src['title']} - {src['author']}\n")
            print(f"\n已保存到: {args.output}")


if __name__ == "__main__":
    main()
