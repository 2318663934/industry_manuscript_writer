"""
数据存储模块
保存爬取的文章到本地
"""
import json
import csv
import os
from datetime import datetime
from typing import List, Dict
from config import DATA_DIR, OUTPUT_FORMAT


class ArticleStorage:
    """文章存储器"""

    def __init__(self, keyword: str):
        self.keyword = keyword
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"{keyword}_{self.timestamp}"

        if OUTPUT_FORMAT == "json":
            self.filepath = os.path.join(DATA_DIR, f"{self.filename}.json")
        else:
            self.filepath = os.path.join(DATA_DIR, f"{self.filename}.csv")

    def save(self, articles: List[Dict[str, str]]) -> str:
        """
        保存文章列表

        Args:
            articles: 文章列表

        Returns:
            保存的文件路径
        """
        if OUTPUT_FORMAT == "json":
            return self._save_json(articles)
        else:
            return self._save_csv(articles)

    def _save_json(self, articles: List[Dict[str, str]]) -> str:
        """保存为JSON格式"""
        data = {
            "keyword": self.keyword,
            "count": len(articles),
            "timestamp": self.timestamp,
            "articles": articles
        }

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return self.filepath

    def _save_csv(self, articles: List[Dict[str, str]]) -> str:
        """保存为CSV格式"""
        if not articles:
            return self.filepath

        fieldnames = ["title", "url", "author", "date", "abstract"]

        with open(self.filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for article in articles:
                row = {k: article.get(k, "") for k in fieldnames}
                writer.writerow(row)

        return self.filepath

    def append(self, article: Dict[str, str]) -> None:
        """追加单篇文章到文件"""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "keyword": self.keyword,
                "count": 0,
                "timestamp": self.timestamp,
                "articles": []
            }

        data["articles"].append(article)
        data["count"] = len(data["articles"])

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_articles(filepath: str) -> List[Dict[str, str]]:
    """从文件加载文章列表"""
    if filepath.endswith(".json"):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("articles", [])
    return []
