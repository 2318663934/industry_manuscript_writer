#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略案例检索模块

从Milvus策略案例库中检索相似案例，用于动态Few-shot
"""

from typing import List, Dict, Any, Optional
from pymilvus import Collection

from .models import StrategyCase
from .case_base import CaseBaseManager


class StrategyRetriever:
    """
    策略案例检索器

    基于向量相似度和过滤条件，从策略案例库中检索相关案例
    """

    def __init__(
        self,
        case_base: CaseBaseManager,
        top_k: int = 5,
    ):
        """
        初始化检索器

        Args:
            case_base: 案例库管理器
            top_k: 默认检索数量
        """
        self.case_base = case_base
        self.top_k = top_k

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[StrategyCase]:
        """
        检索相似策略案例

        Args:
            query: 查询文本（可以是话题、标题等）
            top_k: 检索数量
            filters: 过滤条件

        Returns:
            匹配的策略案例列表
        """
        if top_k is None:
            top_k = self.top_k

        # 生成查询向量
        query_vector = self.case_base.embedding_model.encode([query])[0].tolist()

        # 从Milvus检索
        collection = self.case_base.get_collection()
        if collection is None:
            print("警告：Milvus集合不存在，尝试从JSON文件检索")
            return self._retrieve_from_files(query, top_k, filters)

        # 构建过滤表达式
        expr = self._build_filter_expr(filters)

        # 执行检索
        try:
            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                limit=top_k,
                expr=expr,
                output_fields=["*"],
            )

            # 解析结果
            cases = []
            if results and results[0]:
                for res in results[0]:
                    case = self._search_result_to_case(res)
                    if case:
                        cases.append(case)

            return cases

        except Exception as e:
            print(f"Milvus检索失败: {e}，回退到文件检索")
            return self._retrieve_from_files(query, top_k, filters)

    def retrieve_by_content_type(
        self,
        query: str,
        content_type: str,
        top_k: int = 3,
    ) -> List[StrategyCase]:
        """
        按内容类型检索策略案例

        Args:
            query: 查询文本
            content_type: 内容类型
            top_k: 检索数量

        Returns:
            匹配的策略案例列表
        """
        return self.retrieve(query, top_k, filters={"content_type": content_type})

    def retrieve_by_tags(
        self,
        query: str,
        tags: List[str],
        top_k: int = 3,
    ) -> List[StrategyCase]:
        """
        按标签检索策略案例

        Args:
            query: 查询文本
            tags: 标签列表
            top_k: 检索数量

        Returns:
            匹配的策略案例列表
        """
        return self.retrieve(query, top_k, filters={"tags": tags})

    def retrieve_high_quality(
        self,
        query: str,
        min_score: float = 4.0,
        top_k: int = 5,
    ) -> List[StrategyCase]:
        """
        检索高质量策略案例

        Args:
            query: 查询文本
            min_score: 最低质量评分
            top_k: 检索数量

        Returns:
            高质量策略案例列表
        """
        return self.retrieve(query, top_k, filters={"min_quality": min_score})

    def _build_filter_expr(self, filters: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        构建Milvus过滤表达式

        Args:
            filters: 过滤条件字典

        Returns:
            Milvus表达式字符串
        """
        if not filters:
            return None

        exprs = []

        if "content_type" in filters:
            exprs.append(f'content_type == "{filters["content_type"]}"')

        if "min_quality" in filters:
            exprs.append(f"quality_score >= {filters['min_quality']}")

        if "tags" in filters:
            # 标签过滤需要使用JSON_CONTAINS或类似方法
            for tag in filters["tags"]:
                exprs.append(f'json_contains(tags, "{tag}")')

        if not exprs:
            return None

        return " and ".join(exprs)

    def _retrieve_from_files(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[StrategyCase]:
        """
        从JSON文件检索（Milvus不可用时的备选方案）

        Args:
            query: 查询文本
            top_k: 检索数量
            filters: 过滤条件

        Returns:
            匹配的策略案例列表
        """
        all_cases = self.case_base.list_cases(filters=filters, limit=100)

        if not all_cases:
            return []

        # 简单的文本相似度计算（备选方案）
        query_lower = query.lower()
        scored_cases = []

        for case in all_cases:
            # 计算简单相关性分数
            score = 0.0

            # 标题匹配
            if query_lower in case.title.lower():
                score += 2.0

            # 标签匹配
            for tag in case.tags:
                if tag.lower() in query_lower:
                    score += 1.0

            # 内容类型匹配
            if filters and "content_type" in filters:
                if case.content_type == filters["content_type"]:
                    score += 1.5

            # 质量评分加成
            score += case.quality_score / 5.0

            if score > 0:
                scored_cases.append((case, score))

        # 排序并返回top_k
        scored_cases.sort(key=lambda x: x[1], reverse=True)
        return [case for case, _ in scored_cases[:top_k]]

    def _search_result_to_case(self, result) -> Optional[StrategyCase]:
        """将搜索结果转换为StrategyCase"""
        try:
            entity = result.entity
            if not entity:
                return None

            import json

            annotation_data = json.loads(entity.get("annotation", "{}"))
            return StrategyCase(
                case_id=entity["case_id"],
                title=entity["title"],
                article_url=entity.get("article_url", ""),
                content_type=entity["content_type"],
                target_audience=entity.get("audience", ""),
                annotation=annotation_data,
                quality_score=entity.get("quality_score", 0),
                tags=entity.get("tags", []),
                created_at=entity.get("created_at", ""),
            )
        except Exception as e:
            print(f"转换案例失败: {e}")
            return None


def retrieve_similar_cases(
    case_base: CaseBaseManager,
    query: str,
    top_k: int = 5,
    content_type: Optional[str] = None,
) -> List[StrategyCase]:
    """
    便捷函数：从策略案例库检索相似案例

    Args:
        case_base: 案例库管理器
        query: 查询文本
        top_k: 检索数量
        content_type: 内容类型过滤

    Returns:
        相似策略案例列表
    """
    retriever = StrategyRetriever(case_base, top_k)

    if content_type:
        return retriever.retrieve_by_content_type(query, content_type, top_k)
    else:
        return retriever.retrieve(query, top_k)
