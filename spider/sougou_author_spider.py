#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜狗微信搜索 - 按作者名爬取文章
从搜狗微信搜索结果中筛选特定作者的文章并抓取全文

用法: python sougou_author_spider.py
"""

import re
import time
import requests
import urllib.parse
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Optional, Dict, List

from config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY
from storage import ArticleStorage

SEARCH_QUERY = "托马斯之颅"
AUTHOR_NAME = "托马斯之颅"
MAX_PAGES = 10

# 作者署名模式：用于在文章中判断是否是该作者所写
AUTHOR_PATTERNS = [
    re.compile(r"文\s*[\/／]\s*托馬斯之顱"),
    re.compile(r"文\s*[\/／]\s*托马斯之颅"),
    re.compile(r"作者[：:]\s*托馬斯之顱"),
    re.compile(r"作者[：:]\s*托马斯之颅"),
    re.compile(r"撰文[：:]\s*托馬斯之顱"),
    re.compile(r"撰文[：:]\s*托马斯之颅"),
    re.compile(r"原创[：:]\s*托馬斯之顱"),
    re.compile(r"原创[：:]\s*托马斯之颅"),
    re.compile(r"编辑[：:]\s*托馬斯之顱"),
    re.compile(r"编辑[：:]\s*托马斯之颅"),
]


class SogouAuthorSpider:
    """搜狗微信按作者爬虫"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })

    def search_pages(self) -> List[Dict[str, str]]:
        """搜索所有页，返回文章列表"""
        all_items = []

        # 初始延迟，模拟人类访问行为
        time.sleep(2)

        for page in range(1, MAX_PAGES + 1):
            print(f"  搜索第 {page}/{MAX_PAGES} 页...")
            items = self._search_page(page)
            if not items:
                break
            all_items.extend(items)
            print(f"    找到 {len(items)} 条，累计 {len(all_items)} 条")
            time.sleep(REQUEST_DELAY)

        return all_items

    def _search_page(self, page: int) -> List[Dict[str, str]]:
        """搜索单页"""
        encoded_query = urllib.parse.quote(SEARCH_QUERY)
        url = (
            f"https://weixin.sogou.com/weixin?"
            f"query={encoded_query}&type=2&page={page}&ie=utf8&p=01030402&dp=1"
        )
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"    搜索请求失败: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []

        for li in soup.select(".news-list li"):
            try:
                # 标题和跳转链接
                title_elem = li.select_one("h3 a")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                redirect_href = title_elem.get("href", "")

                # 摘要/描述文本
                txt_box = li.select_one(".txt-box")
                snippet = txt_box.get_text(separator="\n", strip=True) if txt_box else ""

                # 公众号名称
                account_elem = li.select_one(".s-p") or li.select_one(".account")
                account = account_elem.get_text(strip=True) if account_elem else ""

                # 日期
                date_elem = li.select_one(".s2") or li.select_one(".date")
                date = date_elem.get_text(strip=True) if date_elem else ""

                items.append({
                    "title": title,
                    "redirect_url": "https://weixin.sogou.com" + redirect_href,
                    "snippet": snippet,
                    "account": account,
                    "date": date,
                })
            except Exception:
                continue

        return items

    def resolve_wechat_url(self, redirect_url: str, retry: int = 3) -> Optional[str]:
        """从搜狗跳转链接解析出微信文章真实URL，支持重试"""
        for attempt in range(retry):
            try:
                resp = self.session.get(redirect_url, timeout=REQUEST_TIMEOUT)
                resp.encoding = "utf-8"

                fragments = re.findall(r"url \+= '([^']*)';", resp.text)
                if fragments:
                    return "".join(fragments)

                # 可能触发了反爬，重置session重试
                if "antispider" in resp.text.lower() or len(resp.text) < 200:
                    self._reset_session()
                    time.sleep(3 * (attempt + 1))
                    continue

            except Exception:
                time.sleep(2)
                continue
        return None

    def _reset_session(self):
        """重置session获取新cookie"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })

    def fetch_and_filter_article(self, wx_url: str) -> Optional[Dict[str, str]]:
        """获取微信文章并判断是否为该作者所写"""
        try:
            resp = self.session.get(wx_url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException:
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # 标题
        title = ""
        for sel in ["h1#activity-name", "h1.rich_media_title", "h1"]:
            elem = soup.select_one(sel)
            if elem:
                title = elem.get_text(strip=True)
                break

        # 公众号名称
        account = ""
        for sel in ["span#js_name", "a.rich_media_meta_link"]:
            elem = soup.select_one(sel)
            if elem:
                account = elem.get_text(strip=True)
                break

        # 日期
        date = ""
        for sel in ["span#publish_time", "em#post-date", ".rich_media_meta_text"]:
            elem = soup.select_one(sel)
            if elem:
                date = elem.get_text(strip=True)
                break

        # 正文
        content_elem = soup.select_one("div#js_content")
        if not content_elem:
            return None
        content_html = str(content_elem)
        content_text = content_elem.get_text(separator="\n", strip=True)

        # 判断是否为该作者所写
        is_author = self._check_author(content_text, account, title)
        if not is_author:
            return None

        # 封面图
        cover_image = ""
        first_img = content_elem.select_one("img")
        if first_img:
            cover_image = first_img.get("src") or first_img.get("data-src", "")

        return {
            "title": title,
            "url": wx_url,
            "author": AUTHOR_NAME,
            "account": account,
            "date": date,
            "content_html": content_html,
            "content_text": content_text,
            "cover_image": cover_image,
        }

    def _check_author(self, text: str, account: str, title: str) -> bool:
        """检查文章是否由目标作者撰写"""
        # 1. 检查明确的作者署名
        for pattern in AUTHOR_PATTERNS:
            if pattern.search(text):
                return True

        # 2. 标题直含作者名（如"托马斯之颅的来历"）
        if AUTHOR_NAME in title:
            return True

        # 3. 文章开头附近出现作者署名
        head = text[:500]
        if f"文/{AUTHOR_NAME}" in head or f"文／{AUTHOR_NAME}" in head:
            return True
        if f"作者：{AUTHOR_NAME}" in head or f"作者: {AUTHOR_NAME}" in head:
            return True
        if f"原创：{AUTHOR_NAME}" in head or f"原创: {AUTHOR_NAME}" in head:
            return True

        # 4. 文章末尾出现作者署名（常见于公众号文章末尾）
        tail = text[-300:]
        if AUTHOR_NAME in tail and ("文/" in tail or "作者" in tail or "撰文" in tail):
            return True

        return False

    def crawl_all(self) -> List[Dict[str, str]]:
        """完整爬取流程"""
        # Step 1: 搜索
        print(f"\n正在搜狗微信搜索[{SEARCH_QUERY}]...")
        print(f"最多搜索 {MAX_PAGES} 页\n")
        search_results = self.search_pages()

        if not search_results:
            print("未找到搜索结果")
            return []

        print(f"\n共搜索到 {len(search_results)} 条结果\n")

        # Step 2: 逐条解析URL、抓取、筛选
        results = []
        total = len(search_results)

        print("=" * 60)
        print(f"开始解析文章并筛选作者[{AUTHOR_NAME}]的文章")
        print("=" * 60)

        for i, item in enumerate(search_results, 1):
            title_preview = item["title"][:50]
            print(f"\n[{i}/{total}] {title_preview}{'...' if len(item['title']) > 50 else ''}")

            # 解析真实URL
            wx_url = self.resolve_wechat_url(item["redirect_url"])
            if not wx_url:
                print("    跳过: 无法解析微信URL")
                continue

            # 抓取并筛选
            article = self.fetch_and_filter_article(wx_url)
            if article:
                results.append(article)
                word_count = len(article["content_text"])
                print(f"    [OK] 作者确认! 字数: {word_count}")
            else:
                print(f"    [SKIP] 非目标作者文章，跳过")

            if i < total:
                time.sleep(5)  # 至少5秒间隔，避免被限流

        return results


def main():
    print("=" * 60)
    print(f"搜狗微信作者爬虫")
    print(f"搜索词: {SEARCH_QUERY} | 目标作者: {AUTHOR_NAME}")
    print("=" * 60)

    spider = SogouAuthorSpider()
    results = spider.crawl_all()

    if not results:
        print("\n未找到匹配的文章")
        return

    # 统计
    total_chars = sum(len(r.get("content_text", "")) for r in results)
    print("\n" + "=" * 60)
    print(f"筛选完成！共找到 {len(results)} 篇 {AUTHOR_NAME} 的文章")
    print(f"总字数: {total_chars:,}, 平均: {total_chars // len(results):,} 字/篇")
    print("=" * 60)

    # 保存
    storage = ArticleStorage(f"sougou_{AUTHOR_NAME}")
    filepath = storage.save(results)
    print(f"\n结果已保存到: {filepath}")

    # 列出文章标题
    print("\n文章列表:")
    for i, a in enumerate(results, 1):
        print(f"  [{i}] {a['title'][:60]}")


if __name__ == "__main__":
    main()
