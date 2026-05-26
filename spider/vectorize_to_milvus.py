#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文章向量化和存储到 Milvus
"""
import json
import time
from pathlib import Path
from typing import List, Dict
from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema
from sentence_transformers import SentenceTransformer


MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
COLLECTION_NAME = "rag_articles"
DIM = 768  # shibing624/text2vec-base-chinese 模型输出维度
EMBEDDING_MODEL = "shibing624/text2vec-base-chinese"  # 中文Embedding模型


def load_articles(json_path: str) -> List[Dict]:
    """加载文章数据"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["articles"]


def create_embedding_model():
    """创建embedding模型"""
    print(f"加载Embedding模型: {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("模型加载完成")
    return model


def generate_embeddings(model, texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """生成文本向量"""
    print(f"正在生成 {len(texts)} 个文本的向量...")
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=True)
    return embeddings.tolist()


def connect_milvus() -> MilvusClient:
    """连接Milvus"""
    print(f"连接Milvus ({MILVUS_HOST}:{MILVUS_PORT})...")
    client = MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")
    print("连接成功")
    return client


def create_collection(client: MilvusClient):
    """创建集合"""
    # 如果集合已存在，先删除
    if client.has_collection(COLLECTION_NAME):
        print(f"集合 {COLLECTION_NAME} 已存在，删除中...")
        client.drop_collection(COLLECTION_NAME)

    # 创建字段schema
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="author", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="date", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="content_length", dtype=DataType.INT64),
        FieldSchema(name="content_text", dtype=DataType.VARCHAR, max_length=50000),  # 存储文章内容
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
    ]
    schema = CollectionSchema(fields=fields, description="WeChat Articles")

    print(f"创建集合 {COLLECTION_NAME}...")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
    )
    print("集合创建成功")

    # 创建索引（向量字段需要索引才能被加载和搜索）
    print("创建向量索引...")
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="AUTOINDEX",
        metric_type="IP",
    )
    client.create_index(
        collection_name=COLLECTION_NAME,
        index_params=index_params,
    )
    print("索引创建成功")


def insert_articles(client: MilvusClient, articles: List[Dict], embeddings: List[List[float]]):
    """插入文章数据"""
    print("正在插入数据...")

    data = []
    for i, (article, embedding) in enumerate(zip(articles, embeddings)):
        data.append({
            "id": i + 1,
            "title": article.get("title", "")[:500],
            "url": article.get("url", "")[:500],
            "author": article.get("author", "")[:200] if article.get("author") else "",
            "date": article.get("date", "")[:50] if article.get("date") else "",
            "content_length": len(article.get("content_text", "")),
            "content_text": article.get("content_text", "")[:50000],  # 限制最大长度
            "embedding": embedding,
        })

    result = client.insert(collection_name=COLLECTION_NAME, data=data)
    print(f"插入完成! 成功插入 {result['insert_count']} 条记录")
    return result


def search_similar(client: MilvusClient, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
    """搜索相似文章"""
    results = client.search(
        collection_name=COLLECTION_NAME,
        anns_field="embedding",
        data=[query_embedding],
        limit=top_k,
        output_fields=["title", "url", "author", "date"],
    )
    return results[0] if results else []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="文章向量化和存储到Milvus")
    parser.add_argument("json_file", help="文章JSON文件路径")
    parser.add_argument("--recreate", action="store_true", help="重建集合（删除旧数据）")
    args = parser.parse_args()

    # 1. 加载文章
    print("=" * 50)
    print("步骤1: 加载文章数据")
    print("=" * 50)
    articles = load_articles(args.json_file)
    print(f"共加载 {len(articles)} 篇文章")

    if not articles:
        print("错误: 没有文章数据")
        return

    # 2. 生成文本（标题 + 全文）
    print("\n" + "=" * 50)
    print("步骤2: 准备文本（使用完整文章内容）")
    print("=" * 50)
    texts = []
    for article in articles:
        # 组合标题和完整文章内容
        content = article.get("content_text", "") or ""
        text = f"{article.get('title', '')}。{content}"
        texts.append(text)
        print(f"  {article.get('title', '')[:40]}... -> {len(text)} 字符")

    # 3. 生成向量
    print("\n" + "=" * 50)
    print("步骤3: 生成向量")
    print("=" * 50)
    model = create_embedding_model()
    embeddings = generate_embeddings(model, texts)

    # 4. 连接Milvus
    print("\n" + "=" * 50)
    print("步骤4: 连接Milvus")
    print("=" * 50)
    client = connect_milvus()

    # 5. 创建集合
    if args.recreate or not client.has_collection(COLLECTION_NAME):
        create_collection(client)

    # 6. 插入数据
    print("\n" + "=" * 50)
    print("步骤5: 插入数据到Milvus")
    print("=" * 50)
    result = insert_articles(client, articles, embeddings)

    # 7. 统计
    print("\n" + "=" * 50)
    print("完成!")
    print("=" * 50)
    stats = client.get_collection_stats(COLLECTION_NAME)
    print(f"集合: {COLLECTION_NAME}")
    print(f"记录数: {stats['row_count']}")
    print(f"维度: {DIM}")

    # 8. 加载集合（用于搜索）
    print("\n" + "=" * 50)
    print("步骤6: 加载集合")
    print("=" * 50)
    client.load_collection(COLLECTION_NAME)
    print("集合加载成功")

    # 9. 测试搜索
    print("\n" + "=" * 50)
    print("步骤7: 测试相似文章搜索")
    print("=" * 50)
    if texts:
        test_embedding = embeddings[0]
        results = search_similar(client, test_embedding, top_k=3)
        print(f"以第1篇文章为查询，找到 {len(results)} 篇相似文章:")
        for r in results:
            print(f"  - {r['entity']['title'][:40]} (距离: {r['distance']:.4f})")


if __name__ == "__main__":
    main()
