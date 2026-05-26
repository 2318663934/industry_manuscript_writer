#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
触乐(chuapp.com)作者文章爬虫
爬取指定作者的全部文章
用法: python chuapp_spider.py
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Optional, Dict, List

from config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY
from storage import ArticleStorage

BASE_URL = "https://www.chuapp.com"
AUTHOR_UID = 41
AUTHOR_NAME = "祝佳音"
START_PAGE = 1
END_PAGE = 14


class ChuappSpider:
    """触乐文章爬虫"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

    def get_article_links_from_page(self, page: int) -> List[Dict[str, str]]:
        """从作者列表页获取文章链接和元信息"""
        url = f"{BASE_URL}/user/author/uid/{AUTHOR_UID}/p/{page}.html"
        print(f"  获取列表: {url}")

        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"  错误: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        articles = []

        # 文章卡片: div.category-list 下的 a.fn-clear
        for a in soup.select("div.category-list a.fn-clear[href]"):
            href = a["href"]
            if "/article/" not in href:
                continue
            if not href.startswith("http"):
                href = BASE_URL + href

            # 标题在 dt 标签中
            title = ""
            dt = a.select_one("dt")
            if dt:
                title = dt.get_text(strip=True)
            if not title:
                title = a.get("title", "")

            # 作者在 em 标签中
            author = AUTHOR_NAME
            em = a.select_one("em")
            if em:
                author = em.get_text(strip=True)

            # 日期在 span.fn-left 中（格式：作者名 + 日期）
            date = ""
            span_fn_left = a.select_one("span.fn-left")
            if span_fn_left:
                full_text = span_fn_left.get_text(strip=True)
                # 去掉作者名部分，剩下的就是日期
                if author and full_text.startswith(author):
                    date = full_text[len(author):]

            # 摘要/导语在 dt 后面的 dd 中
            summary = ""
            dds = a.select("dd")
            for dd in dds:
                # 跳过 meta 信息行（含 span.fn-clear）
                if dd.select_one("span.fn-left") or dd.select_one("span.fn-right"):
                    continue
                text = dd.get_text(strip=True)
                if text:
                    summary = text
                    break

            articles.append({
                "title": title,
                "url": href,
                "author": author,
                "date": date,
                "summary": summary,
            })

        # 去重
        seen = set()
        unique_articles = []
        for art in articles:
            if art["url"] not in seen:
                seen.add(art["url"])
                unique_articles.append(art)

        print(f"  找到 {len(unique_articles)} 篇文章")
        return unique_articles

    def get_all_article_links(self) -> List[Dict[str, str]]:
        """获取所有页面的文章链接"""
        all_articles = []
        print(f"\n正在获取作者「{AUTHOR_NAME}」的文章列表...")
        print(f"页码范围: {START_PAGE} - {END_PAGE} (共{END_PAGE}页)\n")

        for page in range(START_PAGE, END_PAGE + 1):
            articles = self.get_article_links_from_page(page)
            all_articles.extend(articles)
            if page < END_PAGE:
                time.sleep(REQUEST_DELAY)

        # 全局去重
        seen = set()
        unique_articles = []
        for art in all_articles:
            if art["url"] not in seen:
                seen.add(art["url"])
                unique_articles.append(art)

        print(f"\n共获取 {len(unique_articles)} 篇不重复文章\n")
        return unique_articles

    def fetch_article(self, url: str) -> Optional[Dict[str, str]]:
        """获取单篇文章内容"""
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"    请求失败: {e}")
            return None

        return self._parse_article(resp.text, url)

    def _parse_article(self, html: str, url: str) -> Dict[str, str]:
        """解析文章详情页面"""
        soup = BeautifulSoup(html, "lxml")

        # 标题: h1
        title = ""
        h1 = soup.select_one("h1")
        if h1:
            title = h1.get_text(strip=True)

        # 正文: .the-content
        content_html = ""
        content_text = ""
        content_elem = soup.select_one(".the-content")
        if content_elem:
            content_html = str(content_elem)
            content_text = content_elem.get_text(separator="\n", strip=True)

        # 封面图
        cover_image = ""
        if content_elem:
            first_img = content_elem.select_one("img")
            if first_img:
                cover_image = first_img.get("src") or first_img.get("data-src", "")

        # 作者和日期从 .content.single 中提取
        author = AUTHOR_NAME
        date = ""
        meta_elem = soup.select_one(".content.single")
        if meta_elem:
            meta_text = meta_elem.get_text(separator="\n", strip=True)
            # 格式: "...编辑祝佳音2026年03月10日 19时57分..."
            date_match = re.search(r"(\d{4}年\d{2}月\d{2}日\s*\d{2}时\d{2}分)", meta_text)
            if date_match:
                date = date_match.group(1)

        return {
            "title": title,
            "author": author,
            "date": date,
            "content_html": content_html,
            "content_text": content_text,
            "cover_image": cover_image,
            "url": url,
        }

    def crawl_all(self, delay: int = REQUEST_DELAY) -> List[Dict[str, str]]:
        """爬取所有文章"""
        # Step 1: 获取文章链接
        article_links = self.get_all_article_links()

        if not article_links:
            print("未找到任何文章链接，退出")
            return []

        # Step 2: 逐篇抓取
        results = []
        total = len(article_links)

        print("=" * 60)
        print(f"开始抓取文章内容，共 {total} 篇")
        print("=" * 60)

        for i, art in enumerate(article_links, 1):
            title_preview = art["title"][:40]
            print(f"\n[{i}/{total}] {title_preview}{'...' if len(art['title']) > 40 else ''}")
            print(f"    URL: {art['url']}")

            try:
                article = self.fetch_article(art["url"])
                if article and article.get("content_text"):
                    # 如果详情页标题为空，使用列表页的标题
                    if not article.get("title"):
                        article["title"] = art["title"]
                    if not article.get("date"):
                        article["date"] = art.get("date", "")
                    results.append(article)
                    word_count = len(article["content_text"])
                    print(f"    成功! 字数: {word_count}")
                else:
                    results.append({
                        "title": art["title"],
                        "url": art["url"],
                        "content_text": "",
                        "content_html": "",
                        "author": art.get("author", AUTHOR_NAME),
                        "date": art.get("date", ""),
                        "cover_image": "",
                        "summary": art.get("summary", ""),
                        "error": "fetch_failed",
                    })
                    print(f"    失败: 未能获取内容")
            except Exception as e:
                results.append({
                    "title": art["title"],
                    "url": art["url"],
                    "content_text": "",
                    "content_html": "",
                    "author": art.get("author", AUTHOR_NAME),
                    "date": art.get("date", ""),
                    "cover_image": "",
                    "summary": art.get("summary", ""),
                    "error": str(e),
                })
                print(f"    错误: {e}")

            if i < total:
                time.sleep(delay)

        return results


def main():
    print("=" * 60)
    print(f"触乐文章爬虫 - 作者: {AUTHOR_NAME}")
    print("=" * 60)

    spider = ChuappSpider()
    results = spider.crawl_all()

    # 统计
    success = sum(1 for r in results if r.get("content_text") and not r.get("error"))
    failed = len(results) - success

    print("\n" + "=" * 60)
    print(f"抓取完成！成功: {success}, 失败: {failed}")
    print("=" * 60)

    # 保存
    storage = ArticleStorage("chuapp_zhujiayin")
    filepath = storage.save(results)
    print(f"\n结果已保存到: {filepath}")

    # 保存失败列表
    failed_articles = [r for r in results if r.get("error")]
    if failed_articles:
        failed_file = Path("data") / "chuapp_failed.txt"
        with open(failed_file, "w", encoding="utf-8") as f:
            for art in failed_articles:
                f.write(f"{art['title']}\n{art['url']}\n\n")
        print(f"失败文章已保存到: {failed_file}")


if __name__ == "__main__":
    main()
