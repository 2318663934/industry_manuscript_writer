#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎文章爬虫 - 支持专栏文章和用户回答
用法:
  python zhihu_spider.py                    # 爬取专栏文章
  python zhihu_spider.py --mode answers     # 爬取回答(需要cookie)
  python zhihu_spider.py --cookie "your_cookie_string"
"""

import re
import time
import json
import argparse
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Optional, Dict, List

from config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY
from storage import ArticleStorage

USER_TOKEN = "ThomasHead"
USER_NAME = "托马斯之颅"
COLUMN_ID = "ThomasHead"
COLUMN_NAME = "托马斯之颅的脑中世界"


class ZhihuSpider:
    """知乎爬虫"""

    def __init__(self, cookie: str = ""):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        if cookie:
            self.session.headers["Cookie"] = cookie

    # ========== 专栏文章 ==========

    def fetch_column_articles(self) -> List[Dict[str, str]]:
        """通过API获取专栏全部文章"""
        print(f"\n正在获取专栏「{COLUMN_NAME}」的文章...")
        all_articles = []
        limit = 20
        offset = 0

        while True:
            url = f"https://zhuanlan.zhihu.com/api/columns/{COLUMN_ID}/articles?limit={limit}&offset={offset}"
            try:
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"  获取列表失败 (offset={offset}): {e}")
                break

            items = data.get("data", [])
            if not items:
                break

            for item in items:
                all_articles.append(self._parse_column_item(item))

            paging = data.get("paging", {})
            if paging.get("is_end", False):
                break

            offset += limit
            print(f"  已获取 {len(all_articles)}/{paging.get('totals', '?')} 篇")
            time.sleep(REQUEST_DELAY // 2)

        print(f"  专栏共 {len(all_articles)} 篇文章\n")
        return all_articles

    def _parse_column_item(self, item: dict) -> Dict[str, str]:
        """解析专栏API返回的单篇文章"""
        content = item.get("content", "")
        content_text = ""
        if content:
            soup = BeautifulSoup(content, "lxml")
            content_text = soup.get_text(separator="\n", strip=True)

        created_ts = item.get("created", 0)
        date = ""
        if created_ts:
            import datetime
            date = datetime.datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M:%S")

        author = item.get("author", {})
        author_name = author.get("name", USER_NAME) if isinstance(author, dict) else USER_NAME

        return {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "author": author_name,
            "date": date,
            "content_html": content,
            "content_text": content_text,
            "cover_image": item.get("title_image", ""),
            "excerpt": item.get("excerpt", ""),
            "voteup_count": item.get("voteup_count", 0),
            "comment_count": item.get("comment_count", 0),
        }

    # ========== 用户回答 (需要cookie) ==========

    def fetch_user_answers(self) -> List[Dict[str, str]]:
        """通过API获取用户回答(需要登录cookie)"""
        if not self.session.headers.get("Cookie"):
            print("错误: 获取回答需要提供登录后的Cookie")
            print("请从浏览器复制知乎的Cookie后使用 --cookie 参数")
            return []

        print(f"\n正在获取用户「{USER_NAME}」的回答...")
        all_answers = []
        limit = 20
        offset = 0

        while True:
            # 尝试多个可能的API端点
            url = f"https://www.zhihu.com/api/v4/members/{USER_TOKEN}/answers?include=data[*].content,excerpt&limit={limit}&offset={offset}"
            try:
                resp = self.session.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    headers={
                        "Referer": f"https://www.zhihu.com/people/{USER_TOKEN}/answers",
                        "X-Requested-With": "fetch",
                    },
                )
                if resp.status_code != 200:
                    print(f"  API返回 {resp.status_code}: {resp.text[:200]}")
                    break
                data = resp.json()
            except Exception as e:
                print(f"  请求失败 (offset={offset}): {e}")
                break

            items = data.get("data", [])
            if not items:
                break

            paging = data.get("paging", {})
            totals = paging.get("totals", 0)

            for item in items:
                all_answers.append(self._parse_answer_item(item))

            # 去重
            seen_urls = set()
            deduped = []
            for a in all_answers:
                url = a.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    deduped.append(a)
            all_answers = deduped

            if paging.get("is_end", False) or len(all_answers) >= totals:
                break

            offset += limit
            print(f"  已获取 {len(all_answers)}/{totals} 条回答")
            time.sleep(REQUEST_DELAY)

        print(f"  共获取 {len(all_answers)} 条回答\n")
        return all_answers

    def _parse_answer_item(self, item: dict) -> Dict[str, str]:
        """解析回答API返回的数据"""
        content = item.get("content", "")
        content_text = ""
        if content:
            soup = BeautifulSoup(content, "lxml")
            content_text = soup.get_text(separator="\n", strip=True)

        question = item.get("question", {})
        question_title = question.get("title", "") if isinstance(question, dict) else ""

        created_ts = item.get("created_time", item.get("updated_time", 0))
        date = ""
        if created_ts:
            import datetime
            date = datetime.datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M:%S")

        author = item.get("author", {})
        author_name = author.get("name", USER_NAME) if isinstance(author, dict) else USER_NAME

        return {
            "title": question_title,
            "url": item.get("url", ""),
            "author": author_name,
            "date": date,
            "content_html": content,
            "content_text": content_text,
            "cover_image": "",
            "excerpt": item.get("excerpt", ""),
            "voteup_count": item.get("voteup_count", 0),
            "comment_count": item.get("comment_count", 0),
        }

    # ========== 爬取入口 ==========

    def crawl_all(self, mode: str = "column", delay: int = REQUEST_DELAY) -> List[Dict[str, str]]:
        """爬取入口"""
        if mode == "answers":
            return self.fetch_user_answers()
        else:
            return self.fetch_column_articles()


def main():
    parser = argparse.ArgumentParser(description="知乎文章爬虫")
    parser.add_argument("--mode", choices=["column", "answers"], default="column",
                        help="爬取模式: column(专栏) / answers(回答)")
    parser.add_argument("--cookie", type=str, default="",
                        help="知乎登录Cookie(爬取回答时必需)")
    parser.add_argument("--delay", type=int, default=REQUEST_DELAY,
                        help=f"请求间隔(秒)，默认{REQUEST_DELAY}")

    args = parser.parse_args()

    mode_desc = "专栏文章" if args.mode == "column" else "用户回答"
    print("=" * 60)
    print(f"知乎爬虫 - {mode_desc} - 用户: {USER_NAME}")
    print("=" * 60)

    spider = ZhihuSpider(cookie=args.cookie)
    results = spider.crawl_all(mode=args.mode, delay=args.delay)

    if not results:
        print("未获取到任何文章")
        return

    # 统计
    success = sum(1 for r in results if r.get("content_text") and len(r["content_text"]) > 50)
    failed = len(results) - success

    print("\n" + "=" * 60)
    print(f"抓取完成！成功: {success}, 失败: {failed}")
    if results:
        total_chars = sum(len(r.get("content_text", "")) for r in results)
        print(f"总字数: {total_chars:,}, 平均: {total_chars // len(results):,} 字/篇")
    print("=" * 60)

    # 保存
    suffix = "column" if args.mode == "column" else "answers"
    storage = ArticleStorage(f"zhihu_{USER_TOKEN}_{suffix}")
    filepath = storage.save(results)
    print(f"\n结果已保存到: {filepath}")

    # 保存失败列表
    failed_articles = [r for r in results if r.get("error") or len(r.get("content_text", "")) < 50]
    if failed_articles:
        failed_file = Path("data") / f"zhihu_{suffix}_failed.txt"
        with open(failed_file, "w", encoding="utf-8") as f:
            for art in failed_articles:
                f.write(f"{art['title']}\n{art['url']}\n\n")
        print(f"失败记录已保存到: {failed_file}")


if __name__ == "__main__":
    main()
