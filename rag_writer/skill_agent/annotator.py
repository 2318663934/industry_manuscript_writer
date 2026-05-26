#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM辅助策略标注模块

使用大语言模型对文章进行策略标注，提取写作方法论特征。
标注结果用于构建策略案例库，支持后续的策略检索和Few-shot学习。
"""

import json
import re
import time
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

from ..llm_client import BaseLLMClient, create_llm_client
from .models import StrategyCase, ArticleAnnotation, SectionAnnotation
from .config import get_skill_config


# 默认标注提示词
DEFAULT_ANNOTATION_PROMPT = """你是一位资深行业编辑。请分析以下文章，提取其写作策略特征。

文章标题：{title}
文章内容：
{content}

请仔细分析这篇文章的：
1. 开篇方式及效果
2. 整体结构模式和章节安排
3. 各章节的写作手法
4. 收尾方式及效果
5. 风格特征和亮点手法

请以JSON格式输出策略标注（确保输出有效的JSON）：
{{
    "opening_approach": "开篇方式（故事切入/数据震撼/问题引发/对比反差/引用名言/场景描写/新闻切入）",
    "opening_effectiveness": 开篇效果评分(1-5),
    "opening_analysis": "开篇效果分析简述",
    "structural_pattern": "结构模式（递进式/并列式/对比式/时间线式/问题-方案式）",
    "section_strategies": [
        {{
            "section_title": "章节标题（推测）",
            "position": 1,
            "structural_approach": "本节结构手法",
            "content_focus": "本节核心内容",
            "style_guidance": "风格指导建议",
            "transition_to_next": "如何过渡到下一节（若无则填'无'）",
            "notable_techniques": ["亮点手法1", "亮点手法2"]
        }}
    ],
    "closing_approach": "收尾方式（升华展望/问题回扣/行动呼吁/总结要点/留白思考）",
    "closing_effectiveness": 收尾效果评分(1-5),
    "closing_analysis": "收尾效果分析简述",
    "style_features": ["风格特征1", "风格特征2"],
    "notable_techniques": ["全文亮点手法1", "全文亮点手法2"],
    "core_tension": "文章核心张力/矛盾（用一句话描述）",
    "target_audience": "推测的目标受众"
}}

注意：
- opening_effectiveness和closing_effectiveness是1-5的数字评分
- 如果文章章节不明显，section_strategies可以为空数组但不要省略
- notable_techniques尽量具体，如"开篇数据冲击"、"矩阵对比"、"升维收尾"等
"""


class StrategyAnnotator:
    """
    使用LLM对文章进行策略标注

    标注流程：
    1. 接收文章标题和内容
    2. 构建标注提示词
    3. 调用LLM生成标注
    4. 解析JSON结果并验证
    5. 返回ArticleAnnotation对象
    """

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        prompt_template: str = DEFAULT_ANNOTATION_PROMPT,
        temperature: float = 0.3,
        max_retries: int = 3,
    ):
        """
        初始化标注器

        Args:
            llm_client: LLM客户端（若为None则使用默认配置创建）
            prompt_template: 标注提示词模板
            temperature: 生成温度
            max_retries: 最大重试次数
        """
        self.llm_client = llm_client
        self.prompt_template = prompt_template
        self.temperature = temperature
        self.max_retries = max_retries

    def _get_llm_client(self) -> BaseLLMClient:
        """获取LLM客户端"""
        if self.llm_client is None:
            self.llm_client = create_llm_client()
        return self.llm_client

    def annotate(
        self,
        title: str,
        content: str,
        max_chars: Optional[int] = None,
    ) -> ArticleAnnotation:
        """
        标注单篇文章

        Args:
            title: 文章标题
            content: 文章内容
            max_chars: 最大字符数（超过则截断）

        Returns:
            ArticleAnnotation: 策略标注对象

        Raises:
            ValueError: 标注失败或解析失败
        """
        config = get_skill_config()
        if max_chars is None:
            max_chars = config.annotation_max_chars

        # 截断内容
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[内容已截断...]"

        # 构建提示词
        prompt = self.prompt_template.format(
            title=title,
            content=content,
        )

        # 调用LLM生成
        llm = self._get_llm_client()
        retry_count = 0

        while retry_count < self.max_retries:
            try:
                if hasattr(llm, 'generate_with_system'):
                    response = llm.generate_with_system(
                        system_prompt="你是一个专业的行业文章策略分析师，擅长提取文章的结构和写作手法。",
                        user_prompt=prompt,
                        temperature=self.temperature,
                    )
                else:
                    response = llm.generate(
                        prompt,
                        temperature=self.temperature,
                    )

                # 解析JSON
                annotation_dict = self._parse_json(response.content)
                return ArticleAnnotation(**annotation_dict)

            except (json.JSONDecodeError, ValueError) as e:
                retry_count += 1
                print(f"标注解析失败（尝试 {retry_count}/{self.max_retries}）: {e}")
                if retry_count >= self.max_retries:
                    raise ValueError(f"标注失败，已达最大重试次数: {e}")
                time.sleep(1)  # 重试前等待

        raise ValueError("标注失败")

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        从LLM输出中解析JSON

        尝试多种策略：
        1. 直接解析整个文本
        2. 提取```json ... ```块
        3. 提取{ ... }块
        """
        text = text.strip()

        # 策略1：直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 策略2：提取json代码块
        json_block_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # 策略3：提取第一个{到}之间的内容
        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError(f"无法解析JSON: {text[:200]}...", text, 0)

    def annotate_case(
        self,
        title: str,
        content: str,
        article_url: str = "",
        content_type: str = "行业分析",
        tags: Optional[List[str]] = None,
    ) -> StrategyCase:
        """
        标注并创建策略案例

        Args:
            title: 文章标题
            content: 文章内容
            article_url: 文章URL
            content_type: 内容类型
            tags: 标签列表

        Returns:
            StrategyCase: 策略案例对象
        """
        annotation = self.annotate(title, content)

        # 计算质量评分（开篇和收尾的平均）
        quality_score = (
            annotation.opening_effectiveness + annotation.closing_effectiveness
        ) / 2

        # 生成案例ID
        import hashlib
        case_id = f"case_{hashlib.md5(title.encode()).hexdigest()[:8]}"

        return StrategyCase(
            case_id=case_id,
            title=title,
            article_url=article_url,
            content_type=content_type,
            target_audience=annotation.target_audience or "",
            annotation=annotation,
            quality_score=quality_score,
            tags=tags or [],
        )


