#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜狗微信搜索 - Selenium版作者文章爬虫
通过Selenium绕过反爬，自动跟随跳转，抓取并筛选文章
遇到验证页面时暂停，等待用户手动完成验证后继续

用法: python sougou_selenium_spider.py
"""

import re
import time
import random
import json
import os
import urllib.parse
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from storage import ArticleStorage

SEARCH_QUERY = "托马斯之颅"
AUTHOR_NAME = "托马斯之颅"
MAX_PAGES = 10

AUTHOR_PATTERNS = [
    re.compile(r"文\s*[\/／]\s*" + AUTHOR_NAME),
    re.compile(r"作者[：:]\s*" + AUTHOR_NAME),
    re.compile(r"撰文[：:]\s*" + AUTHOR_NAME),
    re.compile(r"原创[：:]\s*" + AUTHOR_NAME),
]

# 验证页面检测关键词
VERIFY_KEYWORDS = [
    "请输入验证码", "验证码", "点击验证", "滑动验证", "拼图验证",
    "人机验证", "安全验证", "请完成以下验证", "verify", "captcha",
    "antispider", "请点击", "拖动滑块", "请按住滑块",
]


def create_driver():
    """创建带反检测的Chrome driver"""
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # 不隐藏窗口，方便用户看到验证页面
    # options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en']});
            window.chrome = {runtime: {}};
        """
    })
    return driver


def is_verify_page(driver) -> bool:
    """检测当前页面是否为验证页面"""
    try:
        html = driver.page_source
        page_len = len(html)
        url = driver.current_url

        # 1. 页面太小（正常页面30KB+，反爬页约5KB）
        if page_len < 12000:
            return True

        # 2. URL中包含验证相关路径
        if any(kw in url.lower() for kw in ["verify", "captcha", "antispider", "unhuman"]):
            return True

        # 3. 搜索页但没有搜索结果（可能是被拦截后返回的空壳）
        if "weixin.sogou.com/weixin" in url and "query=" in url:
            soup = BeautifulSoup(html, "lxml")
            if not soup.select(".news-list li"):
                # 没有文章列表，检查是否有验证关键词
                body_text = soup.body.get_text() if soup.body else ""
                for kw in VERIFY_KEYWORDS:
                    if kw in body_text:
                        return True
                # 如果页面异常短，也可能是反爬
                if page_len < 8000:
                    return True

        # 4. 页面内容包含验证提示
        body_text_lower = html[:2000].lower()
        for kw in ["captcha", "antispider", "验证码", "人机验证", "安全验证"]:
            if kw in body_text_lower:
                return True

    except Exception:
        pass
    return False


def wait_for_verification(driver, context: str = ""):
    """检测到验证页面后，等待用户手动完成验证"""
    print("\n" + "!" * 60)
    print(f"!!! 检测到验证页面 !!!")
    if context:
        print(f"!!! 位置: {context}")
    print(f"!!! 当前URL: {driver.current_url[:100]}")
    print("!" * 60)
    print("\n请在浏览器窗口中手动完成验证（滑动/点击等）")
    print("验证通过后，回到此终端按 Enter 继续爬取...")
    print("(输入 'q' 并回车可以提前退出)\n")

    user_input = input().strip().lower()
    if user_input == "q":
        print("用户选择退出")
        return False

    print("继续爬取...")
    time.sleep(2)
    return True


def safe_navigate(driver, url: str, context: str = "", retry: int = 3) -> bool:
    """
    安全导航：导航到URL，如果遇到验证则等待用户处理
    返回 True 表示成功，False 表示用户选择退出
    """
    for attempt in range(retry):
        driver.get(url)
        time.sleep(random.uniform(2, 3))

        if is_verify_page(driver):
            if not wait_for_verification(driver, context):
                return False
            # 验证通过后重新导航
            driver.get(url)
            time.sleep(random.uniform(2, 3))

        # 再次检查是否还是验证页
        if not is_verify_page(driver):
            return True

        print(f"  验证后仍被拦截，重试 {attempt + 1}/{retry}...")
        time.sleep(3)

    print(f"  重试{retry}次后仍失败，跳过")
    return False


def check_author(text: str) -> bool:
    """检查文章是否由目标作者撰写"""
    for pattern in AUTHOR_PATTERNS:
        if pattern.search(text):
            return True
    head = text[:500]
    if f"文/{AUTHOR_NAME}" in head or f"作者：{AUTHOR_NAME}" in head:
        return True
    if f"文／{AUTHOR_NAME}" in head or f"作者: {AUTHOR_NAME}" in head:
        return True
    tail = text[-300:]
    if AUTHOR_NAME in tail and ("文/" in tail or "作者" in tail or "撰文" in tail):
        return True
    return False


def parse_article(html: str) -> dict:
    """从微信文章页面提取内容"""
    soup = BeautifulSoup(html, "lxml")
    content_elem = soup.select_one("div#js_content")
    if not content_elem:
        return {}

    content_html = str(content_elem)
    content_text = content_elem.get_text(separator="\n", strip=True)

    title = ""
    for sel in ["h1#activity-name", "h1.rich_media_title", "h1"]:
        elem = soup.select_one(sel)
        if elem:
            title = elem.get_text(strip=True)
            break

    account = ""
    js_name = soup.select_one("span#js_name")
    if js_name:
        account = js_name.get_text(strip=True)

    date = ""
    for sel in ["em#post-date", "span#publish_time"]:
        elem = soup.select_one(sel)
        if elem:
            date = elem.get_text(strip=True)
            break

    return {
        "title": title,
        "account": account,
        "date": date,
        "content_html": content_html,
        "content_text": content_text,
    }


