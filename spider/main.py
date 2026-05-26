#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信文章爬虫 - 主程序
通过搜狗搜索爬取微信公众文章
"""

import sys
import time
import argparse
from config import REQUEST_DELAY, MAX_PAGES
from sougou_search import SogouSearch
from article_parser import ArticleParser
from storage import ArticleStorage


class WechatSpider:
    """微信文章爬虫"""

    def __init__(self, keyword: str, pages: int = 1, full_content: bool = False):
        self.keyword = keyword
        self.pages = pages
        self.full_content = full_content
        self.searcher = SogouSearch()
        self.parser = ArticleParser()
        self.storage = ArticleStorage(keyword)

    def run(self):
        """运行爬虫"""
        print("=" * 50)
        print(f"微信文章爬虫 - 关键词: {self.keyword}")
        print("=" * 50)

        # Step 1: 搜索文章
        print("\n[1/2] 正在搜索文章...")
        articles = self.searcher.search_articles(self.keyword, pages=self.pages)

        if not articles:
            print("\n" + "=" * 50)
            print("未找到任何文章！")
            print("=" * 50)
            print("\n可能原因：")
            print("1. 搜狗微信有反爬机制，requests无法获取动态内容")
            print("2. 网络问题或IP被限制")
            print("\n替代方案：")
            print("方案A: 使用 Selenium 版本 (需要Chrome浏览器)")
            print("  python selenium_search.py")
            print("\n方案B: 直接抓取已知文章链接")
            print("  已有微信文章链接？直接使用 article_parser.py 抓取")
            print("\n方案C: 使用 RSS 服务")
            print("  访问 feeddd.com 搜索公众号RSS")
            return

        print(f"找到 {len(articles)} 篇文章")

        # Step 2: 抓取全文（可选）
        if self.full_content:
            print("\n[2/2] 正在抓取文章全文...")
            articles = self._fetch_full_content(articles)
        else:
            print("\n[2/2] 保存搜索结果...")

        # Step 3: 保存结果
        filepath = self.storage.save(articles)
        print(f"\n完成！已保存到: {filepath}")

    def _fetch_full_content(self, articles: list) -> list:
        """抓取每篇文章的全文内容"""
        results = []

        for i, article in enumerate(articles, 1):
            print(f"\n[{i}/{len(articles)}] 正在抓取: {article['title'][:30]}...")

            # 抓取全文
            full_article = self.parser.fetch_article(article["url"])

            if full_article:
                # 合并数据
                article.update({
                    "content_text": full_article.get("content_text", ""),
                    "content_html": full_article.get("content_html", ""),
                    "cover_image": full_article.get("cover_image", "")
                })
                print(f"   成功！字数: {len(article.get('content_text', ''))}")
            else:
                print(f"   失败！")

            results.append(article)

            # 延迟避免被封
            if i < len(articles):
                time.sleep(REQUEST_DELAY)

        return results


def main():
    parser = argparse.ArgumentParser(description="微信文章爬虫")
    parser.add_argument("keyword", help="搜索关键词（公众号名称）")
    parser.add_argument("-p", "--pages", type=int, default=1, help="搜索页数（默认1页，10篇文章/页）")
    parser.add_argument("-f", "--full", action="store_true", help="抓取文章全文")

    args = parser.parse_args()

    spider = WechatSpider(
        keyword=args.keyword,
        pages=min(args.pages, MAX_PAGES),
        full_content=args.full
    )
    spider.run()


if __name__ == "__main__":
    main()
