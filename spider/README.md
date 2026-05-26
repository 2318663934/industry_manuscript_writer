# 微信文章爬虫

通过搜狗搜索爬取微信公众文章的工具。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 方式一：搜索公众号文章（可能因反爬失效）

```bash
python main.py "公众号名称"
python main.py "人民日报" -p 3 -f
```

### 方式二：批量抓取已知链接（推荐）

将文章链接整理到 txt 文件，每行一个链接：

```
# links.txt 内容示例：
https://mp.weixin.qq.com/s/xxxxxxxxx1
https://mp.weixin.qq.com/s/xxxxxxxxx2
https://mp.weixin.qq.com/s/xxxxxxxxx3
```

然后运行：
```bash
python batch_spider.py links.txt
```

参数：
- `-d 5` 设置请求间隔（秒）
- `-o output_name` 自定义输出文件名

示例：
```bash
python batch_spider.py my_articles.txt -d 3
```

## 输出文件

文章会保存到 `data/` 目录下：
- JSON 格式：包含完整信息（标题、链接、作者、日期、摘要、正文等）
- 失败链接会保存到 `*_failed.txt` 文件

## 项目结构

```
wechat_spider/
├── config.py          # 配置文件
├── sougou_search.py   # 搜狗搜索模块
├── article_parser.py  # 文章解析模块
├── storage.py         # 数据存储模块
├── main.py            # 主程序入口
└── requirements.txt   # 依赖列表
```

## 注意事项

1. **请求间隔** - 默认3秒请求一次，避免被封
2. **Cookie限制** - 部分文章需要登录Cookie才能访问全文
3. **频率限制** - 建议每次搜索不超过5页
4. **合法使用** - 仅用于个人学习研究
