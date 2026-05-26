#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GameLook文章爬虫 - 从标题+链接格式的文件爬取文章
用法: python gamelook_spider.py gamelook文章链接.txt
"""

import sys
import time
import argparse
from pathlib import Path
from article_parser import ArticleParser
from storage import ArticleStorage
from config import REQUEST_DELAY


def read_gamelook_file(filepath: str) -> list:
    """
    读取gamelook格式的文件
    格式：标题、空行、URL、空行、标题、空行、URL...

    Args:
        filepath: 文件路径

    Returns:
        [(title, url), ...] 列表
    """
    articles = []

    # 尝试多种编码
    encodings = ["utf-8", "gbk", "gb2312", "gb18030"]

    for encoding in encodings:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read()
            # 成功读取，跳出循环
            break
        except UnicodeDecodeError:
            continue
    else:
        # 所有编码都失败
        print(f"错误: 无法读取文件，编码都不匹配")
        return []

    lines = content.split("\n")

    i = 0
    while i < len(lines):
        title = lines[i].strip()

        # 跳过空行和标记行
        if not title or title in ("Title", "Link"):
            i += 1
            continue

        # 跳过空行，找URL
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1  # 跳过空行

        # 检查是否有URL
        if j < len(lines):
            url = lines[j].strip()
            if url.startswith("http"):
                articles.append((title, url))
                i = j + 1
                continue

        i += 1

    return articles


def batch_fetch_gamelook(articles: list, delay: int = 3) -> list:
    """
    批量抓取GameLook文章

    Args:
        articles: [(title, url), ...] 列表
        delay: 请求间隔（秒）

    Returns:
        文章列表
    """
    parser = ArticleParser()
    results = []
    total = len(articles)

    print("=" * 60)
    print(f"开始批量抓取GameLook文章，共 {total} 篇")
    print("=" * 60)

    for i, (title, url) in enumerate(articles, 1):
        print(f"\n[{i}/{total}] 正在抓取...")
        print(f"   标题: {title[:40]}{'...' if len(title) > 40 else ''}")
        print(f"   URL: {url}")

        try:
            article = parser.fetch_gamelook_article(url)
            if article and article.get("content_text"):
                # 使用文件中的标题覆盖解析出的标题（更准确）
                if not article.get("title"):
                    article["title"] = title
                results.append(article)
                print(f"   成功! 字数: {len(article.get('content_text', ''))}")
            else:
                # 即使抓取失败，也保存基本信息
                results.append({
                    "title": title,
                    "url": url,
                    "content_text": "",
                    "content_html": "",
                    "author": "",
                    "date": "",
                    "error": "fetch_failed"
                })
                print(f"   失败: 未能获取内容")
        except Exception as e:
            results.append({
                "title": title,
                "url": url,
                "content_text": "",
                "content_html": "",
                "author": "",
                "date": "",
                "error": str(e)
            })
            print(f"   错误: {e}")

        if i < total:
            time.sleep(delay)

    return results


def main():
    parser = argparse.ArgumentParser(description="GameLook文章爬虫")
    parser.add_argument("file", nargs="?", default="gamelook文章链接.txt",
                        help="GameLook文章链接文件路径（默认: gamelook文章链接.txt）")
    parser.add_argument("-d", "--delay", type=int, default=3,
                        help="请求间隔（秒），默认3秒")

    args = parser.parse_args()

    filepath = args.file

    # 检查文件是否存在
    if not Path(filepath).exists():
        print(f"错误: 文件不存在 - {filepath}")
        return

    # 读取文章列表
    print(f"读取文件: {filepath}")
    articles = read_gamelook_file(filepath)
    print(f"共读取 {len(articles)} 篇文章\n")

    if not articles:
        print("错误: 文件中没有有效的文章")
        return

    # 批量抓取
    results = batch_fetch_gamelook(articles, args.delay)

    # 统计
    success = sum(1 for r in results if r.get("content_text") and not r.get("error"))
    failed = len(results) - success

    print("\n" + "=" * 60)
    print(f"抓取完成！成功: {success}, 失败: {failed}")
    print("=" * 60)

    # 保存结果
    storage = ArticleStorage("gamelook")
    filepath_saved = storage.save(results)
    print(f"\n结果已保存到: {filepath_saved}")

    # 保存失败的文章信息
    failed_articles = [r for r in results if r.get("error")]
    if failed_articles:
        failed_file = Path("data") / "gamelook_failed.txt"
        with open(failed_file, "w", encoding="utf-8") as f:
            for article in failed_articles:
                f.write(f"{article['title']}\n{article['url']}\n\n")
        print(f"失败文章已保存到: {failed_file}")


if __name__ == "__main__":
    main()