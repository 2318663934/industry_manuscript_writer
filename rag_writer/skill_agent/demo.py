#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SkillAgent演示脚本

展示：
1. 检索相似策略案例
2. 生成策略蓝图
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_writer.skill_agent import CaseBaseManager, SkillAgent
from rag_writer.llm_client import create_llm_client


def demo_retrieve_cases():
    """演示：检索相似策略案例"""
    print("=" * 60)
    print("演示1：检索相似策略案例")
    print("=" * 60)

    # 创建案例库管理器
    case_base = CaseBaseManager(
        base_path="./strategy_cases",
        embedding_model_name="all-MiniLM-L6-v2",
    )

    # 检索与"大模型定价战"相似的策略案例
    query = "大模型定价战 行业分析"
    print(f"\n查询: {query}")

    cases = case_base.list_cases(limit=5)
    print(f"\n找到 {len(cases)} 个相似案例:\n")

    for i, case in enumerate(cases, 1):
        print(f"【案例 {i}】{case.title}")
        print(f"  - 内容类型: {case.content_type}")
        print(f"  - 目标受众: {case.target_audience}")
        print(f"  - 开篇方式: {case.annotation.opening_approach}")
        print(f"  - 结构模式: {case.annotation.structural_pattern}")
        print(f"  - 收尾方式: {case.annotation.closing_approach}")
        print(f"  - 质量评分: {case.quality_score}")
        print()


def demo_skill_agent():
    """演示：使用SkillAgent生成策略蓝图"""
    print("\n" + "=" * 60)
    print("演示2：使用SkillAgent生成策略蓝图")
    print("=" * 60)

    # 创建LLM客户端
    llm_client = create_llm_client("minimax")

    # 创建案例库管理器
    case_base = CaseBaseManager(
        base_path="./strategy_cases",
        embedding_model_name="all-MiniLM-L6-v2",
    )

    # 创建SkillAgent
    skill_agent = SkillAgent(
        case_base=case_base,
        llm_client=llm_client,
        temperature=0.4,
    )

    # 模拟RAG上下文
    rag_context = {
        "knowledge": [],
        "topic": "大模型定价战分析",
    }

    print("\n话题: 大模型定价战分析")
    print("目标受众: 企业高管、投资者")
    print("内容类型: 行业分析")

    try:
        # 生成策略蓝图
        blueprint = skill_agent.generate_blueprint(
            topic="大模型定价战分析",
            rag_context=rag_context,
            content_type="行业分析",
            target_audience="企业高管、投资者",
            use_reflection=False,  # 演示时关闭校验加快速度
        )

        print("\n生成成功！")
        print(f"\n核心张力: {blueprint.core_tension}")
        print(f"写作基调: {blueprint.writing_tone.value}")
        print(f"置信度: {blueprint.confidence:.2f}")

        print(f"\n开篇策略: {blueprint.opening.approach}")
        print(f"  - {blueprint.opening.hook_content}")

        print(f"\n章节结构 ({len(blueprint.sections)} 节):")
        for section in blueprint.sections:
            print(f"  {section.section_id}. {section.title}")
            print(f"     手法: {section.structural_approach}")

        print(f"\n收尾策略: {blueprint.closing.approach}")
        print(f"  - {blueprint.closing.key_takeaway}")

        # 转换为Markdown格式展示
        print("\n" + "-" * 40)
        print("完整策略蓝图 (Markdown格式):")
        print("-" * 40)
        print(blueprint.to_markdown())

    except Exception as e:
        print(f"\n生成失败: {e}")
        print("（可能是因为LLM服务不可用或配额不足）")


def demo_stats():
    """演示：查看案例库统计"""
    print("\n" + "=" * 60)
    print("演示3：策略案例库统计")
    print("=" * 60)

    case_base = CaseBaseManager(
        base_path="./strategy_cases",
        embedding_model_name="all-MiniLM-L6-v2",
    )

    stats = case_base.get_collection_stats()
    print(f"\n总案例数: {stats['total_cases']}")
    print(f"平均质量分: {stats['avg_quality_score']:.2f}")
    print(f"内容类型: {', '.join(stats['content_types'][:5])}")


if __name__ == "__main__":
    demo_stats()
    demo_retrieve_cases()
    demo_skill_agent()
