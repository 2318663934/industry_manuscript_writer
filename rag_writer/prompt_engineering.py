#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提示词工程模块 - 构建高质量提示词
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .config import settings
from .style_injector import get_style_injection


@dataclass
class WritingTask:
    """写作任务"""
    topic: str  # 话题/主题
    requirements: str  # 具体要求
    keywords: List[str]  # 关键词
    style: Optional[str] = None  # 写作风格要求
    length: Optional[str] = None  # 字数要求
    # B端深度稿件特有字段
    target_audience: Optional[str] = None  # 目标受众：企业高管/行业投资者/技术同行
    perspective: Optional[str] = None  # 站位：厂家同行/产业链合作伙伴/资深行业观察者
    min_dimensions: int = 5  # 最少发散维度数


@dataclass
class KnowledgeContext:
    """知识上下文"""
    title: str
    url: str
    author: str
    date: str
    content: str  # 原文内容
    source_type: str = "database"  # 来源类型: "database" 或 "supplementary"


class PromptBuilder:
    """提示词构建器"""

    def __init__(self):
        self.prompt_config = settings.prompt

    def build_knowledge_context(
        self,
        knowledge_items: List[KnowledgeContext],
        max_chars: Optional[int] = None,
    ) -> str:
        """
        构建知识上下文

        Args:
            knowledge_items: 知识条目列表
            max_chars: 最大字符数

        Returns:
            格式化的知识上下文
        """
        if max_chars is None:
            max_chars = self.prompt_config.max_knowledge_chars

        # 分离数据库知识和补充资料
        db_items = [k for k in knowledge_items if k.source_type != "supplementary"]
        supp_items = [k for k in knowledge_items if k.source_type == "supplementary"]

        context_parts = []
        total_chars = 0

        # 添加数据库检索的知识
        if db_items:
            context_parts.append("## 数据库检索资料\n")
            total_chars += len(context_parts[-1])

            for i, item in enumerate(db_items, 1):
                part = f"""【参考资料 {i}】
标题: {item.title}
来源: {item.author} | {item.date}
内容:
{item.content}
"""
                part_chars = len(part)
                if total_chars + part_chars > max_chars:
                    remaining = max_chars - total_chars
                    if remaining > 200:
                        part = f"""【参考资料 {i}】
标题: {item.title}
来源: {item.author} | {item.date}
内容:
{item.content[:remaining - 50]}...(内容截断)
"""
                        context_parts.append(part)
                    break

                context_parts.append(part)
                total_chars += part_chars

        # 添加补充资料
        if supp_items:
            if context_parts:
                context_parts.append("")  # 空行分隔
                total_chars += 1

            context_parts.append("## 用户补充资料\n")
            total_chars += len(context_parts[-1])

            for i, item in enumerate(supp_items, 1):
                # 补充资料使用不同前缀，并在标题中标注来源
                source_label = f"（来源: {item.title}）"
                if item.url:
                    source_label = f"（来源: {item.title} | {item.url}）"

                part = f"""【补充资料 {i}】
标题: {item.title}
来源: {source_label}
内容:
{item.content}
"""
                part_chars = len(part)
                if total_chars + part_chars > max_chars:
                    remaining = max_chars - total_chars
                    if remaining > 200:
                        part = f"""【补充资料 {i}】
标题: {item.title}
来源: {source_label}
内容:
{item.content[:remaining - 50]}...(内容截断)
"""
                        context_parts.append(part)
                    break

                context_parts.append(part)
                total_chars += part_chars

        if not context_parts:
            return ""

        return "\n".join(context_parts)

        return "\n".join(context_parts)

    def build_system_prompt(self) -> str:
        """构建系统提示词"""
        prompt = """你是一位资深的行业内容创作者，擅长撰写专业、有深度且读起来自然的行业分析文章。

你的写作风格:
- 专业但不晦涩，用通俗易懂的语言解释专业概念
- 有自己独立的观点和见解，不做简单的信息堆砌
- 善于使用具体案例、数据和故事来支撑观点
- 文章结构清晰，逻辑连贯，段落之间过渡自然
- 语言有节奏感，长短句结合，读起来不枯燥

写作原则:
1. 避免AI常见的空洞套话（如"随着时代发展"、"众所周知"、"毋庸置疑"等）
2. 避免每句话都以"我们"开头
3. 避免重复使用相同的句式结构
4. 主动句为主，减少被动语态
5. 可以适当使用口语化表达和过渡词（如"话说回来"、"更重要的是"、"说起来"）
6. 避免文章开头就讲大道理，从具体案例或场景切入"""

        prompt += get_style_injection()
        return prompt

    def build_user_prompt(
        self,
        task: WritingTask,
        knowledge_context: str,
    ) -> str:
        """
        构建用户提示词

        Args:
            task: 写作任务
            knowledge_context: 知识上下文

        Returns:
            完整的用户提示词
        """
        prompt = f"""## 写作任务

**话题/主题:** {task.topic}

**具体要求:**
{task.requirements}
"""

        if task.keywords:
            prompt += f"\n**关键词:** {', '.join(task.keywords)}"

        if task.style:
            prompt += f"\n**写作风格:** {task.style}"

        if task.length:
            prompt += f"\n**字数要求:** {task.length}"

        if knowledge_context:
            prompt += f"""

## 参考资料

以下是相关的参考资料，请结合这些内容进行写作。注意：不要直接复制原文，要用自己的话重新组织和表达。

{knowledge_context}

## 写作要求

请根据以上任务和参考资料，撰写一篇专业的行业文章。

具体要求:
{self.prompt_config.style_requirements}

请直接输出文章内容，不需要写"以下是文章"之类的引导语。"""

        return prompt

    def build_prompt(
        self,
        task: WritingTask,
        knowledge_items: List[KnowledgeContext],
    ) -> Dict[str, str]:
        """
        构建完整的提示词

        Args:
            task: 写作任务
            knowledge_items: 知识条目列表

        Returns:
            包含system和user键的字典
        """
        # 构建知识上下文
        knowledge_context = self.build_knowledge_context(knowledge_items)

        return {
            "system": self.build_system_prompt(),
            "user": self.build_user_prompt(task, knowledge_context),
        }

    def build_revision_prompt(
        self,
        original_article: str,
        revision_requirements: str,
    ) -> Dict[str, str]:
        """
        构建修改提示词

        Args:
            original_article: 原文
            revision_requirements: 修改要求

        Returns:
            包含system和user键的字典
        """
        system = """你是一位资深编辑，擅长优化和修改文章，使文章更加流畅、专业、有可读性。

你的编辑风格:
- 在保持原文核心观点的基础上，让文章更加流畅自然
- 消除AI写作的痕迹，让文章读起来像人写的
- 适当调整句子结构，增加句式多样性
- 精简冗余表达，让文章更紧凑
- 强化有说服力的部分，弱化空洞的内容"""

        user = f"""## 原文

{original_article}

## 修改要求

{revision_requirements}

请直接输出修改后的文章，不需要说明修改了什么。"""

        return {"system": system, "user": user}


