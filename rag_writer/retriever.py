#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向量检索模块 - 从Milvus检索相关知识
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pymilvus import MilvusClient

from .config import settings, get_milvus_uri


@dataclass
class KnowledgeItem:
    """知识条目"""
    id: int
    title: str
    url: str
    author: str
    date: str
    content_length: int
    distance: float  # 相似度距离
    content: Optional[str] = None  # 完整内容

    def load_content_from_json(self, articles_data: List[Dict[str, Any]]) -> None:
        """
        从文章JSON数据中加载完整内容

        Args:
            articles_data: 文章数据列表
        """
        for article in articles_data:
            # 匹配ID（假设JSON中的id字段或者使用数组索引+1作为ID）
            article_id = article.get('id')
            if article_id is None:
                # 如果没有id字段，使用数组索引+1作为ID
                idx = articles_data.index(article)
                article_id = idx + 1

            if article_id == self.id:
                self.content = article.get('content_text', '')
                self.content_length = len(self.content) if self.content else 0
                break


class VectorRetriever:
    """向量检索器"""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[str] = None,
        collection_name: Optional[str] = None,
        articles_json: Optional[str] = None,
    ):
        """
        初始化向量检索器

        Args:
            host: Milvus主机地址
            port: Milvus端口
            collection_name: 集合名称
            articles_json: 文章JSON文件路径（用于获取完整文章内容）
        """
        self.host = host or settings.milvus.host
        self.port = port or settings.milvus.port
        self.collection_name = collection_name or settings.milvus.collection_name
        self.articles_json = articles_json
        self._client: Optional[MilvusClient] = None
        self._articles_data: Optional[List[Dict[str, Any]]] = None

    @property
    def client(self) -> MilvusClient:
        """获取Milvus客户端（懒加载）"""
        if self._client is None:
            self._client = MilvusClient(uri=get_milvus_uri())
        return self._client

    def is_collection_exists(self) -> bool:
        """检查集合是否存在"""
        return self.client.has_collection(self.collection_name)

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息"""
        if not self.is_collection_exists():
            return {"exists": False, "row_count": 0}
        return {
            "exists": True,
            "row_count": self.client.get_collection_stats(self.collection_name)["row_count"],
        }

    def search(
        self,
        query_vector: List[float],
        top_k: Optional[int] = None,
        output_fields: Optional[List[str]] = None,
        load_full_content: bool = True,
    ) -> List[KnowledgeItem]:
        """
        搜索相似向量

        Args:
            query_vector: 查询向量
            top_k: 返回数量
            output_fields: 输出字段列表
            load_full_content: 是否加载完整文章内容

        Returns:
            相似知识条目列表
        """
        if output_fields is None:
            # 默认包含content_text以便直接获取文章内容
            output_fields = ["id", "title", "url", "author", "date", "content_length", "content_text"]

        if top_k is None:
            top_k = settings.milvus.top_k

        results = self.client.search(
            collection_name=self.collection_name,
            anns_field="embedding",
            data=[query_vector],
            limit=top_k,
            output_fields=output_fields,
        )

        items = []
        for res in results[0]:
            entity = res["entity"]
            item = KnowledgeItem(
                id=entity["id"],
                title=entity["title"],
                url=entity["url"],
                author=entity["author"],
                date=entity["date"],
                content_length=entity["content_length"],
                distance=res["distance"],
            )

            # 直接从Milvus获取content_text（如果存在）
            if load_full_content and "content_text" in entity:
                item.content = entity["content_text"]
            elif load_full_content:
                # 回退到从JSON文件加载
                articles_data = self._load_articles_data()
                if articles_data:
                    item.load_content_from_json(articles_data)

            items.append(item)
        return items

    def _load_articles_data(self) -> Optional[List[Dict[str, Any]]]:
        """懒加载文章数据"""
        if self._articles_data is None and self.articles_json:
            try:
                self._articles_data = load_articles_from_json(self.articles_json)
            except Exception as e:
                print(f"警告: 加载文章数据失败: {e}")
                self._articles_data = []
        return self._articles_data

    def search_by_text(
        self,
        query_text: str,
        embedding_model,
        top_k: Optional[int] = None,
        load_full_content: bool = True,
    ) -> List[KnowledgeItem]:
        """
        通过文本搜索（自动向量化）

        Args:
            query_text: 查询文本
            embedding_model: embedding模型
            top_k: 返回数量
            load_full_content: 是否加载完整文章内容

        Returns:
            相似知识条目列表
        """
        # 生成查询向量
        query_vector = embedding_model.encode([query_text])[0].tolist()
        return self.search(query_vector, top_k, load_full_content=load_full_content)

    def get_article_content(self, article_id: int) -> Optional[str]:
        """
        获取文章完整内容（通过ID）

        从关联的JSON文件中获取完整文章内容。

        Args:
            article_id: 文章ID

        Returns:
            文章内容，如果不可用则返回None
        """
        articles_data = self._load_articles_data()
        if not articles_data:
            return None

        for article in articles_data:
            article_id_in_data = article.get('id')
            if article_id_in_data is None:
                idx = articles_data.index(article)
                article_id_in_data = idx + 1

            if article_id_in_data == article_id:
                return article.get('content_text', '')
        return None


class TextRetriever:
    """文本检索器（用于全文检索）"""

    def __init__(self, articles_data: List[Dict[str, Any]]):
        """
        初始化文本检索器

        Args:
            articles_data: 文章数据列表，每个文章包含title, content_text等字段
        """
        self.articles = articles_data

    def search(
        self,
        query_text: str,
        top_k: int = 5,
        min_similarity: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        基于关键词匹配的文本检索

        Args:
            query_text: 查询文本
            top_k: 返回数量
            min_similarity: 最小相似度阈值

        Returns:
            匹配的文章列表
        """
        import jieba
        from collections import Counter

        # 停用词
        stopwords = {
            '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '那', '什么', '怎么', '为什么', '如何', '可以', '这个', '那个',
        }

        # 提取查询关键词
        query_words = set(jieba.cut(query_text)) - stopwords

        results = []
        for article in self.articles:
            title = article.get('title', '')
            content = article.get('content_text', '')

            # 计算标题匹配度
            title_words = set(jieba.cut(title))
            title_match = len(query_words & title_words) / max(len(query_words), 1)

            # 计算内容匹配度
            content_words = set(jieba.cut(content))
            content_match = len(query_words & content_words) / max(len(query_words), 1)

            # 综合评分
            score = title_match * 0.6 + content_match * 0.4

            if score >= min_similarity:
                results.append({
                    'article': article,
                    'score': score,
                    'title': title,
                    'content_preview': content[:500] if content else '',
                })

        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]


