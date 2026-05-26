#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG写作系统使用示例
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_writer import (
    create_writer,
    parse_document,
    extract_topic_from_text,
    FewShotPromptBuilder,
    WritingTask,
    KnowledgeContext,
)


def example_basic_usage():
    """基本用法"""
    print("=" * 60)
    print("示例1: 基本用法")
    print("=" * 60)

    # 创建写作引擎
    writer = create_writer(
        articles_json="e:/行业稿件写作/code/wechat_spider/data/文章链接_20260401_162942.json",
        use_few_shot=True,
    )

    # 检查状态
    print("\n系统状态:")
    status = writer.check_status()
    print(f"  Milvus集合: {status['milvus']}")
    print(f"  Embedding模型: {status['embedding_model']}")

    # 执行写作
    result = writer.write(
        topic="AI大模型在内容创作领域的应用",
        requirements="分析AI大模型（如ChatGPT、Claude等）如何改变内容创作行业，包括优势、挑战和未来趋势",
        keywords=["AI", "大模型", "内容创作", "AIGC"],
        length="2000字左右",
    )

    print(f"\n生成完成!")
    print(f"  模型: {result.model}")
    print(f"  知识来源: {result.knowledge_count}条")
    print(f"  生成时间: {result.generation_time:.2f}秒")

    print("\n--- 生成的文章 ---")
    print(result.article)

    return result


def example_from_file():
    """从文件输入写作"""
    print("\n" + "=" * 60)
    print("示例2: 从文件输入写作")
    print("=" * 60)

    # 创建写作引擎
    writer = create_writer(
        articles_json="e:/行业稿件写作/code/wechat_spider/data/文章链接_20260401_162942.json",
    )

    # 假设用户有一个需求文档
    # result = writer.write_from_file("用户需求.docx")

    # 这里用纯文本演示
    topic = "远程办公对企业团队协作的影响"
    requirements = """
请分析远程办公对企业团队协作的影响，包括：
1. 远程办公带来的积极变化
2. 面临的挑战和问题
3. 应对策略和建议
文章要有深度，避免空洞的套话。
"""
    keywords = ["远程办公", "团队协作", "企业管理", "数字化"]

    result = writer.write(
        topic=topic,
        requirements=requirements,
        keywords=keywords,
    )

    print(f"\n生成完成!")
    print(result.article)

    return result


def example_with_custom_knowledge():
    """使用自定义知识"""
    print("\n" + "=" * 60)
    print("示例3: 使用自定义知识")
    print("=" * 60)

    writer = create_writer()

    # 使用自定义知识（模拟检索结果）
    knowledge = [
        KnowledgeContext(
            title="AI时代的内容创作变革",
            url="https://example.com/1",
            author="张三",
            date="2024-01-15",
            content="""
人工智能正在深刻改变内容创作行业。从ChatGPT到Claude，大语言模型展现出惊人的创作能力。
研究表明，AI辅助写作可以将内容生产效率提升50%以上。
但同时也存在挑战：如何保证内容的真实性和原创性，如何避免AI生成的模板化表达。
优秀的内容创作者开始学会与AI协作，而不是被AI取代。
""",
        ),
        KnowledgeContext(
            title="AIGC的商业化之路",
            url="https://example.com/2",
            author="李四",
            date="2024-02-20",
            content="""
AIGC（AI Generated Content）正在从概念走向落地。
目前主要应用场景包括：新闻写作、广告文案、产品描述、客服对话等。
商业模式也在探索中：订阅制、按量计费、行业解决方案等。
关键成功因素：数据质量、模型能力、垂直场景理解。
""",
        ),
    ]

    result = writer.write(
        topic="AIGC对内容创作行业的影响",
        requirements="分析AIGC技术如何重塑内容创作行业，讨论机遇与挑战",
        keywords=["AIGC", "内容创作", "人工智能"],
        knowledge=knowledge,  # 传入预检索的知识
    )

    print(f"\n生成完成!")
    print(result.article)

    return result


def example_revision():
    """文章修改"""
    print("\n" + "=" * 60)
    print("示例4: 文章修改")
    print("=" * 60)

    writer = create_writer()

    # 假设已经有了一篇文章
    original_article = """
随着科技的不断发展，人工智能技术正在改变我们的生活方式。
人工智能技术的发展可以追溯到上世纪50年代，经过几十年的发展，如今已经取得了巨大的进步。
人工智能技术的应用范围非常广泛，包括医疗、金融、教育、交通等各个领域。
在内容创作领域，人工智能也发挥着越来越重要的作用。
人工智能可以帮助人们更高效地完成各种任务。
总的来说，人工智能技术的发展对于社会发展具有重要意义。
"""

    # 提出修改要求
    revision_requirements = """
请修改这篇文章：
1. 消除AI写作的套话感（如"随着...发展"开头）
2. 使用更具体的案例和数据支撑观点
3. 让语言更加生动自然，减少说教感
4. 调整文章结构，让开头更有吸引力
"""

    revised = writer.revise(original_article, revision_requirements)

    print("修改后的文章:")
    print(revised)


def example_stream_output():
    """流式输出"""
    print("\n" + "=" * 60)
    print("示例5: 流式输出")
    print("=" * 60)

    writer = create_writer()

    print("正在生成（流式输出）...\n")

    for chunk in writer.write_stream(
        topic="数字化转型对企业管理的挑战",
        requirements="分析企业在数字化转型过程中面临的管理挑战和应对策略",
        keywords=["数字化转型", "企业管理", "数字转型"],
    ):
        print(chunk, end="", flush=True)

    print("\n\n流式输出完成!")


def main():
    """运行所有示例"""
    print("\n" + "#" * 60)
    print("# RAG写作系统使用示例")
    print("#" * 60)

    try:
        # 示例1: 基本用法（需要先确保Milvus中有数据）
        # example_basic_usage()

        # 示例2: 从文件输入
        # example_from_file()

        # 示例3: 使用自定义知识（不需要Milvus）
        example_with_custom_knowledge()

        # 示例4: 文章修改
        example_revision()

        # 示例5: 流式输出
        # example_stream_output()

        print("\n" + "#" * 60)
        print("# 示例运行完成!")
        print("#" * 60)

    except KeyboardInterrupt:
        print("\n\n已取消")
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