class FewShotPromptBuilder(PromptBuilder):
    """Few-shot提示词构建器"""

    def __init__(self):
        super().__init__()
        self.examples = self._load_examples()

    def _load_examples(self) -> List[Dict[str, str]]:
        """加载示例文章"""
        # 这里可以加载真实的优秀文章作为示例
        # 实际应用中可以从文件或数据库加载
        return [
            {
                "task": "以'远程办公对企业管理的影响'为话题写一篇行业分析",
                "output": """说起远程办公，很多人第一反应是："这不就是在家躺着干活吗？"

还真不是。

去年，我们公司全面推行混合办公模式。起初我也担心：员工会不会摸鱼？协作会不会变差？效率会不会下降？

结果呢？三个月下来，数据让我意外——效率不降反升，请假率还降了两成。

这背后其实有个逻辑：远程办公倒逼了管理的精细化。当你能看到的只有结果时，就必须学会目标管理、信任授权。

当然，挑战也不少。沟通成本上升、新人培训难度加大、团队凝聚力难以维持……这些都是实实在在的问题。

所以，远程办公从来不是一道是非题，而是道选择题。选什么？怎么选？取决于你的团队基因和业务特性。

关键在于：不要把远程办公当成疫情的临时措施，而要当成一次管理升级的机会。"""
            }
        ]

    def build_few_shot_prompt(
        self,
        task: WritingTask,
        knowledge_items: List[KnowledgeContext],
    ) -> Dict[str, str]:
        """构建Few-shot提示词"""
        system = self.build_system_prompt()

        # 构建Few-shot示例
        examples_text = "\n\n".join([
            f"示例 {i+1}:\n任务: {ex['task']}\n\n文章:\n{ex['output']}"
            for i, ex in enumerate(self.examples)
        ])

        knowledge_context = self.build_knowledge_context(knowledge_items)

        user = f"""## 示例

{examples_text}

---

## 新任务

**话题/主题:** {task.topic}

**具体要求:**
{task.requirements}
"""

        if task.keywords:
            user += f"\n**关键词:** {', '.join(task.keywords)}"

        if knowledge_context:
            user += f"""

## 参考资料

{knowledge_context}

## 写作要求

请参考示例的写作风格，结合参考资料，撰写文章。

{self.prompt_config.style_requirements}

请直接输出文章内容。"""

        return {"system": system, "user": user}


