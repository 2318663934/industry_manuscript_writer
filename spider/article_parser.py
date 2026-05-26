"""
文章解析模块
从微信文章页面提取正文内容
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict
from config import USER_AGENT, REQUEST_TIMEOUT


class ArticleParser:
    """微信文章解析器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_article(self, url: str) -> Optional[Dict[str, str]]:
        """
        获取文章内容

        Args:
            url: 文章链接

        Returns:
            文章信息字典，包含 title, author, date, content, html 等
        """
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            return self._parse_article(response.text, url)

        except requests.RequestException as e:
            print(f"获取文章失败: {e}")
            return None

    def _parse_article(self, html: str, url: str) -> Dict[str, str]:
        """解析文章页面"""
        soup = BeautifulSoup(html, "lxml")

        # 提取标题
        title = ""
        title_elem = soup.select_one("h1#activity-name")
        if not title_elem:
            title_elem = soup.select_one("h1.rich_media_title")
        if title_elem:
            title = title_elem.get_text(strip=True)

        # 提取作者
        author = ""
        author_elem = soup.select_one("span#js_name")
        if not author_elem:
            author_elem = soup.select_one("a.rich_media_meta.rich_media_meta_link")
        if author_elem:
            author = author_elem.get_text(strip=True)

        # 提取日期
        date = ""
        date_elem = soup.select_one("span#publish_time")
        if not date_elem:
            date_elem = soup.select_one("em#post-date")
        if date_elem:
            date = date_elem.get_text(strip=True)

        # 提取正文内容 (js_content 是微信文章正文的容器)
        content_html = ""
        content_elem = soup.select_one("div#js_content")
        if content_elem:
            # 清理样式类
            for tag in content_elem.find_all(class_="rich_media_content"):
                pass
            content_html = str(content_elem)

        # 提取纯文本内容
        content_text = ""
        if content_elem:
            content_text = content_elem.get_text(separator="\n", strip=True)

        # 提取封面图
        cover_image = ""
        cover_elem = soup.select_one("div#js_content img")
        if cover_elem:
            cover_image = cover_elem.get("src", "")

        return {
            "title": title,
            "author": author,
            "date": date,
            "content_html": content_html,
            "content_text": content_text,
            "cover_image": cover_image,
            "url": url
        }

    def fetch_gamelook_article(self, url: str) -> Optional[Dict[str, str]]:
        """
        获取GameLook文章内容

        Args:
            url: GameLook文章链接

        Returns:
            文章信息字典，包含 title, author, date, content, html 等
        """
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            return self._parse_gamelook_article(response.text, url)

        except requests.RequestException as e:
            print(f"获取文章失败: {e}")
            return None

    def _parse_gamelook_article(self, html: str, url: str) -> Dict[str, str]:
        """解析GameLook文章页面"""
        soup = BeautifulSoup(html, "lxml")

        # 提取标题 - GameLook通常使用h1.article-title或.entry-title
        title = ""
        title_elem = soup.select_one("h1.article-title")
        if not title_elem:
            title_elem = soup.select_one("h1.entry-title")
        if not title_elem:
            title_elem = soup.select_one("h1")
        if title_elem:
            title = title_elem.get_text(strip=True)

        # 提取作者 - GameLook通常在.info或.author类中
        author = ""
        author_elem = soup.select_one("span.author")
        if not author_elem:
            author_elem = soup.select_one("span.byline")
        if not author_elem:
            author_elem = soup.select_one(".info span")
        if not author_elem:
            author_elem = soup.select_one("[rel='author']")
        if author_elem:
            author = author_elem.get_text(strip=True)

        # 提取日期 - GameLook使用time标签或.date类
        date = ""
        date_elem = soup.select_one("time.entry-date")
        if not date_elem:
            date_elem = soup.select_one("span.date")
        if not date_elem:
            date_elem = soup.select_one("time")
        if date_elem:
            date = date_elem.get_text(strip=True)
            # 如果有datetime属性，优先使用
            if date_elem.name == "time" and date_elem.get("datetime"):
                date = date_elem.get("datetime")

        # 提取正文内容 - GameLook通常使用.entry-content或.article-content
        content_html = ""
        content_elem = soup.select_one("div.entry-content")
        if not content_elem:
            content_elem = soup.select_one("div.article-content")
        if not content_elem:
            content_elem = soup.select_one("div.post-content")
        if not content_elem:
            content_elem = soup.select_one("div.content")
        if content_elem:
            content_html = str(content_elem)

        # 提取纯文本内容
        content_text = ""
        if content_elem:
            content_text = content_elem.get_text(separator="\n", strip=True)

        # 提取封面图 - 通常在文章内容区域的第一张图
        cover_image = ""
        if content_elem:
            first_img = content_elem.select_one("img")
            if first_img:
                cover_image = first_img.get("src") or first_img.get("data-src", "")

        return {
            "title": title,
            "author": author,
            "date": date,
            "content_html": content_html,
            "content_text": content_text,
            "cover_image": cover_image,
            "url": url
        }

    def extract_images(self, html: str) -> list:
        """提取文章中的所有图片"""
        soup = BeautifulSoup(html, "lxml")
        images = []

        for img in soup.select("img"):
            src = img.get("data-src") or img.get("src")
            if src and src.startswith("http"):
                images.append(src)

        return images


def main():
    """测试函数"""
    parser = ArticleParser()

    # 测试文章URL（可以用搜狗搜索返回的链接测试）
    test_url = "https://mp.weixin.qq.com/s/example"

    print("=" * 50)
    print("测试文章解析")
    print("=" * 50)
    print(f"\n请使用搜狗搜索获取真实文章链接进行测试\n")


if __name__ == "__main__":
    main()
