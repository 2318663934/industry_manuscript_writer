"""
搜狗微信搜索 - Selenium版本
通过浏览器自动化获取搜索结果
"""
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from config import SOGOU_SEARCH_URL, USER_AGENT, REQUEST_DELAY


class SogouSearchSelenium:
    """基于Selenium的搜狗微信搜索"""

    def __init__(self):
        self.driver = self._init_driver()

    def _init_driver(self):
        """初始化Chrome浏览器"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 无头模式
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"--user-agent={USER_AGENT}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # 防检测
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """
        })

        return driver

    def search_articles(self, keyword: str, pages: int = 1) -> List[Dict[str, str]]:
        """
        搜索文章

        Args:
            keyword: 搜索关键词
            pages: 搜索页数

        Returns:
            文章列表
        """
        all_articles = []

        for page in range(1, pages + 1):
            print(f"正在搜索第 {page}/{pages} 页...")

            if page == 1:
                # 首次访问搜索页面
                url = f"{SOGOU_SEARCH_URL}?type=1&query={keyword}&ie=utf8"
            else:
                # 后续翻页
                url = f"{SOGOU_SEARCH_URL}?type=1&query={keyword}&ie=utf8&page={page}"

            try:
                self.driver.get(url)
                time.sleep(3)  # 等待页面加载

                # 等待文章列表加载
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "li.list_item"))
                )

                # 获取页面源码
                html = self.driver.page_source
                page_articles = self._parse_search_results(html)
                all_articles.extend(page_articles)

                if page < pages:
                    time.sleep(REQUEST_DELAY)

            except Exception as e:
                print(f"搜索失败: {e}")
                continue

        return all_articles

    def _parse_search_results(self, html: str) -> List[Dict[str, str]]:
        """解析搜索结果"""
        soup = BeautifulSoup(html, "lxml")
        articles = []

        items = soup.select("li.list_item")

        for item in items:
            try:
                title_elem = item.select_one("div.txt_info h3 a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                url = title_elem.get("href", "")

                author = ""
                author_elem = item.select_one("div.txt_info div.s_pup a")
                if author_elem:
                    author = author_elem.get_text(strip=True)

                date = ""
                date_elem = item.select_one("div.txt_info div.s_time")
                if date_elem:
                    date = date_elem.get_text(strip=True)

                abstract = ""
                abstract_elem = item.select_one("div.txt_info p.descrip")
                if abstract_elem:
                    abstract = abstract_elem.get_text(strip=True)

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
                print(f"解析失败: {e}")
                continue

        return articles

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """测试"""
    with SogouSearchSelenium() as searcher:
        articles = searcher.search_articles("人民日报", pages=1)

        print(f"\n找到 {len(articles)} 篇文章:")
        for i, a in enumerate(articles, 1):
            print(f"{i}. {a['title']} - {a['author']}")


if __name__ == "__main__":
    main()