def create_prompt_builder(use_few_shot: bool = False, deep_brief: bool = False) -> PromptBuilder:
    """创建提示词构建器"""
    if deep_brief:
        return DeepBriefPromptBuilder()
    if use_few_shot:
        return FewShotPromptBuilder()
    return PromptBuilder()


class DeepBriefPromptBuilder(PromptBuilder):
    """
    B端深度稿件策划专家提示词构建器

    特点：
    - 纵向透视（技术深度）和横向扩张（产业广度）
    - 5-7个维度的硬核发散分析
    - 严禁虚无缥缈，必须有"骨头"
    - 产出可直接给作者的完整深度Brief
    """

    # 五个核心分析维度
    DIMENSIONS = [
        {
            "name": "研发解密视角",
            "description": "剖析实现过程中的'魔鬼细节'",
            "focus": "功耗、散热、算法剪枝、数据互通的具体难点",
            "audience": "技术同行、研发团队",
        },
        {
            "name": "商业范式视角",
            "description": "探讨商业模式的'变轨'",
            "focus": "从卖数值到卖审美、从买断制到GaaS化订阅",
            "audience": "企业高管、投资者、战略规划者",
        },
        {
            "name": "用户认知视角",
            "description": "分析'操作直觉'或'资产平移'",
            "focus": "10年肌肉记忆的无缝迁移、用户心智占领",
            "audience": "产品经理、用户体验设计师",
        },
        {
            "name": "产业生态视角",
            "description": "探讨该产品如何牵动上下游技术链条的整体水位上升",
            "focus": "供应链、技术栈、合作生态、竞争对手反应",
            "audience": "产业链合作伙伴、投资者",
        },
        {
            "name": "社会伦理视角",
            "description": "讨论技术如何应对人类本质需求",
            "focus": "陪伴感、隐私主权、认知卸载",
            "audience": "政策制定者、行业观察者、社会学家",
        },
    ]

    def build_system_prompt(self) -> str:
        """构建B端深度稿件专家系统提示词"""
        prompt = """【角色定义】
你是一名拥有15年行业深耕经验的顶级公关战略专家与商业分析师。

【服务对象】
你的服务对象是企业高管、行业投资者及技术同行。

【核心使命】
你的任务是跳出"消费者说明书"的表层逻辑，通过产品的发布或表现，剖析背后的：
- 行业变革趋势
- 研发卡点与难点
- 商业竞争规则重写
- 社会学变迁

【严禁事项】
你拒绝做"图书管理员"，严禁简单堆砌资料。

【思考逻辑 - 两套核心路径】

●纵向透视（Vertical Deep Dive）：
穿透表象，扎向技术/逻辑的最深处。
关注：研发难点（坑在哪里）、技术卡点（为什么别人做不到）、应用上限（物理或算力的天花板）、底层认知（操作习惯的复用）。

●横向扩张（Horizontal Expansion）：
跨界联想，连接社会与产业。
关注：产业协同（牵动了谁的利益/技术突破）、流量重构（解构了谁的入口）、社会契约（定义了什么新社交/消费规则）。

【发散维度 - 5个强制分析视角】

1.研发解密视角：
剖析实现过程中的"魔鬼细节"（如：功耗、散热、算法剪枝、数据互通的具体难点）。
谁会关心：技术同行、研发团队

2.商业范式视角：
探讨商业模式的"变轨"（如：从卖数值到卖审美、从买断制到GaaS化订阅）。
谁会关心：企业高管、投资者、战略规划者

3.用户认知视角：
分析"操作直觉"或"资产平移"（如：10年肌肉记忆的无缝迁移）。
谁会关心：产品经理、用户体验设计师

4.产业生态视角：
探讨该产品如何牵动上下游技术链条的整体水位上升。
谁会关心：产业链合作伙伴、投资者

5.社会伦理视角：
讨论技术如何应对人类本质需求（如：陪伴感、隐私主权、认知卸载）。
谁会关心：政策制定者、行业观察者、社会学家

【输出标准 - 三条铁律】

1.严禁虚无缥缈：
拒绝"感官进化"、"时代礼赞"、"技术革命"等虚词。

2.必须有"骨头"：
必须包含具体的技术场景、研发难点或行业对比数据。

3.站位要清晰：
明确你是站在"厂家同行"、"产业链合作伙伴"还是"资深行业观察者"的角度说话。"""

        prompt += get_style_injection()
        return prompt

    def build_deep_brief_prompt(
        self,
        task: WritingTask,
        knowledge_items: List[KnowledgeContext],
    ) -> Dict[str, str]:
        """
        构建深度Brief提示词

        Args:
            task: 写作任务
            knowledge_items: 知识条目列表

        Returns:
            包含system和user键的字典
        """
        knowledge_context = self.build_knowledge_context(knowledge_items)

        # 构建目标受众和站位说明
        audience_desc = ""
        if task.target_audience:
            audience_desc = f"\n**目标受众:** {task.target_audience}"
        if task.perspective:
            audience_desc += f"\n**内容站位:** {task.perspective}"

        # 构建维度要求
        dimensions_text = "\n".join([
            f"{i+1}. **{d['name']}**：{d['description']}\n   关注点：{d['focus']}\n   谁会关心：{d['audience']}"
            for i, d in enumerate(self.DIMENSIONS[:task.min_dimensions])
        ])

        user_prompt = f"""## 一、需求解析

**话题/主题:** {task.topic}

**具体需求:**
{task.requirements}
{audience_desc}

**关键词:** {', '.join(task.keywords) if task.keywords else '无'}

**字数要求:** {task.length or '根据内容深度自行把握'}"""

        if knowledge_context:
            user_prompt += f"""

## 二、参考资料

以下是经过检索和筛选的相关资料。请分析这些资料，找出：
- 哪些技术细节值得关注深挖
- 哪些数据可以作为"骨头"
- 哪些观点需要交叉验证

{knowledge_context}
"""
        else:
            user_prompt += "\n\n（无参考资料，请基于你的行业知识储备进行分析）"

        user_prompt += f"""

## 三、深度发散分析

请从以下 **{task.min_dimensions}** 个维度进行硬核发散，每个维度必须给出：
- 核心洞察（这个维度最关键的是什么）
- 具体论据（技术细节、数据、案例）
- 上限与边界（能做到什么程度、做不到什么）
- 谁会真正关心这个点

### 发散维度：

{dimensions_text}

## 四、对标分析

针对上述每个维度，明确回答：
1. **谁会关心这个点？**（具体到人群）
2. **解决了什么真实痛点？**（不是表面需求）
3. **上限在哪里？**（天花板分析）

## 五、结构化Brief输出

请生成一份可以直接给到作者/编辑的完整深度Brief，格式如下：

---
**【Brief标题】**：{task.topic}

**【核心张力/矛盾】**：这篇稿件要抓住哪对核心矛盾？

**【内容站位】**：厂家同行视角 / 产业链合作伙伴视角 / 资深行业观察者视角

**【不建议写的方向】**：哪些老生常谈的话题要避免？

---
**【角度一：XXX】**
- 核心观点：...
- 必备"骨头"：...（具体技术细节/数据）
- 段落结构建议：...
- 字数建议：约XXX字

**【角度二：XXX】**
- ...（同上格式）

**【角度N：XXX】**
- ...

---
**【文章骨架建议】**：
1. 开头切入点（不要从大道理讲起，建议从一个具体场景/数据/矛盾切入）
2. 中间论述逻辑（如何层层递进）
3. 结尾升华点（不要喊口号，要给出有价值的展望或警示）

**【必须避免的AI味表达】**：
- 禁用开头："随着..."、"近年来..."、"众所周知..."
- 禁用套话："技术革命"、"行业突破"、"重磅发布"
- 禁用说教："我们应该..."、"企业必须..."

---

请开始生成深度Brief。"""

        return {
            "system": self.build_system_prompt(),
            "user": user_prompt,
        }

    def build_prompt(
        self,
        task: WritingTask,
        knowledge_items: List[KnowledgeContext],
    ) -> Dict[str, str]:
        """构建完整提示词（兼容接口）"""
        return self.build_deep_brief_prompt(task, knowledge_items)