def extract_tags(title: str, content: str, max_tags: int = 5) -> List[str]:
    """
    从标题和内容中提取标签

    Args:
        title: 文章标题
        content: 文章内容
        max_tags: 最大标签数量

    Returns:
        标签列表
    """
    # 常见行业标签模式
    industry_patterns = [
        "AI", "人工智能", "大模型", "LLM", "ChatGPT",
        "自动驾驶", "新能源", "电动汽车", "锂电池",
        "半导体", "芯片", "集成电路",
        "云计算", "SaaS", "PaaS",
        "元宇宙", "Web3", "区块链",
        "智能家居", "物联网", "IOT",
        "生物医药", "医疗", "基因",
        "新材料", "碳中和", "环保",
    ]

    tags = []
    text = title + " " + content[:2000]  # 只检查前2000字

    for pattern in industry_patterns:
        if pattern.lower() in text.lower():
            tags.append(pattern)

    # 如果标签不足，尝试从标题中提取关键词
    if len(tags) < 3:
        # 简单的中文分词（基于字符）
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', title)
        for word in words:
            if word not in tags and len(tags) < max_tags:
                tags.append(word)

    return tags[:max_tags]


def batch_annotate(
    articles: List[Dict[str, str]],
    output_path: str,
    llm_client: Optional[BaseLLMClient] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    save_interval: int = 10,
) -> List[StrategyCase]:
    """
    批量标注文章

    Args:
        articles: 文章列表 [{"title": "", "content": "", "url": "", "content_type": ""}]
        output_path: 输出文件路径（JSON格式）
        llm_client: LLM客户端
        progress_callback: 进度回调函数 (current, total)
        save_interval: 每多少篇保存一次中间结果

    Returns:
        策略案例列表
    """
    annotator = StrategyAnnotator(llm_client=llm_client)
    results = []
    output_path = Path(output_path)

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for i, article in enumerate(articles):
        title = article.get("title", "未命名")
        content = article.get("content", "")
        url = article.get("url", "")
        content_type = article.get("content_type", "行业分析")

        print(f"正在标注 {i + 1}/{len(articles)}: {title[:30]}...")

        try:
            case = annotator.annotate_case(
                title=title,
                content=content,
                article_url=url,
                content_type=content_type,
            )
            results.append(case)

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, len(articles))

        except Exception as e:
            print(f"标注失败 {title}: {e}")
            # 创建占位案例（标记为未标注成功）
            # 使用最小有效值1.0以满足Pydantic验证
            from datetime import datetime
            results.append(StrategyCase(
                case_id=f"case_failed_{i + 1:03d}",
                title=title,
                article_url=url,
                content_type=content_type,
                annotation=ArticleAnnotation(
                    opening_approach="标注失败",
                    opening_effectiveness=1.0,
                    structural_pattern="未知",
                    closing_approach="标注失败",
                    closing_effectiveness=1.0,
                ),
                quality_score=1.0,  # 使用最小有效值
                tags=extract_tags(title, content),
            ))

        # 定期保存中间结果
        if (i + 1) % save_interval == 0:
            _save_cases(results, output_path)
            print(f"已保存中间结果 ({i + 1}篇)")

    # 最终保存
    _save_cases(results, output_path)
    print(f"批量标注完成，共{len(results)}篇")

    return results


def _save_cases(cases: List[StrategyCase], path: Path):
    """保存案例到JSON文件"""
    data = [case.to_dict() for case in cases]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 测试标注器
    print("测试StrategyAnnotator...")

    test_content = """
    说起远程办公，很多人第一反应是："这不就是在家躺着干活吗？"

    还真不是。

    去年，我们公司全面推行混合办公模式。起初我也担心：员工会不会摸鱼？协作会不会变差？效率会不会下降？

    结果呢？三个月下来，数据让我意外——效率不降反升，请假率还降了两成。

    这背后其实有个逻辑：远程办公倒逼了管理的精细化。当你能看到的只有结果时，就必须学会目标管理、信任授权。

    当然，挑战也不少。沟通成本上升、新人培训难度加大、团队凝聚力难以维持……这些都是实实在在的问题。

    所以，远程办公从来不是一道是非题，而是道选择题。选什么？怎么选？取决于你的团队基因和业务特性。

    关键在于：不要把远程办公当成疫情的临时措施，而要当成一次管理升级的机会。
    """

    annotator = StrategyAnnotator()

    # 注意：实际调用需要有效的LLM客户端
    # annotation = annotator.annotate("远程办公对企业管理的影响", test_content)
    # print(annotation.model_dump_json(indent=2))

    print("测试代码已准备，需要有效的LLM客户端才能运行")
