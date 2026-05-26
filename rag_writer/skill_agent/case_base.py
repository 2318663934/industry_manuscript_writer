#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略案例库管理模块

管理优质文章的策略标注数据，支持：
- Milvus向量索引构建
- 策略案例的CRUD操作
- 与现有RAG系统的隔离存储
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility
from sentence_transformers import SentenceTransformer

from .models import StrategyCase, ArticleAnnotation
from .config import get_skill_config


class CaseBaseManager:
    """
    策略案例库管理器

    负责：
    - 案例的离线标注存储（JSON文件）
    - Milvus向量索引管理
    - 案例的CRUD操作
    """

    MILVUS_COLLECTION = "strategy_cases"
    EMBEDDING_DIM = 768  # shibing624/text2vec-base-chinese

    def __init__(
        self,
        base_path: Optional[str] = None,
        milvus_client: Optional[Any] = None,
        embedding_model: Optional[SentenceTransformer] = None,
        embedding_model_name: Optional[str] = None,
    ):
        """
        初始化案例库管理器

        Args:
            base_path: 案例库根目录路径
            milvus_client: Milvus客户端（若为None则创建连接）
            embedding_model: 向量模型（若为None则懒加载）
            embedding_model_name: 向量模型名称（默认使用配置中的模型）
        """
        config = get_skill_config()

        self.base_path = Path(base_path or config.case_base_path)
        self.milvus_client = milvus_client
        self.embedding_model = embedding_model
        # 默认使用配置中的embedding模型
        embedding_cfg = config.embedding
        if isinstance(embedding_cfg, dict):
            self.embedding_model_name = embedding_model_name or embedding_cfg.get("model_name", "all-MiniLM-L6-v2")
        else:
            self.embedding_model_name = embedding_model_name or getattr(embedding_cfg, "model_name", "all-MiniLM-L6-v2")

        # 确保目录结构
        self._ensure_directories()

    def _ensure_directories(self):
        """确保必要目录存在"""
        (self.base_path / "annotations").mkdir(parents=True, exist_ok=True)
        (self.base_path / "articles").mkdir(parents=True, exist_ok=True)
        (self.base_path / "index").mkdir(parents=True, exist_ok=True)

    @property
    def embedding_model(self) -> SentenceTransformer:
        """获取Embedding模型（懒加载）"""
        if self._embedding_model is None:
            print(f"加载Embedding模型: {self.embedding_model_name}...")
            self._embedding_model = SentenceTransformer(self.embedding_model_name)
            print("Embedding模型加载完成")
        return self._embedding_model

    @embedding_model.setter
    def embedding_model(self, value):
        self._embedding_model = value

    # ============ Milvus索引管理 ============

    def _get_milvus_client(self):
        """获取Milvus客户端"""
        if self.milvus_client is None:
            config = get_skill_config()
            if config.milvus_use_lite:
                # Milvus Lite 模式：使用MilvusClient
                from pymilvus import MilvusClient
                self.milvus_client = MilvusClient(uri=config.milvus_uri)
            else:
                # 服务器模式：使用旧式连接
                from pymilvus import connections
                connections.connect(
                    host=config.milvus_host,
                    port=config.milvus_port,
                )
                self.milvus_client = connections
        return self.milvus_client

    def _is_lite_mode(self) -> bool:
        """检查是否使用Milvus Lite模式"""
        config = get_skill_config()
        return config.milvus_use_lite

    def create_collection(self, drop_existing: bool = False) -> Optional[Any]:
        """
        创建Milvus策略案例集合

        Schema设计：
        - case_id: 主键 (VarChar)
        - title: 标题 (VarChar)
        - article_url: 原文链接 (VarChar)
        - content_type: 内容类型 (VarChar)
        - audience: 目标受众 (VarChar)
        - quality_score: 质量评分 (Float)
        - tags: 标签数组 (Array[VarChar])
        - embedding: 向量 (FloatVector[384])
        - annotation: 标注JSON (VarChar)
        - created_at: 创建时间 (VarChar)
        """
        config = get_skill_config()

        if self._is_lite_mode():
            # Milvus Lite 模式
            client = self._get_milvus_client()
            if client.has_collection(config.milvus_collection):
                if drop_existing:
                    client.drop_collection(config.milvus_collection)
                    print(f"已删除现有集合: {config.milvus_collection}")
                else:
                    print(f"集合已存在: {config.milvus_collection}")
                    return client

            client.create_collection(
                collection_name=config.milvus_collection,
                dimension=self.EMBEDDING_DIM,
                primary_column_name="case_id",
                vector_column_name="embedding",
                metric_type="COSINE",
                index_type="IVF_FLAT",
            )
            print(f"创建Milvus Lite集合: {config.milvus_collection}")
            return client
        else:
            # 服务器模式
            client = self._get_milvus_client()
            from pymilvus import utility

            if utility.has_collection(config.milvus_collection):
                if drop_existing:
                    utility.drop_collection(config.milvus_collection)
                    print(f"已删除现有集合: {config.milvus_collection}")
                else:
                    print(f"集合已存在: {config.milvus_collection}")
                    return self.get_collection()

            # 创建字段列表（pymilvus 2.6+ 需要的格式）
            fields = [
                FieldSchema(
                    name="case_id",
                    dtype=DataType.VARCHAR,
                    max_length=64,
                    is_primary=True,
                ),
                FieldSchema(
                    name="title",
                    dtype=DataType.VARCHAR,
                    max_length=256,
                ),
                FieldSchema(
                    name="article_url",
                    dtype=DataType.VARCHAR,
                    max_length=512,
                ),
                FieldSchema(
                    name="content_type",
                    dtype=DataType.VARCHAR,
                    max_length=64,
                ),
                FieldSchema(
                    name="audience",
                    dtype=DataType.VARCHAR,
                    max_length=256,
                ),
                FieldSchema(
                    name="quality_score",
                    dtype=DataType.FLOAT,
                ),
                FieldSchema(
                    name="tags",
                    dtype=DataType.ARRAY,
                    element_type=DataType.VARCHAR,
                    max_length=64,
                    max_capacity=20,
                ),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=self.EMBEDDING_DIM,
                ),
                FieldSchema(
                    name="annotation",
                    dtype=DataType.VARCHAR,
                    max_length=16384,
                ),
                FieldSchema(
                    name="created_at",
                    dtype=DataType.VARCHAR,
                    max_length=32,
                ),
            ]

            # 创建Schema（pymilvus 2.6+ 格式）
            schema = CollectionSchema(
                fields=fields,
                description="策略案例库 - 存储优质文章的策略标注和向量",
            )

            # 创建集合
            from pymilvus import Collection
            collection = Collection(
                name=config.milvus_collection,
                schema=schema,
            )
            print(f"创建Milvus集合: {config.milvus_collection}")

            # 创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }
            collection.create_index(
                field_name="embedding",
                index_params=index_params,
            )
            print("向量索引创建完成")

            return collection

    def get_collection(self) -> Optional[Any]:
        """获取Milvus集合"""
        config = get_skill_config()

        if self._is_lite_mode():
            client = self._get_milvus_client()
            if client.has_collection(config.milvus_collection):
                return client
            return None
        else:
            # 先确保Milvus连接已建立
            self._get_milvus_client()
            from pymilvus import Collection, utility
            if utility.has_collection(config.milvus_collection):
                return Collection(config.milvus_collection)
            return None

    # ============ 案例CRUD操作 ============

    def add_case(
        self,
        case: StrategyCase,
        article_content: Optional[str] = None,
    ) -> str:
        """
        添加新案例到案例库

        Args:
            case: 策略案例
            article_content: 原文内容（用于生成向量）

        Returns:
            case_id
        """
        # 1. 生成向量嵌入
        text_for_embedding = f"{case.title}\n{case.annotation.model_dump_json()}"
        embedding = self.embedding_model.encode([text_for_embedding])[0].tolist()

        # 2. 保存到JSON文件
        annotation_path = self.base_path / "annotations" / f"{case.case_id}.json"
        with open(annotation_path, "w", encoding="utf-8") as f:
            json.dump(case.to_dict(), f, ensure_ascii=False, indent=2)

        # 3. 保存原文（如果有）
        if article_content:
            article_path = self.base_path / "articles" / f"{case.case_id}.txt"
            with open(article_path, "w", encoding="utf-8") as f:
                f.write(article_content)

        # 4. 插入Milvus
        collection = self.get_collection()
        if collection:
            data = [{
                "case_id": case.case_id,
                "title": case.title,
                "article_url": case.article_url,
                "content_type": case.content_type,
                "audience": case.target_audience,
                "quality_score": case.quality_score,
                "tags": case.tags,
                "embedding": embedding,
                "annotation": case.annotation.model_dump_json(),
                "created_at": case.created_at,
            }]

            if self._is_lite_mode():
                collection.insert(
                    collection_name=get_skill_config().milvus_collection,
                    data=data,
                )
            else:
                collection.insert(data)
                collection.flush()
            print(f"案例已添加Milvus: {case.case_id}")

        return case.case_id

    def get_case(self, case_id: str) -> Optional[StrategyCase]:
        """
        获取单个案例

        Args:
            case_id: 案例ID

        Returns:
            StrategyCase或None
        """
        # 从JSON文件读取
        annotation_path = self.base_path / "annotations" / f"{case_id}.json"
        if annotation_path.exists():
            with open(annotation_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return StrategyCase.from_dict(data)

        # 从Milvus读取
        collection = self.get_collection()
        if collection:
            if self._is_lite_mode():
                results = collection.query(
                    collection_name=get_skill_config().milvus_collection,
                    filter=f'case_id == "{case_id}"',
                    output_fields=["*"],
                    limit=1,
                )
            else:
                results = collection.query(
                    expr=f'case_id == "{case_id}"',
                    output_fields=["*"],
                    limit=1,
                )
            if results:
                return self._milvus_to_case(results[0])

        return None

    def list_cases(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[StrategyCase]:
        """
        列出案例

        Args:
            filters: 过滤条件（暂不支持复杂查询）
            limit: 返回数量限制

        Returns:
            案例列表
        """
        cases = []

        # 从JSON文件列表读取
        annotations_dir = self.base_path / "annotations"
        if annotations_dir.exists():
            for json_file in sorted(annotations_dir.glob("*.json"))[:limit]:
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    case = StrategyCase.from_dict(data)

                    # 应用过滤
                    if filters:
                        if "content_type" in filters and case.content_type != filters["content_type"]:
                            continue
                        if "min_quality" in filters and case.quality_score < filters["min_quality"]:
                            continue
                        if "tags" in filters and not any(t in case.tags for t in filters["tags"]):
                            continue

                    cases.append(case)
                except Exception as e:
                    print(f"读取案例失败 {json_file}: {e}")

        return cases

    def update_annotation(
        self,
        case_id: str,
        annotation: ArticleAnnotation,
    ) -> bool:
        """
        更新案例标注

        Args:
            case_id: 案例ID
            annotation: 新的标注

        Returns:
            是否成功
        """
        case = self.get_case(case_id)
        if case is None:
            return False

        # 更新标注
        case.annotation = annotation
        case.quality_score = (
            annotation.opening_effectiveness + annotation.closing_effectiveness
        ) / 2

        # 保存
        annotation_path = self.base_path / "annotations" / f"{case_id}.json"
        with open(annotation_path, "w", encoding="utf-8") as f:
            json.dump(case.to_dict(), f, ensure_ascii=False, indent=2)

        # 更新Milvus
        collection = self.get_collection()
        if collection:
            if self._is_lite_mode():
                # Milvus Lite 不支持直接update，需要delete后重新insert
                collection.delete(
                    collection_name=get_skill_config().milvus_collection,
                    filter=f'case_id == "{case_id}"',
                )
            else:
                collection.update(
                    expr=f'case_id == "{case_id}"',
                    data={
                        "annotation": case.annotation.model_dump_json(),
                        "quality_score": case.quality_score,
                    },
                )

        return True

    def delete_case(self, case_id: str) -> bool:
        """
        删除案例

        Args:
            case_id: 案例ID

        Returns:
            是否成功
        """
        # 删除文件
        annotation_path = self.base_path / "annotations" / f"{case_id}.json"
        article_path = self.base_path / "articles" / f"{case_id}.txt"

        if annotation_path.exists():
            annotation_path.unlink()
        if article_path.exists():
            article_path.unlink()

        # 从Milvus删除
        collection = self.get_collection()
        if collection:
            if self._is_lite_mode():
                collection.delete(
                    collection_name=get_skill_config().milvus_collection,
                    filter=f'case_id == "{case_id}"',
                )
            else:
                collection.delete(expr=f'case_id == "{case_id}"')

        return True

    # ============ 辅助方法 ============

    def _milvus_to_case(self, entity: Dict[str, Any]) -> StrategyCase:
        """将Milvus实体转换为StrategyCase"""
        annotation_data = json.loads(entity["annotation"])
        return StrategyCase(
            case_id=entity["case_id"],
            title=entity["title"],
            article_url=entity.get("article_url", ""),
            content_type=entity["content_type"],
            target_audience=entity.get("audience", ""),
            annotation=ArticleAnnotation(**annotation_data),
            quality_score=entity.get("quality_score", 0),
            tags=entity.get("tags", []),
            created_at=entity.get("created_at", ""),
        )

    def import_from_json(self, json_path: str) -> int:
        """
        从JSON文件批量导入案例

        Args:
            json_path: JSON文件路径，包含案例列表

        Returns:
            导入数量
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for item in data:
            try:
                case = StrategyCase.from_dict(item)
                self.add_case(case)
                count += 1
            except Exception as e:
                print(f"导入案例失败: {e}")

        return count

    def export_to_json(self, output_path: str) -> int:
        """
        导出所有案例到JSON文件

        Args:
            output_path: 输出文件路径

        Returns:
            导出数量
        """
        cases = self.list_cases()
        data = [case.to_dict() for case in cases]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return len(data)

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取案例库统计信息"""
        cases = self.list_cases()
        return {
            "total_cases": len(cases),
            "collection_name": self.MILVUS_COLLECTION,
            "embedding_dim": self.EMBEDDING_DIM,
            "annotation_dir": str(self.base_path / "annotations"),
            "content_types": list(set(c.content_type for c in cases)),
            "avg_quality_score": sum(c.quality_score for c in cases) / len(cases) if cases else 0,
        }


if __name__ == "__main__":
    # 测试案例库管理
    print("测试CaseBaseManager...")

    manager = CaseBaseManager(base_path="./test_strategy_cases")

    # 创建集合
    # manager.create_collection(drop_existing=True)

    print("测试代码已准备")