class DeepArticlePromptBuilder(DeepBriefPromptBuilder):
    """
    深度文章写作提示词构建器

    在DeepBrief基础上，直接生成完整文章而非Brief
    """

    def build_article_prompt(
        self,
        task: WritingTask,
        knowledge_items: List[KnowledgeContext],
    ) -> Dict[str, str]:
        """构建深度文章提示词"""
        knowledge_context = self.build_knowledge_context(knowledge_items)

        # 构建维度要求
        dimensions_text = "\n".join([
            f"{i+1}. **{d['name']}**：{d['description']} - 关注：{d['focus']}"
            for i, d in enumerate(self.DIMENSIONS[:task.min_dimensions])
        ])

        audience_note = ""
        if task.target_audience:
            audience_note += f"\n目标读者：{task.target_audience}"
        if task.perspective:
            audience_note += f"\n内容站位：{task.perspective}"

        user_prompt = f"""## 写作任务

**话题:** {task.topic}

**需求:**
{task.requirements}
{audience_note}

**关键词:** {', '.join(task.keywords) if task.keywords else '无'}
**字数:** {task.length or '2000-3000字'}"""

        if knowledge_context:
            user_prompt += f"""

## 参考资料

{knowledge_context}

**使用要求：**
- 不要直接复制原文，要用自己的话重新组织和表达
- 引用数据时注明来源和背景
- 将技术术语翻译成目标读者能理解的语言"""

        user_prompt += f"""

## 分析维度要求

请确保文章涵盖以下 **{task.min_dimensions}** 个分析维度：

{dimensions_text}

## 写作标准

【铁律 - 必须遵守】
1. **严禁虚无缥缈**：拒绝"感官进化"、"时代礼赞"等虚词
2. **必须有"骨头"**：包含具体技术场景、研发难点、行业对比数据
3. **站位清晰**：明确站在哪个角度说话

【语言风格】
- 专业但不晦涩，像跟同行聊天那样自然
- 长短句结合，有节奏感
- 主动句为主，减少被动语态
- 可以用"说起来"、"话说回来"这样的过渡词
- 禁止每句话都以"我们"或"你"开头

【结构要求】
- 开头：不要从大道理讲起，从一个具体场景/数据/矛盾切入
- 中间：逻辑递进，每个维度要有实质性分析
- 结尾：给出有价值的展望或警示，不要喊口号

【禁止的AI套话】
- 开头禁用："随着..."、"近年来..."、"在这个时代..."
- 套话禁用："技术革命"、"行业突破"、"重磅发布"、"众所周知"
- 说教禁用："我们应该..."、"企业必须..."、"必须指出的是..."

## 输出

请直接输出完整文章，不要加"以下是文章"之类的引导语。"""

        return {
            "system": self.build_system_prompt(),
            "user": user_prompt,
        }


