#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SkillAgent配置模块
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from rag_writer.config import Settings


class SkillAgentConfig(BaseModel):
    """SkillAgent配置"""

    # 案例库配置
    case_base_path: str = Field(
        default="./strategy_cases",
        description="策略案例库根目录"
    )
    case_retrieval_top_k: int = Field(
        default=5,
        description="策略案例检索数量"
    )

    # LLM生成配置
    temperature: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="策略生成温度，建议0.3~0.5"
    )
    reflection_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Self-Reflection校验温度"
    )

    # Self-Reflection配置
    max_reflection_iterations: int = Field(
        default=2,
        ge=1,
        le=5,
        description="最大校验迭代次数"
    )
    min_confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="策略置信度阈值，低于此值将重试"
    )

    # Milvus配置（策略案例库专用）
    milvus_collection: str = Field(
        default="strategy_cases",
        description="Milvus策略案例集合名"
    )
    milvus_use_lite: bool = Field(
        default=False,
        description="是否使用Milvus Lite（暂不可用）"
    )
    milvus_uri: str = Field(
        default="./strategy_cases/milvus_lite.db",
        description="Milvus Lite数据库路径（仅use_lite=True时使用）"
    )
    milvus_host: str = Field(
        default="localhost",
        description="Milvus主机"
    )
    milvus_port: str = Field(
        default="19530",
        description="Milvus端口"
    )

    # 案例标注配置
    annotation_max_chars: int = Field(
        default=8000,
        description="标注时文章最大字符数"
    )

    # Embedding模型配置（与主配置保持一致）
    embedding: Dict[str, Any] = Field(
        default_factory=lambda: {"model_name": "shibing624/text2vec-base-chinese"},
        description="Embedding模型配置"
    )


class SettingsWithSkill(Settings):
    """扩展的Settings，包含SkillAgent配置"""

    skill_agent: SkillAgentConfig = Field(
        default_factory=SkillAgentConfig
    )


# 全局配置实例
_settings: Optional[SkillAgentConfig] = None


def get_skill_config() -> SkillAgentConfig:
    """获取SkillAgent配置（单例）"""
    global _settings
    if _settings is None:
        _settings = SkillAgentConfig()
    return _settings


def update_skill_config(**kwargs) -> SkillAgentConfig:
    """更新SkillAgent配置"""
    global _settings
    if _settings is None:
        _settings = SkillAgentConfig()
    _settings = _settings.model_copy(update=kwargs)
    return _settings