class HybridRetriever:
    """混合检索器（向量 + 文本）"""

    def __init__(
        self,
        vector_retriever: VectorRetriever,
        text_retriever: TextRetriever,
        articles_json: Optional[str] = None,
    ):
        self.vector_retriever = vector_retriever
        self.text_retriever = text_retriever
        self.articles_json = articles_json
        self._articles_data: Optional[List[Dict[str, Any]]] = None

    def _load_articles_data(self) -> Optional[List[Dict[str, Any]]]:
        """懒加载文章数据"""
        if self._articles_data is None and self.articles_json:
            try:
                self._articles_data = load_articles_from_json(self.articles_json)
            except Exception as e:
                print(f"警告: 加载文章数据失败: {e}")
                self._articles_data = []
        return self._articles_data

    def search(
        self,
        query_text: str,
        embedding_model,
        top_k: int = 5,
        vector_weight: float = 0.6,
        text_weight: float = 0.4,
        load_full_content: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        混合搜索

        Args:
            query_text: 查询文本
            embedding_model: embedding模型
            top_k: 返回数量
            vector_weight: 向量检索权重
            text_weight: 文本检索权重
            load_full_content: 是否加载完整文章内容

        Returns:
            混合检索结果
        """
        # 向量检索（已包含完整内容，因为VectorRetriever默认load_full_content=True）
        vector_results = self.vector_retriever.search_by_text(
            query_text, embedding_model, top_k * 2, load_full_content=True
        )

        # 文本检索
        text_results = self.text_retriever.search(query_text, top_k * 2)

        # 加载完整文章数据（用于获取text检索结果的完整内容）
        articles_data = None
        if load_full_content:
            articles_data = self._load_articles_data()

        # 融合评分
        scored_results = {}

        # 添加向量检索结果（已有完整内容）
        for res in vector_results:
            key = res.title
            scored_results[key] = {
                'source': 'vector',
                'title': res.title,
                'url': res.url,
                'author': res.author,
                'date': res.date,
                'distance': res.distance,
                'score': res.distance * vector_weight,
                'content': res.content or '',  # 完整内容
            }

        # 添加文本检索结果
        for res in text_results:
            key = res['title']
            # 获取完整内容
            full_content = res['article'].get('content_text', '') if res.get('article') else ''

            if key in scored_results:
                scored_results[key]['score'] += res['score'] * text_weight
                scored_results[key]['text_score'] = res['score']
                # 如果之前没有content，补充完整内容
                if not scored_results[key].get('content') and full_content:
                    scored_results[key]['content'] = full_content
            else:
                scored_results[key] = {
                    'source': 'text',
                    'title': res['title'],
                    'url': res['article'].get('url', '') if res.get('article') else '',
                    'author': res['article'].get('author', '') if res.get('article') else '',
                    'date': res['article'].get('date', '') if res.get('article') else '',
                    'content': full_content,  # 完整内容
                    'score': res['score'] * text_weight,
                    'text_score': res['score'],
                }

        # 排序并返回
        sorted_results = sorted(
            scored_results.values(),
            key=lambda x: x['score'],
            reverse=True
        )
        return sorted_results[:top_k]


def load_articles_from_json(json_path: str) -> List[Dict[str, Any]]:
    """从JSON文件加载文章数据"""
    import json
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('articles', [])


if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) > 1:
        from sentence_transformers import SentenceTransformer

        # 加载模型
        model = SentenceTransformer("all-MiniLM-L6-v2")

        # 创建检索器
        retriever = VectorRetriever()

        # 检查集合
        stats = retriever.get_collection_stats()
        print(f"集合状态: {stats}")

        if stats.get('exists') and stats.get('row_count', 0) > 0:
            # 测试搜索
            results = retriever.search_by_text(sys.argv[1], model, top_k=3)
            print(f"\n找到 {len(results)} 条相关知识:")
            for i, res in enumerate(results, 1):
                print(f"{i}. {res.title}")
                print(f"   作者: {res.author} | 日期: {res.date}")
                print(f"   相似度: {res.distance:.4f}")
                print(f"   链接: {res.url}")
        else:
            print("集合为空或不存在，请先运行vectorize_to_milvus.py导入数据")
    else:
        print("用法: python retriever.py <查询文本>")