@dataclass
class OutlineSection:
    """大纲章节"""
    title: str  # 章节标题
    description: str  # 章节说明/核心内容概述
    citations: List[Dict[str, str]]  # 引用卡片 [{"title": "...", "author": "...", "date": "...", "source_quote": "..."}]
    word_count_estimate: int  # 字数估算


class OutlinePromptBuilder(PromptBuilder):
    """
    文章大纲生成提示词构建器

    生成符合行业标准的文章大纲，每节附引用卡片
    """

    def build_system_prompt(self) -> str:
        """构建大纲生成专家系统提示词"""
        return """【角色定义】
你是一位资深的行业策划编辑，擅长根据检索到的资料和用户需求，设计专业、有深度且结构清晰的文章大纲。

【核心理念】
1. 追求"立意新颖"：不满足于泛泛而谈，要挖掘独特的切入角度和新颖的核心观点
2. 深度与广度并重：纵向要有技术/逻辑深度，横向要有关联产业/社会视野
3. 以用户补充资料为核心：用户提供的补充资料代表其核心意图，必须重点参考
4. 超越数据库信息：不应仅复述数据库检索到的内容，而要在此基础上创新

【严禁事项】
1. 严禁生成空洞无物的章节标题（如"行业概述"、"发展趋势"）
2. 严禁章节之间逻辑混乱，缺乏递进关系
3. 严禁引用来源模糊或不准确
4. 严禁简单复述已有信息，要有独到见解

【输出标准】
1. 章节标题要具体、明确，能反映该节核心内容
2. 每节必须标注基于哪些参考资料
3. 字数分配要合理，体现内容重要性差异
4. 核心观点要有新意，不人云亦云"""

    def build_outline_prompt(
        self,
        task: WritingTask,
        knowledge_items: List[KnowledgeContext],
    ) -> Dict[str, str]:
        """
        构建大纲生成提示词

        Args:
            task: 写作任务
            knowledge_items: 知识条目列表

        Returns:
            包含system和user键的字典
        """
        knowledge_context = self.build_knowledge_context(knowledge_items)

        # 构建目标受众和站位说明
        audience_desc = ""
        if task.target_audience:
            audience_desc = f"\n**目标受众:** {task.target_audience}"
        if task.perspective:
            audience_desc += f"\n**内容站位:** {task.perspective}"

        user_prompt = f"""## 写作任务

**话题/主题:** {task.topic}

**具体需求:**
{task.requirements}
{audience_desc}

**关键词:** {', '.join(task.keywords) if task.keywords else '无'}
**字数要求:** {task.length or '根据内容深度自行把握'}"""

        # 分离数据库知识和补充资料用于分别展示
        db_items = [k for k in knowledge_items if k.source_type != "supplementary"]
        supp_items = [k for k in knowledge_items if k.source_type == "supplementary"]

        if db_items or supp_items:
            user_prompt += """

## 参考资料

"""
            # 首先强调用户补充资料的重要性
            if supp_items:
                user_prompt += f"""【第一类：用户补充资料】
这是用户额外提供的参考资料，是本次写作的核心素材，请以这些资料为主：
来源：用户直接上传/粘贴的文本、文件或链接

{self._format_supplementary_context(supp_items)}

"""

            if db_items:
                user_prompt += f"""【第二类：数据库检索资料】
这是根据您提供的主题、具体要求、关键词从知识库（Milvus）中向量搜索检索出的相关文章。
用途：作为背景补充，验证和完善用户的核心观点

{self._format_database_context(db_items)}

"""

        else:
            user_prompt += "\n\n（无参考资料，请基于你的行业知识储备进行分析）"

        user_prompt += """

## 输出要求

请生成一份完整的文章大纲，包含：

1. **文章标题**（简洁有力，体现核心观点）

2. **章节结构**（3-6个主要章节，每章包含）：
   - 章节标题
   - 章节说明（该章节要讨论的核心内容）
   - 引用卡片（基于哪些参考资料，具体引用了哪些观点）
   - 字数估算

3. **写作指导**（可选）：
   - 开头切入点建议
   - 章节之间如何过渡
   - 结尾升华点

## 输出格式

请使用以下Markdown格式输出：

**【文章标题】**：xxx

---

### 一、章节标题
**说明**：xxx
**引用卡片**：
- 【参考资料1】xxx（引用观点简述）
- 【参考资料2】xxx（引用观点简述）
**字数估算**：约xxx字

### 二、章节标题
...

---

请确保：
1. 章节之间有清晰的逻辑递进关系
2. 每个章节都有具体的参考资料支撑，尤其是用户补充资料
3. 字数分配要体现内容的重要性和复杂度
4. 避免章节标题过于宽泛或重复
5. **立意要新颖**：避免老生常谈的观点，要有独到见解
6. **深度与广度并重**：既有技术深度，又有产业视野"""

        return {
            "system": self.build_system_prompt(),
            "user": user_prompt,
        }

    def _format_supplementary_context(self, supp_items: List[KnowledgeContext]) -> str:
        """格式化用户补充资料"""
        parts = []
        for i, item in enumerate(supp_items, 1):
            source_label = f"（来源: {item.title}）"
            if item.url:
                source_label = f"（来源: {item.title} | {item.url}）"
            parts.append(f"""【补充资料 {i}】
标题: {item.title}
来源: {source_label}
内容:
{item.content}
""")
        return "\n".join(parts)

    def _format_database_context(self, db_items: List[KnowledgeContext], max_chars: int = 4000) -> str:
        """格式化数据库检索资料"""
        parts = []
        total_chars = 0
        for i, item in enumerate(db_items, 1):
            part = f"""【参考资料 {i}】
标题: {item.title}
来源: {item.author} | {item.date}
内容:
{item.content}
"""
            part_chars = len(part)
            if total_chars + part_chars > max_chars:
                remaining = max_chars - total_chars
                if remaining > 200:
                    part = f"""【参考资料 {i}】
标题: {item.title}
来源: {item.author} | {item.date}
内容:
{item.content[:remaining - 50]}...(内容截断)
"""
                    parts.append(part)
                break
            parts.append(part)
            total_chars += part_chars
        return "\n".join(parts)

    def build_revision_prompt(
        self,
        original_outline: str,
        feedback: str,
        knowledge_items: List[KnowledgeContext],
    ) -> Dict[str, str]:
        """
        构建大纲修订提示词

        Args:
            original_outline: 原大纲
            feedback: 用户修改意见
            knowledge_items: 知识条目列表

        Returns:
            包含system和user键的字典
        """
        knowledge_context = self.build_knowledge_context(knowledge_items)

        system_prompt = """你是一位资深的行业策划编辑，擅长根据用户反馈优化文章大纲。

【工作原则】
1. 仔细理解用户的修改意见
2. 在保持原大纲优点的基础上进行修订
3. 确保修订后的章节之间逻辑清晰、递进合理
4. 确保引用卡片准确反映参考资料

【修订类型】
- 增加章节：新增有必要的章节，删除冗余内容
- 删除章节：删除与主题不相关的内容
- 合并章节：将过于细碎的章节合并
- 拆分章节：将过于庞大的章节拆分
- 调整顺序：优化章节逻辑递进
- 修改内容：根据反馈修改章节说明或引用

请根据用户反馈，输出修订后的完整大纲。"""

        user_prompt = f"""## 原大纲

{original_outline}

## 用户修改意见

{feedback}
"""

        if knowledge_context:
            user_prompt += f"""

## 参考资料

{knowledge_context}

请基于以上资料和用户反馈，生成修订后的大纲。
"""
        else:
            user_prompt += "\n\n请基于你的行业知识，生成修订后的大纲。"

        user_prompt += """

## 输出格式

请直接输出修订后的完整大纲，使用以下Markdown格式：

**【文章标题】**：xxx

---

### 一、章节标题
**说明**：xxx
**引用卡片**：
- 【参考资料1】xxx（引用观点简述）
**字数估算**：约xxx字

### 二、章节标题
...

"""

        return {
            "system": system_prompt,
            "user": user_prompt,
        }

    def build_section_regenerate_prompt(
        self,
        original_outline: str,
        section_title: str,
        feedback: str,
        knowledge_items: List[KnowledgeContext],
    ) -> Dict[str, str]:
        """
        构建仅重写特定章节的提示词

        Args:
            original_outline: 原大纲
            section_title: 要重写的章节标题
            feedback: 对该章节的修改意见
            knowledge_items: 知识条目列表

        Returns:
            包含system和user键的字典
        """
        knowledge_context = self.build_knowledge_context(knowledge_items)

        system_prompt = """你是一位资深的行业策划编辑，擅长优化文章大纲的单个章节。

【工作原则】
1. 仅重写用户指定的章节
2. 保持其他章节不变
3. 确保新章节与整体大纲逻辑一致
4. 确保引用卡片准确

请仅输出修订后的该章节内容，不要修改其他章节。"""

        user_prompt = f"""## 原大纲

{original_outline}

## 需要重写的章节

【{section_title}】

## 用户对该章节的修改意见

{feedback}
"""

        if knowledge_context:
            user_prompt += f"""

## 参考资料

{knowledge_context}
"""

        user_prompt += f"""

请输出修订后的【{section_title}】章节，使用以下格式：

### {section_title}
**说明**：xxx
**引用卡片**：
- 【参考资料1】xxx（引用观点简述）
**字数估算**：约xxx字

注意：只输出这一个章节的内容，不要输出完整大纲。
"""

        return {
            "system": system_prompt,
            "user": user_prompt,
        }

    def parse_outline_sections(self, outline_text: str) -> List[OutlineSection]:
        """
        解析大纲文本，提取章节结构

        Args:
            outline_text: 大纲文本（Markdown格式）

        Returns:
            章节列表
        """
        sections = []
        lines = outline_text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 匹配章节标题（以 ### 开头）
            if line.startswith('### '):
                if current_section:
                    sections.append(current_section)

                title = line[4:].strip()
                current_section = OutlineSection(
                    title=title,
                    description="",
                    citations=[],
                    word_count_estimate=0,
                )
            elif current_section:
                # 解析章节内容
                if line.startswith('**说明**') or line.startswith('说明：'):
                    current_section.description = line.split('：', 1)[-1].strip()
                    if current_section.description.startswith('**'):
                        current_section.description = current_section.description.strip('*')
                elif line.startswith('**字数估算**') or line.startswith('字数估算：'):
                    try:
                        num_str = line.split('约')[-1].strip().rstrip('字').strip()
                        current_section.word_count_estimate = int(num_str)
                    except (ValueError, IndexError):
                        current_section.word_count_estimate = 500
                elif '【参考资料' in line and '】' in line:
                    # 解析引用卡片
                    parts = line.split('】', 1)
                    if len(parts) == 2:
                        citation = {
                            "title": parts[0].replace('【参考资料', '').strip(),
                            "source_quote": parts[1].strip().lstrip('：').lstrip('-').strip(),
                        }
                        current_section.citations.append(citation)

        if current_section:
            sections.append(current_section)

        return sections