def save_checkpoint(results: list, filename: str = "data/_sougou_checkpoint.json"):
    """保存检查点"""
    checkpoint = {
        "keyword": f"sougou_{AUTHOR_NAME}",
        "count": len(results),
        "articles": results,
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="搜狗微信Selenium爬虫")
    parser.add_argument("--resume", type=str, default="",
                        help="从检查点文件恢复爬取（如 data/_sougou_checkpoint.json）")
    parser.add_argument("--start-page", type=int, default=1,
                        help="起始搜索页码")
    args = parser.parse_args()

    print("=" * 60)
    print(f"搜狗微信作者爬虫 (Selenium + 验证检测)")
    print(f"搜索词: {SEARCH_QUERY} | 目标作者: {AUTHOR_NAME}")
    print("=" * 60)
    print("提示: 遇到验证页面时会暂停，请在浏览器中手动完成验证后")
    print("      回到此终端按 Enter 继续。输入 q 可提前退出。")
    print("=" * 60)

    driver = create_driver()
    results = []
    existing_titles = set()

    # 恢复检查点
    if args.resume and os.path.exists(args.resume):
        with open(args.resume, "r", encoding="utf-8") as f:
            cp = json.load(f)
        results = cp.get("articles", [])
        existing_titles = {a["title"].strip() for a in results}
        print(f"\n从检查点恢复: 已有 {len(results)} 篇文章")
        print(f"将从第 {args.start_page} 页继续\n")

    total_checked = 0
    total_skipped_author = 0
    total_failed = 0
    stopped_early = False

    try:
        encoded_query = urllib.parse.quote(SEARCH_QUERY)

        for page in range(args.start_page, MAX_PAGES + 1):
            search_url = f"https://weixin.sogou.com/weixin?query={encoded_query}&type=2&page={page}&ie=utf8"

            # 安全导航到搜索页
            if not safe_navigate(driver, search_url, f"搜索第{page}页"):
                stopped_early = True
                break

            time.sleep(random.uniform(1, 2))

            soup = BeautifulSoup(driver.page_source, "lxml")
            items = soup.select(".news-list li")

            if not items:
                # 有可能是验证拦截，再检查一次
                if is_verify_page(driver):
                    if not wait_for_verification(driver, f"搜索第{page}页(无结果)"):
                        stopped_early = True
                        break
                    # 重新导航
                    if not safe_navigate(driver, search_url, f"搜索第{page}页(重试)"):
                        stopped_early = True
                        break
                    time.sleep(2)
                    soup = BeautifulSoup(driver.page_source, "lxml")
                    items = soup.select(".news-list li")

                if not items:
                    print(f"第 {page} 页: 无结果，搜索结束")
                    break

            print(f"\n--- 第 {page} 页: {len(items)} 条 ---")

            for item in items:
                total_checked += 1
                h3 = item.select_one("h3 a")
                if not h3:
                    total_failed += 1
                    continue

                title_snippet = h3.get_text(strip=True)
                redirect_href = h3.get("href", "")
                if not redirect_href.startswith("http"):
                    redirect_href = "https://weixin.sogou.com" + redirect_href

                # 跟随跳转（带验证检测）
                if not safe_navigate(driver, redirect_href, f"跳转: {title_snippet[:30]}"):
                    stopped_early = True
                    break

                time.sleep(random.uniform(1, 2))

                # 检查是否到达微信文章页
                if "mp.weixin.qq.com" not in driver.current_url:
                    # 可能还在跳转中，检查是否是验证页
                    if is_verify_page(driver):
                        if not wait_for_verification(driver, f"跳转后: {title_snippet[:30]}"):
                            stopped_early = True
                            break
                        # 重新跳转
                        if not safe_navigate(driver, redirect_href, f"重新跳转: {title_snippet[:30]}"):
                            stopped_early = True
                            break
                        time.sleep(2)

                    if "mp.weixin.qq.com" not in driver.current_url:
                        total_failed += 1
                        continue

                # 解析文章
                article = parse_article(driver.page_source)
                if not article or not article.get("content_text"):
                    total_failed += 1
                    continue

                # 跳过已有文章
                art_title = (article["title"] or title_snippet).strip()
                if art_title in existing_titles:
                    continue

                # 筛选作者
                if not check_author(article["content_text"]):
                    total_skipped_author += 1
                    continue

                existing_titles.add(art_title)

                result = {
                    "title": article["title"] or title_snippet,
                    "author": AUTHOR_NAME,
                    "account": article.get("account", ""),
                    "date": article.get("date", ""),
                    "url": driver.current_url,
                    "content_html": article["content_html"],
                    "content_text": article["content_text"],
                    "cover_image": "",
                }
                results.append(result)

                word_count = len(article["content_text"])
                print(f"  [{len(results)}] {word_count}字")

                # 每5条保存检查点
                if len(results) % 5 == 0:
                    save_checkpoint(results)

            if stopped_early:
                break

    finally:
        # 最终保存
        if results:
            save_checkpoint(results, f"data/_sougou_final_checkpoint_{len(results)}.json")
        driver.quit()

    # 统计
    print("\n" + "=" * 60)
    if stopped_early:
        print("爬取中断（用户操作或验证未通过）")
    else:
        print("爬取完成!")
    print(f"  检查总数: {total_checked}")
    print(f"  确认作者: {len(results)}")
    print(f"  非目标作者: {total_skipped_author}")
    print(f"  失败/跳转: {total_failed}")

    if results:
        total_chars = sum(len(r["content_text"]) for r in results)
        print(f"  总字数: {total_chars:,}, 平均: {total_chars // len(results):,} 字/篇")
        print("=" * 60)

        storage = ArticleStorage(f"sougou_{AUTHOR_NAME}")
        filepath = storage.save(results)
        print(f"\n结果已保存到: {filepath}")
    else:
        print("未找到匹配的文章")


if __name__ == "__main__":
    main()
