#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SkillAgent演示 - 生成策略蓝图

演示完整的流程：
1. 创建SkillAgent
2. 检索相似策略案例（动态Few-shot）
3. 生成策略蓝图
4. 预览蓝图（Markdown格式）
5. 编译为写作指令
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_writer import create_writer
from rag_writer.llm_client import create_llm_client
from rag_writer.skill_agent import CaseBaseManager, SkillAgent


def main():
    print("=" * 60)
    print("SkillAgent演示 - 生成策略蓝图")
    print("=" * 60)

    # 1. 创建RAGWriter（用于RAG检索）
    print("\n[1] 初始化RAGWriter...")
    writer = create_writer()
    print(f"    LLM: {writer.llm_client.model}")
    print(f"    Embedding: {writer._embedding_model_name}")

    # 2. 创建SkillAgent
    print("\n[2] 初始化SkillAgent...")
    skill_agent = writer.create_skill_agent(
        case_base_path="./strategy_cases"
    )
    print(f"    案例库: {skill_agent.case_base.base_path}")

    # 查看案例库统计
    stats = skill_agent.get_case_base_stats()
    print(f"    案例总数: {stats['total_cases']}")
    print(f"    平均质量分: {stats['avg_quality_score']:.2f}")

    # 3. 定义写作话题
    topic = "AI Agent的落地困境与未来趋势"
    content_type = "行业分析"
    target_audience = "企业决策者、技术从业者"

    print(f"\n[3] 写作任务:")
    print(f"    话题: {topic}")
    print(f"    内容类型: {content_type}")
    print(f"    目标受众: {target_audience}")

    # 4. 检索RAG上下文（事实素材）
    print("\n[4] 检索RAG事实素材...")
    rag_knowledge = writer.retrieve_knowledge(topic, top_k=3)
    print(f"    检索到 {len(rag_knowledge)} 条相关知识")

    rag_context = {
        "knowledge": rag_knowledge,
        "topic": topic,
        "content_type": content_type,
    }

    # 5. 检索相似策略案例（动态Few-shot）
    print("\n[5] 检索相似策略案例（动态Few-shot）...")
    similar_cases = skill_agent.retriever.retrieve(topic, top_k=3)
    print(f"    找到 {len(similar_cases)} 个相似案例:")
    for i, case in enumerate(similar_cases, 1):
        print(f"    {i}. [{case.case_id}] {case.title}")
        print(f"       开篇: {case.annotation.opening_approach} | "
              f"结构: {case.annotation.structural_pattern} | "
              f"收尾: {case.annotation.closing_approach} | "
              f"质量: {case.quality_score:.1f}")

    # 6. 生成策略蓝图
    print("\n[6] 生成策略蓝图...")
    print("    (调用LLM进行策略规划，启用Self-Reflection校验)")

    blueprint = skill_agent.generate_blueprint(
        topic=topic,
        rag_context=rag_context,
        content_type=content_type,
        target_audience=target_audience,
        use_reflection=False,  # 暂时禁用Self- Reflection以便演示
    )

    print(f"\n    策略蓝图生成完成!")
    print(f"    置信度: {blueprint.confidence:.2f}")
    print(f"    章节数: {len(blueprint.sections)}")
    print(f"    引用案例: {len(blueprint.meta.get('case_references', []))} 个")

    # 7. 预览蓝图（Markdown格式）
    print("\n" + "=" * 60)
    print("策略蓝图预览（Markdown格式）")
    print("=" * 60)
    print(blueprint.to_markdown())

    # 8. 编译为写作指令
    print("\n" + "=" * 60)
    print("写作指令编译")
    print("=" * 60)

    instructions = skill_agent.compile_to_instructions(blueprint, rag_context)
    print(f"指令长度: {len(instructions.instruction_text)} 字符")
    print(f"分节数: {len(instructions.section_instructions)} 节")
    print(f"风格约束: {instructions.style_constraints}")

    # 显示部分指令示例
    print("\n--- 写作指令片段 ---")
    print(instructions.instruction_text[:1500] + "...")

    # 9. 总结
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)
    print(f"""
下一步:
1. 人工审核策略蓝图（Markdown预览）
2. 基于蓝图生成文章: writer.write_from_blueprint(blueprint)
3. 或一键完成: skill_agent.write_with_blueprint(topic, rag_context)
    """)


if __name__ == "__main__":
    main()
