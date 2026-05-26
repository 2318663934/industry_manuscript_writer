#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量爬虫 - 从txt文件读取文章链接并爬取
用法: python batch_spider.py links.txt
"""

import sys
import time
import argparse
from pathlib import Path
from article_parser import ArticleParser
from storage import ArticleStorage


def read_links(filepath: str) -> list:
    """从文件读取链接列表"""
    links = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):  # 忽略空行和注释
                # 去掉行号（如果有的话），如 "1    https://..." -> "https://..."
                parts = line.split(None, 1)  # 按空白字符分割，最多分1次
                url = parts[-1] if len(parts) > 1 else parts[0]
                if url.startswith("http"):
                    links.append(url)
    return links


def batch_fetch(links: list, delay: int = 3) -> list:
    """批量抓取文章"""
    parser = ArticleParser()
    results = []
    total = len(links)

    print("=" * 50)
    print(f"开始批量抓取，共 {total} 篇文章")
    print("=" * 50)

    for i, url in enumerate(links, 1):
        print(f"\n[{i}/{total}] 正在抓取...")
        print(f"   URL: {url[:60]}...")

        try:
            article = parser.fetch_article(url)
            if article and article.get("title"):
                results.append(article)
                print(f"   成功: {article['title'][:40]}")
            else:
                print(f"   失败: 未能获取内容")
                # 保存失败链接以便重试
                results.append({
                    "url": url,
                    "title": "",
                    "content_text": "",
                    "error": "fetch_failed"
                })
        except Exception as e:
            print(f"   错误: {e}")
            results.append({
                "url": url,
                "title": "",
                "content_text": "",
                "error": str(e)
            })

        if i < total:
            time.sleep(delay)

    return results


def main():
    parser = argparse.ArgumentParser(description="批量爬取微信文章")
    parser.add_argument("file", help="包含文章链接的txt文件路径")
    parser.add_argument("-d", "--delay", type=int, default=3, help="请求间隔（秒），默认3秒")
    parser.add_argument("-o", "--output", help="输出文件名（不含扩展名）")

    args = parser.parse_args()

    # 检查文件是否存在
    if not Path(args.file).exists():
        print(f"错误: 文件不存在 - {args.file}")
        return

    # 读取链接
    print(f"读取文件: {args.file}")
    links = read_links(args.file)
    print(f"共读取 {len(links)} 个链接\n")

    if not links:
        print("错误: 文件中没有有效的链接")
        return

    # 批量抓取
    results = batch_fetch(links, args.delay)

    # 统计
    success = sum(1 for r in results if r.get("title"))
    failed = len(results) - success

    print("\n" + "=" * 50)
    print(f"抓取完成！成功: {success}, 失败: {failed}")
    print("=" * 50)

    # 保存结果
    output_name = args.output or Path(args.file).stem
    storage = ArticleStorage(output_name)
    filepath = storage.save(results)
    print(f"\n结果已保存到: {filepath}")

    # 保存失败链接
    failed_links = [r["url"] for r in results if not r.get("title")]
    if failed_links:
        failed_file = Path(filepath).parent / f"{output_name}_failed.txt"
        with open(failed_file, "w", encoding="utf-8") as f:
            for url in failed_links:
                f.write(url + "\n")
        print(f"失败链接已保存到: {failed_file}")


if __name__ == "__main__":
    main()
