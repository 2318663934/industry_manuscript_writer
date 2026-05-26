#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B端深度稿件策划专家使用示例

展示如何使用 deep_brief=True 模式生成深度Brief和文章
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_writer import (
    create_writer,
    DeepBriefPromptBuilder,
    DeepArticlePromptBuilder,
    WritingTask,
    KnowledgeContext,
)


def example_generate_deep_brief():
    """
    示例1: 生成深度Brief（而非直接写文章）

    这是推荐的工作流程：
    1. 先用AI生成一个深度Brief
    2. 编辑/调整Brief
    3. 再用Brief指导作者写文章
    """
    print("=" * 70)
    print("示例1: 生成B端深度Brief")
    print("=" * 70)

    # 创建支持deep_brief的写作引擎
    writer = create_writer(
        articles_json="e:/行业稿件写作/code/wechat_spider/data/文章链接_20260401_162942.json",
        deep_brief=True,
    )

    # 定义写作任务
    topic = "某头部云厂商发布新一代大模型对行业格局的影响"
    requirements = """
分析某头部云厂商发布新一代AI大模型对国内云服务市场和AI行业格局的影响。要求：
1. 分析技术层面的突破点和局限性
2. 探讨对现有竞争格局的冲击
3. 评估对产业链上下游的影响
4. 预判未来12-18个月的市场走向
"""
    keywords = ["大模型", "云服务", "AI行业", "竞争格局", "产业链"]
    target_audience = "企业高管、行业投资者、技术同行"
    perspective = "资深行业观察者"

    # 生成深度Brief
    result = writer.generate_deep_brief(
        topic=topic,
        requirements=requirements,
        keywords=keywords,
        target_audience=target_audience,
        perspective=perspective,
        length="Brief本身约1500字，可扩展为3000字文章",
    )

    print(f"\n生成完成!")
    print(f"模型: {result.model}")
    print(f"知识来源: {result.knowledge_count}条")
    print(f"生成时间: {result.generation_time:.2f}秒")

    print("\n" + "=" * 70)
    print("生成的深度Brief")
    print("=" * 70)
    print(result.article)

    return result


def example_custom_knowledge_deep_brief():
    """
    示例2: 使用自定义知识生成深度Brief
    """
    print("\n" + "=" * 70)
    print("示例2: 使用自定义知识生成深度Brief")
    print("=" * 70)

    writer = create_writer(deep_brief=True)

    # 模拟检索到的知识
    knowledge = [
        KnowledgeContext(
            title="某厂商新一代AI芯片发布",
            url="https://example.com/1",
            author="行业观察",
            date="2024-03-15",
            content="""
该芯片采用先进制程，推理性能提升显著。
实测在Transformer架构模型上，吞吐量提升约40%。
功耗控制优秀，每TOPS能耗比上一代降低35%。
但生态支持仍不完善，主流框架适配需要3-6个月。
价格策略激进，意图通过硬件绑定软件服务。
""",
        ),
        KnowledgeContext(
            title="国内云服务市场竞争态势分析",
            url="https://example.com/2",
            author="市场研究",
            date="2024-02-28",
            content="""
国内市场前三名占据约65%份额。
价格战持续，整体毛利率下降约5个百分点。
企业级客户更关注稳定性和服务质量，而非单纯价格。
差异化竞争成为新趋势：垂直行业解决方案。
""",
        ),
    ]

    topic = "AI芯片新品发布对国内云服务价格战的影响"
    requirements = "分析这款AI芯片如何影响国内云服务市场的竞争态势和价格走向"

    result = writer.generate_deep_brief(
        topic=topic,
        requirements=requirements,
        keywords=["AI芯片", "云服务", "价格战", "竞争态势"],
        knowledge=knowledge,
        target_audience="企业CTO、云计算投资者",
        perspective="产业链合作伙伴",
    )

    print(f"\nBrief生成完成!")
    print(result.article)

    return result


def example_deep_article():
    """
    示例3: 直接生成深度文章（不经过Brief）
    适用于对话题已经非常熟悉，不需要再梳理Brief的场景
    """
    print("\n" + "=" * 70)
    print("示例3: 直接生成深度文章")
    print("=" * 70)

    writer = create_writer(deep_brief=True)

    topic = "国产大模型加速出海：机遇与挑战"
    requirements = """
分析国产大模型出海的现状、机遇和挑战，要求：
1. 给出具体的市场数据或案例
2. 深入分析技术适配问题
3. 探讨合规和本地化挑战
4. 给出有价值的战略建议
"""
    keywords = ["大模型出海", "国际化", "合规", "本地化"]

    # 使用deep_brief模式生成完整文章
    result = writer.write(
        topic=topic,
        requirements=requirements,
        keywords=keywords,
        target_audience="企业高管、出海团队负责人",
        perspective="厂家同行视角",
    )

    print(f"\n文章生成完成!")
    print(f"模型: {result.model}")
    print(f"生成时间: {result.generation_time:.2f}秒")

    print("\n" + "=" * 70)
    print("生成的文章")
    print("=" * 70)
    print(result.article)

    return result


def example_multi_perspective():
    """
    示例4: 同一话题，多视角分析

    展示如何用同一个话题生成不同站位的Brief
    """
    print("\n" + "=" * 70)
    print("示例4: 多视角分析")
    print("=" * 70)

    writer = create_writer(deep_brief=True)

    topic = "新能源车企价格战对零部件供应商的影响"

    # 视角1: 投资者视角
    print("\n--- 视角1: 投资者视角 ---")
    result_investor = writer.generate_deep_brief(
        topic=topic,
        requirements="分析价格战对供应商利润率和现金流的影响",
        keywords=["新能源", "价格战", "零部件", "供应链"],
        target_audience="二级市场投资者",
        perspective="资深行业观察者",
    )
    print(result_investor.article[:1500] + "...")

    # 视角2: 供应商视角
    print("\n--- 视角2: 供应商视角 ---")
    result_supplier = writer.generate_deep_brief(
        topic=topic,
        requirements="分析作为Tier1/Tier2供应商的应对策略",
        keywords=["新能源", "价格战", "零部件", "供应链"],
        target_audience="零部件企业高管",
        perspective="产业链合作伙伴",
    )
    print(result_supplier.article[:1500] + "...")


def main():
    """运行示例"""
    print("\n" + "#" * 70)
    print("# B端深度稿件策划专家 - 使用示例")
    print("#" * 70)

    try:
        # 示例1: 生成深度Brief（推荐流程）
        example_generate_deep_brief()

        # 示例2: 使用自定义知识
        # example_custom_knowledge_deep_brief()

        # 示例3: 直接生成深度文章
        # example_deep_article()

        # 示例4: 多视角分析
        # example_multi_perspective()

        print("\n" + "#" * 70)
        print("# 示例运行完成!")
        print("#" * 70)

    except KeyboardInterrupt:
        print("\n\n已取消")
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
