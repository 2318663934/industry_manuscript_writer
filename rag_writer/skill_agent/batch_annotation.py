#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量标注脚本 - 对JSON文件中的文章进行策略标注

用法:
    python batch_annotation.py --input "path/to/articles.json" --output "path/to/annotations.json"
"""

import json
import argparse
import re
from pathlib import Path

# 添加父目录到路径以导入rag_writer
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_writer.llm_client import create_llm_client
from rag_writer.skill_agent import StrategyAnnotator, batch_annotate


def extract_text_from_html(html_content: str) -> str:
    """从HTML内容中提取纯文本"""
    if not html_content:
        return ""

    # 移除script和style标签及其内容
    html = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # 移除HTML注释
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

    # 将<br>替换为换行符
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)

    # 移除所有HTML标签
    text = re.sub(r'<[^>]+>', '', html)

    # 解码HTML实体
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&apos;', "'")

    # 清理多余空白
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()

    return text


def load_articles_from_json(json_path: str) -> list:
    """
    从JSON文件加载文章列表

    Args:
        json_path: JSON文件路径

    Returns:
        文章列表 [{"title": "", "content": "", "url": "", ...}, ...]
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articles = data.get('articles', [])
    print(f"从 {json_path} 加载了 {len(articles)} 篇文章")

    # 标准化文章格式
    normalized = []
    for i, article in enumerate(articles):
        # 提取纯文本内容
        content_html = article.get('content_html', '')
        content_text = extract_text_from_html(content_html)

        if not content_text or len(content_text) < 100:
            print(f"  跳过第{i+1}篇（内容过短）: {article.get('title', '无标题')[:30]}...")
            continue

        # 构建URL字段
        url = article.get('url', '')
        if not url:
            # 尝试从其他字段构建
            url = article.get('link', '')

        normalized.append({
            'title': article.get('title', f'无标题_{i+1}'),
            'content': content_text,
            'url': url,
            'author': article.get('author', ''),
            'date': article.get('date', ''),
            'content_type': '行业分析',  # 默认类型
        })

    return normalized


def main():
    parser = argparse.ArgumentParser(description='批量标注文章策略')
    parser.add_argument('--input', '-i', nargs='+', required=True,
                        help='输入JSON文件路径（支持多个文件）')
    parser.add_argument('--output', '-o', default='./annotations.json',
                        help='输出JSON文件路径')
    parser.add_argument('--provider', '-p', default='minimax',
                        help='LLM提供商')
    parser.add_argument('--save-interval', '-s', type=int, default=10,
                        help='每多少篇保存一次中间结果')
    parser.add_argument('--max-articles', '-m', type=int, default=None,
                        help='最多处理文章数量（用于测试）')

    args = parser.parse_args()

    # 加载所有文章
    all_articles = []
    for json_path in args.input:
        articles = load_articles_from_json(json_path)
        all_articles.extend(articles)

    print(f"\n总共加载了 {len(all_articles)} 篇有效文章")

    if args.max_articles and len(all_articles) > args.max_articles:
        print(f"限制处理前 {args.max_articles} 篇（用于测试）")
        all_articles = all_articles[:args.max_articles]

    # 创建LLM客户端
    print(f"\n创建LLM客户端 (provider={args.provider})...")
    llm_client = create_llm_client(args.provider)

    # 创建标注器
    annotator = StrategyAnnotator(llm_client=llm_client, temperature=0.3)

    # 批量标注
    print(f"\n开始批量标注，共 {len(all_articles)} 篇文章...")
    print("-" * 50)

    cases = batch_annotate(
        articles=all_articles,
        output_path=args.output,
        llm_client=llm_client,
        save_interval=args.save_interval,
    )

    print("-" * 50)
    print(f"\n标注完成！")
    print(f"共处理 {len(cases)} 篇文章")
    print(f"结果已保存到: {args.output}")

    # 统计信息
    success_count = sum(1 for c in cases if c.quality_score > 0)
    failed_count = len(cases) - success_count
    avg_score = sum(c.quality_score for c in cases) / len(cases) if cases else 0

    print(f"\n统计信息:")
    print(f"  成功标注: {success_count}")
    print(f"  标注失败: {failed_count}")
    print(f"  平均质量分: {avg_score:.2f}")


if __name__ == '__main__':
    main()