if __name__ == "__main__":
    # 测试
    builder = DeepBriefPromptBuilder()

    knowledge = [
        KnowledgeContext(
            title="大模型推理能力提升",
            url="https://example.com/1",
            author="AI研究员",
            date="2024-01-15",
            content="新一代大模型在推理任务上取得了显著进步...",
        ),
    ]

    task = WritingTask(
        topic="某国产大模型发布对AI行业的影响",
        requirements="分析该大模型的技术突破、商业影响和竞争格局",
        keywords=["大模型", "AI", "国产替代"],
        length="3000字左右",
        target_audience="企业高管、行业投资者",
        perspective="资深行业观察者",
        min_dimensions=5,
    )

    prompt = builder.build_deep_brief_prompt(task, knowledge)

    print("=" * 60)
    print("SYSTEM PROMPT:")
    print("=" * 60)
    print(prompt["system"])
    print("\n" + "=" * 60)
    print("USER PROMPT:")
    print("=" * 60)
    print(prompt["user"])


if __name__ == "__main__":
    # 测试
    from dataclasses import asdict

    builder = PromptBuilder()

    # 测试知识上下文
    knowledge = [
        KnowledgeContext(
            title="远程办公的未来趋势",
            url="https://example.com/1",
            author="张三",
            date="2024-01-15",
            content="远程办公正在成为新常态...",
        ),
        KnowledgeContext(
            title="企业管理模式变革",
            url="https://example.com/2",
            author="李四",
            date="2024-02-20",
            content="随着技术发展，企业管理模式正在经历深刻变革...",
        ),
    ]

    task = WritingTask(
        topic="远程办公对企业管理的影响",
        requirements="分析远程办公对企业管理的积极和消极影响，提出可行建议",
        keywords=["远程办公", "企业管理", "数字化转型"],
        length="2000字左右",
    )

    prompt = builder.build_prompt(task, knowledge)

    print("=" * 50)
    print("SYSTEM PROMPT:")
    print("=" * 50)
    print(prompt["system"])
    print("\n" + "=" * 50)
    print("USER PROMPT:")
    print("=" * 50)
    print(prompt["user"])
