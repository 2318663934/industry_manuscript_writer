"""
配置文件
"""
import os

# 基础配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 搜狗搜索配置
SOGOU_SEARCH_URL = "https://weixin.sogou.com/weixin"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 请求配置
REQUEST_TIMEOUT = 15
REQUEST_DELAY = 3  # 请求间隔（秒），避免被封

# 搜索结果页数
MAX_PAGES = 5

# 保存格式
OUTPUT_FORMAT = "json"  # json 或 csv
