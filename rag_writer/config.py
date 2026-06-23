#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG写作系统配置文件
"""
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class MilvusConfig(BaseModel):
    """Milvus配置"""
    # use_lite: 是否使用Milvus Lite（嵌入式本地版本，需要安装pymilvus[milvus_lite]）
    use_lite: bool = False  # Docker版Milvus更稳定
    uri: str = "./milvus_lite.db"  # Milvus Lite数据库路径（仅use_lite=True时使用）
    host: str = "localhost"
    port: str = "19530"
    collection_name: str = "rag_articles"
    top_k: int = 5  # 召回数量


class LLMConfig(BaseModel):
    """大模型配置"""
    provider: str = "openai"  # openai / claude / siliconflow / zhipu / minimax / deepseek
    model: str = "deepseek-v4-pro"
    api_key: str = ""
    base_url: Optional[str] = "https://api.deepseek.com"  # DeepSeek API端点
    temperature: float = 0.7
    max_tokens: int = 4000


class EmbeddingConfig(BaseModel):
    """Embedding模型配置"""
    model_name: str = "shibing624/text2vec-base-chinese"
    device: str = "cpu"  # cpu / cuda
    batch_size: int = 32


class WikiConfig(BaseModel):
    """LLM-Wiki 配置 (替代 E:/产品信息知识库 的产品库)"""
    # 本机 Wiki API Server
    api_url: str = "http://127.0.0.1:8088"
    api_key: str = ""                        # Bearer token (留空 = 关闭鉴权)
    # 知识库模式:
    #   "rag":    纯 Milvus 产品库 (原行为, 不调本机)
    #   "wiki":   纯 LLM-Wiki (强制走本机, 失败返回空)
    #   "hybrid": Wiki 优先, 失败降级 RAG (推荐)
    knowledge_mode: str = "hybrid"
    timeout_sec: int = 60


class PromptConfig(BaseModel):
    """提示词配置"""
    max_knowledge_chars: int = 8000  # 知识上下文最大字符数
    min_knowledge_chars: int = 2000  # 知识上下文最小字符数
    style_requirements: str = (
        "1. 语言自然流畅，像人写的那样有节奏感\n"
        "2. 避免AI常见的空洞套话（如'随着时代发展'、'众所周知'）\n"
        "3. 长短句结合，有起有伏\n"
        "4. 可以使用口语化表达和过渡词\n"
        "5. 适当引用数据或案例，但不要堆砌\n"
        "6. 段落之间过渡自然"
    )


class Settings(BaseSettings):
    """全局设置"""
    milvus: MilvusConfig = MilvusConfig()
    llm: LLMConfig = LLMConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    wiki: WikiConfig = WikiConfig()
    prompt: PromptConfig = PromptConfig()

    class Config:
        env_file = str(Path(__file__).parent / ".env")
        env_nested_delimiter = "__"


# 全局设置实例
settings = Settings()


def get_milvus_uri() -> str:
    """获取Milvus URI"""
    if settings.milvus.use_lite:
        return settings.milvus.uri
    return f"http://{settings.milvus.host}:{settings.milvus.port}"
