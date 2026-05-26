"""
搜狗微信搜索模块
通过搜狗搜索获取公众号文章链接
"""
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from config import SOGOU_SEARCH_URL, USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY


class SogouSearch:
    """搜狗微信搜索"""

    def __init__(self):
        self.session = requests.Session()
        # 完整的请求头，模拟真实浏览器
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.8,en;q=0.6",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://weixin.sogou.com/",
            "Upgrade-Insecure-Requests": "1"
        })
        # 先访问首页获取Cookie
        try:
            self.session.get("https://weixin.sogou.com/", timeout=10)
        except:
            pass

    def search_articles(self, keyword: str, pages: int = 1) -> List[Dict[str, str]]:
        """
        搜索文章

        Args:
            keyword: 搜索关键词（公众号名称或文章关键词）
            pages: 搜索页数

        Returns:
            文章列表，每项包含 title, url, author, date, abstract
        """
        articles = []

        for page in range(1, pages + 1):
            print(f"正在搜索第 {page}/{pages} 页...")

            params = {
                "type": "1",
                "query": keyword,
                "ie": "utf8",
                "page": page
            }

            try:
                response = self.session.get(
                    SOGOU_SEARCH_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )
                response.raise_for_status()

                page_articles = self._parse_search_results(response.text)
                articles.extend(page_articles)

                if page < pages:
                    time.sleep(REQUEST_DELAY)

            except requests.RequestException as e:
                print(f"搜索失败: {e}")
                continue

        return articles

    def _parse_search_results(self, html: str) -> List[Dict[str, str]]:
        """解析搜索结果页面"""
        soup = BeautifulSoup(html, "lxml")
        articles = []

        # 查找所有文章条目
        items = soup.select("li.list_item")

        for item in items:
            try:
                # 提取标题和链接
                title_elem = item.select_one("div.txt_info h3 a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                url = title_elem.get("href", "")

                # 提取作者/公众号名称
                author = ""
                author_elem = item.select_one("div.txt_info div.s_pup a")
                if author_elem:
                    author = author_elem.get_text(strip=True)

                # 提取日期
                date = ""
                date_elem = item.select_one("div.txt_info div.s_time")
                if date_elem:
                    date = date_elem.get_text(strip=True)

                # 提取摘要
                abstract = ""
                abstract_elem = item.select_one("div.txt_info p.descrip")
                if abstract_elem:
                    abstract = abstract_elem.get_text(strip=True)

                # 提取封面图
                img_url = ""
                img_elem = item.select_one("div.img_box img")
                if img_elem:
                    img_url = img_elem.get("src", "")

                articles.append({
                    "title": title,
                    "url": url,
                    "author": author,
                    "date": date,
                    "abstract": abstract,
                    "img_url": img_url
                })

            except Exception as e:
                print(f"解析文章条目失败: {e}")
                continue

        return articles

    def search_by_author(self, author_name: str, pages: int = 1) -> List[Dict[str, str]]:
        """
        搜索特定公众号的文章

        Args:
            author_name: 公众号名称
            pages: 搜索页数

        Returns:
            文章列表
        """
        return self.search_articles(author_name, pages)


def main():
    """测试函数"""
    searcher = SogouSearch()

    # 测试搜索
    print("=" * 50)
    print("测试搜狗微信搜索")
    print("=" * 50)

    articles = searcher.search_articles("人民日报", pages=1)

    print(f"\n获取到 {len(articles)} 篇文章:\n")

    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   公众号: {article['author']}")
        print(f"   日期: {article['date']}")
        print(f"   链接: {article['url']}")
        print()


if __name__ == "__main__":
    main()
