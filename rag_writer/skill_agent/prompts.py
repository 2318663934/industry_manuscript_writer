#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SkillAgent提示词构建模块

构建策略生成、Self-Reflection等提示词
"""

import json
from typing import List, Dict, Any, Optional
from ..prompt_engineering import KnowledgeContext


# ============ 系统提示词 ============

SKILL_AGENT_SYSTEM_PROMPT = """【角色定义】
你是一位资深行业主编与写作策略架构师。

【核心使命】
你的任务不是写文章，而是设计"写作蓝图"——告诉作者应该用什么策略、什么角度、什么手法来写这篇文章。

【策略学习指南】
在设计写作策略时，要深入学习优质文章的以下维度：
1. **立意** - 如何找到一击即中的洞察（不是泛泛而谈，而是颠覆认知或揭示真相）
2. **挖掘** - 如何层层深入（不是表面罗列，而是追问"所以呢？"直到本质）
3. **洞悉本质** - 如何用具体细节让读者"看见"（不是抽象概念，而是有画面感的场景）
4. **衍生** - 如何从一件事连接到更广的涟漪（不是机械扩写，而是有机延伸）
5. **更高层次** - 如何让微观事件承载宏观意义（不是强行拔高，而是自然升华）
6. **更广视野** - 如何让技术/商业关联到人的处境（不是数据堆砌，而是洞察人心）

【蓝图结构要求】
策略蓝图必须包含清晰的两层结构：

**第一层：框架概览**（让读者一眼看清文章骨架）
- core_tension: 核心观点（必须是一击即中的洞察——反直觉的发现、颠覆认知的真相、或令人深思的事实。避免"XX是趋势"、"XX很重要"这种正确的废话）
- supporting_points: 支持观点列表（每个必须具体到"谁/在什么情况下/发生了什么"。3-5个观点要形成逻辑链，共同支撑核心张力）

**第二层：章节展开**（指导文章如何具体展开）
每个章节描述必须：
- 标题直击要点（避免"现状分析"、"问题探讨"这种正确的废话）
- content_focus具体到"看见了什么"（不是"分析问题"，而是"还原场景：A和B的对决，结果C震惊了所有人"）
- hook_content有画面感（让人想读下去的具体场景/数字/冲突）

【用词原则 - 最高优先级】
- 能用具体名词，不用抽象概念（"裁员3000人" > "缩减规模"）
- 能用动词，不用形容词（"砍掉70%成本" > "效率提升"）
- 能说影响，不说意义（"客户流失率翻倍" > "面临挑战"）
- 能用对比，不用平衡（"从100万跌到10万" > "发生变化"）

【输出要求 - 最高优先级】
- 直接输出JSON格式的策略蓝图，不要输出任何分析文字
- 不要写"分析如下"、"以下是"等引导语
- 不要在JSON之前输出任何思考过程、规划步骤或解释性文字
- JSON必须完整，以}结束，不要被截断

【严禁事项】
- 禁止使用"感官进化"、"时代礼赞"、"技术革命"、"赋能"、"生态化反"等虚词
- 禁止"众所周知"、"毋庸置疑"、"毫无疑问"等套话开头
- 禁止"我们应该..."、"企业必须..."、"必须指出"等说教句式
- 禁止在JSON前写任何文字"""


# ============ Few-shot示例 ============

FEW_SHOT_EXAMPLES = [
    {
        "task": "以'大模型定价战'为话题写一篇行业分析，目标受众是企业高管和投资者",
        "output": """{
    "version": "1.0",
    "topic": "大模型定价战：一场没有赢家的消耗战",
    "content_type": "行业分析",
    "target_audience": "企业高管、投资者",
    "core_tension": "价格战短期刺激市场，长期侵蚀行业创新动力",
    "supporting_points": [
        "某头部厂商降价90%后，中小厂商订单量腰斩，生存空间被严重压缩",
        "价格战背后是GPU利用率普遍低于40%的算力浪费问题",
        "客户实际采购成本下降超70%，但供应商毛利率已触及生死线"
    ],
    "writing_tone": "analytical",
    "opening": {
        "approach": "数据震撼",
        "hook_content": "某厂商价格降幅超90%，意味着什么",
        "lead_length": "100字内",
        "case_references": []
    },
    "sections": [
        {
            "section_id": "s1",
            "title": "价格战的导火索",
            "structural_approach": "数据驱动",
            "content_focus": "各家定价策略对比、成本结构分析",
            "hook_content": "当一家公司的定价策略开始被同行视为威胁，价格战就已经开始了",
            "style_guidance": "用数据说话，克制情绪化表达",
            "length_ratio": 0.2,
            "transition_to_next": "价格背后是...",
            "case_references": [],
            "confidence": 0.85
        },
        {
            "section_id": "s2",
            "title": "谁在烧钱谁在观望",
            "structural_approach": "对比分析",
            "content_focus": "不同玩家的策略差异",
            "hook_content": "在这场消耗战中，有人选择跟进，有人选择观望，结局截然不同",
            "style_guidance": "客观中立，不选边站队",
            "length_ratio": 0.2,
            "transition_to_next": "这场战能打多久...",
            "case_references": [],
            "confidence": 0.8
        }
    ],
    "closing": {
        "approach": "升华展望",
        "key_takeaway": "价格战是表象，生态战才是终局",
        "ending_length": "150字内",
        "case_references": []
    },
    "global_style_notes": [
        "多引用具体数字，少用抽象描述",
        "保持批判性视角，不被厂商宣传带节奏"
    ],
    "forbidden_patterns": [
        "随着时代发展...",
        "众所周知...",
        "我们应该..."
    ],
    "confidence": 0.78
}"""
    }
]


class SkillPromptBuilder:
    """SkillAgent提示词构建器"""

    def __init__(self):
        self.system_prompt = SKILL_AGENT_SYSTEM_PROMPT

    def build_strategy_prompt(
        self,
        topic: str,
        rag_context: str,
        content_type: Optional[str] = None,
        target_audience: Optional[str] = None,
        few_shot_cases: Optional[List[Dict[str, str]]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        background: Optional[str] = None,
        requirements: Optional[str] = None,
        length: Optional[str] = None,
        article_count: int = 5,
        brainstorm_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        构建策略生成提示词

        Args:
            topic: 写作话题
            rag_context: RAG检索到的上下文
            content_type: 内容类型
            target_audience: 目标受众
            few_shot_cases: Few-shot案例列表
            constraints: 额外约束条件
            background: 背景信息（时事背景等）
            requirements: 具体要求
            length: 字数要求
            article_count: 检索文章数量（用于学习写作策略）

        Returns:
            {"system": ..., "user": ...}
        """
        user_parts = []

        # 任务说明
        user_parts.append("## 写作任务\n")
        user_parts.append(f"**话题/主题:** {topic}\n")

        # 背景信息
        if background:
            user_parts.append(f"**背景:** {background}\n")

        # 具体要求
        if requirements:
            user_parts.append(f"**具体要求:** {requirements}\n")

        if content_type:
            user_parts.append(f"**内容类型:** {content_type}\n")

        if target_audience:
            user_parts.append(f"**目标受众:** {target_audience}\n")

        # 字数要求
        if length:
            user_parts.append(f"**字数要求:** {length}\n")

        # 约束条件
        if constraints:
            if "writing_tone" in constraints:
                user_parts.append(f"**写作基调:** {constraints['writing_tone']}\n")
            if "user_feedback" in constraints:
                user_parts.append(f"\n**用户修改意见（请务必采纳）:**\n")
                user_parts.append(f"{constraints['user_feedback']}\n")

        # 头脑风暴结果（注入选定角度和立意）
        if brainstorm_results:
            selected_angles = brainstorm_results.get("selected_angles", [])
            custom_feedback = brainstorm_results.get("custom_feedback", "")
            product_context = brainstorm_results.get("product_context", "")

            if selected_angles:
                user_parts.append("\n---\n\n## 头脑风暴结果（用户选定的切入角度和立意）\n\n")
                user_parts.append("以下是用户经过头脑风暴选定的角度，请将这些角度作为蓝图设计的**核心输入**：\n\n")
                for i, angle in enumerate(selected_angles, 1):
                    user_parts.append(f"**选定角度 {i}: {angle.get('angle_title', '')}**\n")
                    user_parts.append(f"- 核心立意: {angle.get('stance', '')}\n")
                    user_parts.append(f"- 选择理由: {angle.get('reasoning', '')}\n")
                    if angle.get('product_facts'):
                        user_parts.append(f"- 支撑事实: {'; '.join(angle['product_facts'])}\n")
                    if angle.get('depth', 0) > 0:
                        user_parts.append(f"- 深度级别: 第{angle['depth']}层展开\n")
                    user_parts.append("\n")
                user_parts.append("**关键指令**：请将上述角度融入策略蓝图设计——core_tension应基于选定角度的核心立意，supporting_points应展开角度的关键维度，各section应呼应角度中的产品事实。\n")

            if custom_feedback:
                user_parts.append(f"\n**用户补充想法**: {custom_feedback}\n")

            if product_context:
                user_parts.append(f"\n**相关产品背景（供事实参考）**: \n{product_context[:2000]}\n")

        # 策略学习指南
        user_parts.append("""\n---\n\n## 策略学习维度\n

设计写作策略时，要从以下维度深入思考：

1. **立意** - 如何找到独特的切入角度？
   - 这篇文章要抓住哪对核心矛盾？
   - 如何从独特视角切入而非泛泛而谈？

2. **挖掘** - 如何层层深入？
   - 如何避免停留在表面分析？
   - 如何引导读者思考更深层的问题？

3. **洞悉本质** - 如何揭示事物本质？
   - 现象背后的根本原因是什么？
   - 什么才是这件事的关键变量？

4. **衍生** - 如何从一个点延伸？
   - 如何从单一事件关联到更广泛的现象？
   - 如何从一个维度扩展到多个维度？

5. **更高层次** - 如何提升视野？
   - 如何站在产业/行业/时代高度看问题？
   - 如何关联宏观趋势和微观事件？

6. **更广视野** - 如何拓宽思考边界？
   - 如何关联技术范式变革？
   - 如何关联商业逻辑和社会趋势？
""")

        # 策略案例参考——只展示框架结构（切入方式+递进脉络），不展示写作手法细节
        if few_shot_cases:
            user_parts.append("\n---\n\n## 专业优质文章参考（学习框架与递进方法）\n\n")
            user_parts.append("以下是专业文章的结构拆解，学习它们的**切入角度→章节如何层层递进→如何收尾**，但不要照搬其具体内容：\n\n")
            for i, case in enumerate(few_shot_cases, 1):
                section_flow_str = "\n".join([f"     {s}" for s in case.get('section_flow', [])]) if case.get('section_flow') else "     未标注"
                user_parts.append(f"""**范文 {i}**：《{case.get('title', '')}》
  - 内容类型：{case.get('content_type', '未知')}
  - 目标受众：{case.get('target_audience', '未知')}
  - 核心张力：{case.get('core_tension', '未标注')}
  - 开篇方式：{case.get('opening_approach', '未标注')}
  - 整体结构：{case.get('structural_pattern', '未标注')}
  - 章节递进脉络：
{section_flow_str}
  - 收尾方式：{case.get('closing_approach', '未标注')}

""")

        # RAG上下文（用于事实支撑）
        if rag_context:
            user_parts.append("\n---\n\n## 事实参考资料\n")
            user_parts.append("以下是相关参考资料，用于支撑文章论点：\n")
            user_parts.append(f"{rag_context}\n")
            user_parts.append("\n**使用注意：**")
            user_parts.append("- 不要直接复制原文，要指定引用策略")
            user_parts.append("- 若某论点缺乏事实支撑，在content_focus中标注'需补充XX数据'\n")

        # 输出要求
        user_parts.append("""\n---\n\n## 输出要求

请以JSON格式输出策略蓝图，结构如下：

**第一部分：框架概览**（让读者一眼看清文章骨架）
- core_tension: 核心观点（必须是：一击即中的洞察/颠覆认知的反直觉发现/令人深思的真相。避免"XX发展趋势"、"XX行业分析"这种空洞话题陈述）
- supporting_points: 支持观点列表（3-5个，每个必须：①具体可证，②与核心观点形成逻辑链，③一句话说明白一件事）

**第二部分：章节展开**（指导文章如何具体展开）
每个章节的描述必须具体、可感知、有画面感：
- section_id/title: 章节编号和标题（标题要直击要点，避免"现状分析"、"问题探讨"）
- structural_approach: 结构手法（用具体手法名，如"数据对比"、"时间线还原"、"因果链拆解"）
- content_focus: 内容要点（必须具体到"谁、在什么情况下、发生了什么、意味着什么"。避免"分析XX问题"、"探讨XX趋势"这种模糊表述）
- hook_content: 章节钩子（一句话让人想读这节，用具体场景/数字/冲突引发好奇）
- length_ratio: 篇幅占比
- transition_to_next: 过渡句（承上启下，用具体内容衔接）

**第三部分：首尾策略**
- opening: 开篇策略
  - approach: 具体手法（如"惊人数据切入"、"冲突场景还原"、"反直觉设问"）
  - hook_content: 开篇第一句话（必须有冲击力，让读者停下来）
- closing: 收尾策略
  - approach: 升华路径（如"回到核心洞察"、"放大视野"、"提出行动号令"）
  - key_takeaway: 读者离场前的最后一句话（必须有回响，让人记住一件事）

完整JSON字段：
- article_title: 文章标题——必须像一流媒体的深度报道标题。要求：
  1. 有冲突感或反差（如"1.39亿日活却救不了它的开放世界"而不是"XX游戏的挑战与机遇"）
  2. 或提出一个问题（如"双英雄切换0.8秒，凭什么值一个亿？"）
  3. 或给出一个判断（如"王者世界不是下一个原神，它是第一个自己"）
  4. 绝不能用"XX分析/探讨/浅析/观察/思考"这种学术论文式标题
  5. 参考风格：36氪、晚点LatePost、游戏葡萄的深度报道标题
- topic: 话题
- content_type: 内容类型
- target_audience: 目标受众
- core_tension: 核心观点（一击即中的洞察）
- supporting_points: ["支持观点1", "支持观点2", "支持观点3"]
- writing_tone: 写作基调
- opening: {"approach": "...", "hook_content": "..."}
- sections: [{section_id, title, structural_approach, content_focus, hook_content, length_ratio, transition_to_next}]
- closing: {"approach": "...", "key_takeaway": "..."}
- global_style_notes: ["风格注意事项1", "风格注意事项2"]（如无特殊要求则为空数组[]）
- forbidden_patterns: ["禁止模式1", "禁止模式2"]（如无特殊要求则为空数组[]）
- confidence: 置信度

**用词原则**：每个描述都要让人能想象出具体画面。能用具体名词，不用抽象概念；能用动词，不用形容词；能说"砍掉70%成本"，不说"提升效率"。

请直接输出JSON，不要加说明文字。确保JSON完整，以}结尾。""")

        return {
            "system": self.system_prompt,
            "user": "".join(user_parts),
        }

    def build_simple_strategy_prompt(
        self,
        topic: str,
        rag_context: str,
        content_type: Optional[str] = None,
        target_audience: Optional[str] = None,
        background: Optional[str] = None,
        requirements: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        构建简化版策略生成提示词（用于回退）

        这个版本更简洁，要求更少输出，减少token消耗
        """
        user_parts = []

        # 简洁的任务说明
        user_parts.append(f"## 任务\n为话题「{topic}」设计一篇{content_type or '行业分析'}文章的结构。\n")

        if background:
            user_parts.append(f"背景：{background}\n")

        if target_audience:
            user_parts.append(f"目标受众：{target_audience}\n")

        if requirements:
            user_parts.append(f"具体要求：{requirements}\n")

        # RAG上下文（精简）
        if rag_context:
            user_parts.append(f"\n## 参考资料\n{rag_context[:2000]}...\n")

        # 简化输出要求
        user_parts.append("""\n## 输出格式

输出一个JSON对象，包含：
- article_title: 文章标题（新颖、有冲击力，避免平淡的"XX分析"式标题）
- topic: 话题
- content_type: 内容类型
- target_audience: 目标受众
- core_tension: 核心观点（一击即中的洞察，避免空洞话题陈述）
- supporting_points: ["支持观点1", "支持观点2", "支持观点3"]（3-5个简短有力的观点，阐明核心观点的关键维度）
- writing_tone: analytical
- opening: {"approach": "开篇方式", "hook_content": "开头内容"}
- sections: 3个章节，每个包含 section_id, title, structural_approach, content_focus, hook_content, length_ratio, transition_to_next
- closing: {"approach": "收尾方式", "key_takeaway": "核心结论"}

直接输出JSON，不要额外说明。确保JSON完整，以}结尾。""")

        return {
            "system": "你是一个专业的写作策略设计助手，输出简洁有效的JSON结构。",
            "user": "".join(user_parts),
        }

    def build_revision_prompt(
        self,
        topic: str,
        original_blueprint: Dict[str, Any],
        user_feedback: str,
        rag_context: str,
        content_type: Optional[str] = None,
        target_audience: Optional[str] = None,
        background: Optional[str] = None,
        requirements: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        构建基于原蓝图修订的提示词

        Args:
            topic: 写作话题
            original_blueprint: 原始策略蓝图字典
            user_feedback: 用户修改意见
            rag_context: RAG检索到的上下文
            content_type: 内容类型
            target_audience: 目标受众
            background: 背景信息
            requirements: 具体要求

        Returns:
            {"system": ..., "user": ...}
        """
        import json

        user_parts = []

        # 任务说明
        user_parts.append("## 修订任务\n")
        user_parts.append(f"**话题/主题:** {topic}\n")

        if background:
            user_parts.append(f"**背景:** {background}\n")

        if requirements:
            user_parts.append(f"**具体要求:** {requirements}\n")

        if content_type:
            user_parts.append(f"**内容类型:** {content_type}\n")

        if target_audience:
            user_parts.append(f"**目标受众:** {target_audience}\n")

        # 原始蓝图
        user_parts.append("\n---\n\n## 原始策略蓝图\n")
        user_parts.append("以下是用户当前的策略蓝图，请仔细阅读并理解其结构：\n")
        user_parts.append(f"```json\n{json.dumps(original_blueprint, ensure_ascii=False, indent=2)}\n```\n")

        # 用户修改意见
        user_parts.append("\n---\n\n## 用户修改意见\n")
        user_parts.append("用户提出了以下修改意见，请务必采纳：\n")
        user_parts.append(f"{user_feedback}\n")

        # 修订指导
        user_parts.append("""\n---

## 修订指导原则

请根据用户的修改意见对原蓝图进行修订，遵循以下原则：

1. **采纳用户意见**：优先采纳用户的明确修改要求
2. **保持合理结构**：保持核心张力和整体结构合理性
3. **策略一致性**：修订后的策略应该内在一致
4. **具体可执行**：每个章节的策略描述要具体可执行
5. **立意升维**：在修订时思考是否可以从更高层次、更广视野来优化

请输出修订后的完整JSON蓝图（包含所有字段），不要只输出修改的部分。
""")

        # RAG上下文（如果存在）
        if rag_context:
            user_parts.append("\n---\n\n## RAG检索上下文\n")
            user_parts.append("以下是相关参考资料，请结合这些内容设计写作策略：\n")
            user_parts.append(f"{rag_context}\n")

        # 输出要求
        user_parts.append("""\n## 输出要求

请输出完整的新策略蓝图JSON，包含所有必要字段：
- topic: 话题
- content_type: 内容类型
- target_audience: 目标受众
- core_tension: 核心张力
- supporting_points: ["支持观点1", "支持观点2", "支持观点3"]
- writing_tone: 写作基调
- opening: 开篇策略（包含所有子字段）
- sections: 章节策略列表（每个章节包含所有字段）
- closing: 收尾策略（包含所有子字段）
- global_style_notes: ["风格注意事项1"]（如无特殊要求则为空数组[]）
- forbidden_patterns: ["禁止模式1"]（如无特殊要求则为空数组[]）
- confidence: 置信度

请直接输出JSON，不要加任何说明文字。""")

        return {
            "system": self.system_prompt,
            "user": "".join(user_parts),
        }

    def build_reflection_prompt(
        self,
        blueprint_json: str,
        rag_context: str,
        issues: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        构建Self-Reflection校验提示词

        Args:
            blueprint_json: 策略蓝图JSON字符串
            rag_context: RAG上下文（用于事实一致性检查）
            issues: 之前发现的问题（用于针对性校验）

        Returns:
            {"system": ..., "user": ...}
        """
        system = """【角色定义】
你是一位资深编辑审核专家，负责校验策略蓝图的质量。

【校验维度】
1. 结构完整性：章节数量是否合理（3-5节）
2. 逻辑一致性：节与节之间是否递进，与核心张力是否一致
3. 可执行性：策略描述是否具体可执行
4. 事实一致性：策略中的论点是否能被RAG上下文支撑
5. 创新性：是否有独特的切入角度
6. 视野层次：是否体现更高层次、更广视野的思考

【输出标准】
- 如果通过校验：输出{"is_valid": true, "overall_score": 0.85}
- 如果需要修改：输出{"is_valid": false, "issues": [...], "suggestions": [...]}
- 仅输出JSON，不要其他说明"""

        user_parts = ["## 待校验策略蓝图\n\n"]
        user_parts.append(f"```json\n{blueprint_json}\n```\n")

        if rag_context:
            user_parts.append("\n## RAG上下文（用于事实一致性检查）\n\n")
            user_parts.append(f"{rag_context}\n")

        if issues:
            user_parts.append("\n## 已知问题（请重点校验）\n")
            for issue in issues:
                user_parts.append(f"- {issue}\n")

        return {
            "system": system,
            "user": "".join(user_parts),
        }


    def build_brainstorm_prompt(
        self,
        topic: str,
        product_context: str,
        selected_angle: Optional[Dict[str, Any]] = None,
        user_feedback: Optional[str] = None,
        brainstorm_history: Optional[List[Dict[str, Any]]] = None,
        background: Optional[str] = None,
        requirements: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        strategy_case_context: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        构建头脑风暴提示词

        两种模式：
        - 初始模式（selected_angle=None）：生成3-5个"大角度"
        - 展开模式（selected_angle有值）：沿着该角度往深处刨，生成下一层更具体的子角度

        Args:
            topic: 写作话题
            product_context: 产品知识库检索结果
            selected_angle: 用户选中的角度（有则进入展开模式）
            user_feedback: 用户补充想法
            brainstorm_history: 前几轮的对话历史
            background: 背景信息
            requirements: 具体要求
            keywords: 关键词
            strategy_case_context: 专业优质文章的策略标注（用于学习深度思考方法）

        Returns:
            {"system": ..., "user": ...}
        """
        system = """【角色定义】
你是一位资深行业分析师的创意搭档，专门帮写作者通过一步步递进追问，找到独特而有深度的文章切入角度。

【核心使命】
不只是生成角度列表，更要展示"深度思考"的过程——每一次展开都是一次更深的挖掘。

【深度思考方法论——"刨根法"】
优秀的行业分析遵循以下递进逻辑，每一层都比上一层更具体、更触及本质：

第1层（大角度）：选一个切入方向——"这件事最值得关注的是什么？"
  → 例："双英雄共鸣系统不是微创新，而是开放世界的品类重构"

第2层（子角度）：挖一层——"这个方向背后，真正关键的机制/数据/矛盾是什么？"
  → 例："深入双英雄共鸣：即时切换机制如何改变玩家在开放世界中的空间决策"

第3层（再挖深）：再挖一层——"这个机制/数据/矛盾的根源或影响是什么？"
  → 例："双英雄切换的CD设计：0.8秒是战斗爽感与策略深度的临界点——它是怎么测出来的？"

第4层（更深的追问）：更底层——"这背后反映了什么趋势/人性/规则变化？"
  → 例："从双英雄到多角色：MOBA基因的开放世界正在重写'角色扮演'的定义"

核心原则：
- 每一层必须比上一层更具体，不能停留在同一抽象层级
- 用产品事实说话，不是空想
- 好的角度应该让人产生"原来如此"或"这个角度有意思"的反应

【严禁事项】
- 禁止在同一层级换表述（如把"技术创新"改成"技术突破"——这叫翻来覆去，不是深入）
- 禁止用抽象概念解释抽象概念（如"提升了体验"——要具体到"砍掉了3秒的前摇僵直"）
- 禁止生成与上一层角度无本质区别的内容

【输出格式】
请以JSON数组格式输出角度列表，每个角度包含：
- angle_title: 角度标题（一句话，必须有具体的"谁/什么/怎么样"）
- stance: 核心立意（从什么立场看这件事）
- reasoning: 为什么这个角度比上一层更深（必须指出"深在哪里"——具体到了什么机制/数据/矛盾）
- product_facts: ["具体事实1", "具体事实2"]（从产品知识中提取，不可编造）
- dimension: 切入维度（用于标记是从哪个维度深入的）

直接输出JSON数组，不要任何说明文字。"""

        user_parts = []

        # 话题信息
        user_parts.append(f"## 写作话题\n{topic}\n")
        if background:
            user_parts.append(f"\n## 背景信息\n{background}\n")
        if requirements:
            user_parts.append(f"\n## 具体要求\n{requirements}\n")
        if keywords:
            user_parts.append(f"\n## 关键词\n{', '.join(keywords)}\n")

        # 策略案例——专业文章的深度思考范例
        if strategy_case_context:
            user_parts.append("\n---\n\n## 专业优质文章参考（学习如何层层深入思考）\n")
            user_parts.append("以下是专业写作者分析类似话题时的策略标注，学习他们如何架构文章、如何递进展开：\n\n")
            user_parts.append(strategy_case_context)
            user_parts.append("\n\n**关键启示**：注意上述文章如何从开篇→章节1→章节2→章节3层层递进——每层都在前一层的基础上挖得更深，而不是换个角度重说一遍。你的头脑风暴也应该遵循这种\"递进式\"思考。\n")

        # 产品知识库
        user_parts.append("\n---\n\n## 产品知识库（事实基础）\n")
        user_parts.append("以下是相关产品的最新资讯，是你生成角度的[原材料]。请严格基于这些事实：\n\n")
        user_parts.append(product_context[:5000])

        # 根据模式构建不同的任务说明
        if selected_angle and selected_angle.get("angle_title"):
            # === 展开模式 ===
            user_parts.append("\n---\n\n## 本次任务：深入展开（刨一层）\n")
            user_parts.append(f"""用户在上一步选择了以下角度，现在需要**在此基础上往深处刨一层**：

**上一层角度**：{selected_angle.get('angle_title', '')}
**上一层立意**：{selected_angle.get('stance', '')}
**上一层思考**：{selected_angle.get('reasoning', '')}

""")
            current_depth = (selected_angle.get('depth', 0) or 0) + 1
            if user_feedback:
                user_parts.append(f"**用户希望你关注的方向**：{user_feedback}\n\n")

            user_parts.append(f"""请生成3-5个**更深一层**的子角度。这一层（第{current_depth}层）的要求：

【深度的标准——必须做到以下至少一项】
1. **更具体到机制**：从笼统的"XX系统好"→具体到"XX参数的设计逻辑是什么"
2. **更接近数据**：从定性判断→定量分析（"留存率高出15%的关节点在哪"）
3. **更触及矛盾**：从表面现象→内部冲突（"宣称自由探索 vs 实际上三条主线锁死"）
4. **更走向本源**：从设计结论→设计动机（"为什么这么设计，而不是那么设计"）

【禁止事项】
- 禁止换一个角度重说一遍同样深度的话
- 禁止生成的子角度与父角度在抽象层级上没有实质区别

每个子角度的 reasoning 字段必须明确回答：**"比上一层深在哪里？"**
""")
        else:
            # === 初始模式 ===
            user_parts.append("\n---\n\n## 本次任务：寻找大角度（第1层）\n")

            if user_feedback:
                user_parts.append(f"**用户希望你关注的方向**：{user_feedback}\n\n")

            user_parts.append("""请生成3-5个"大角度"作为思考的起点。这是第1层——每个角度都应该：
1. 找到一个具体而独特的切入方向，不是泛泛而谈
2. 从不同维度切入（数据、机制、用户心理、竞争格局、设计哲学等）
3. 每个角度必须有产品知识库中的事实支撑
4. 让人有"想继续往下挖"的好奇心

dimension字段填入：data_impact / mechanism / user_psychology / competition / design_philosophy
""")

        # 对话历史（如果有多轮）
        if brainstorm_history:
            user_parts.append("\n---\n\n## 前几轮思考脉络\n")
            for i, round_data in enumerate(brainstorm_history, 1):
                user_parts.append(f"\n**第{i}轮**：\n")
                if round_data.get('angles'):
                    user_parts.append(f"该轮角度：{json.dumps([a.get('angle_title','') for a in round_data['angles']], ensure_ascii=False)}\n")
                if round_data.get('selected_angle'):
                    user_parts.append(f"用户选择深入：{round_data['selected_angle'].get('angle_title', '')}\n")
                if round_data.get('feedback'):
                    user_parts.append(f"用户补充想法：{round_data['feedback']}\n")

        # 输出要求
        user_parts.append("""\n---\n\n## 输出格式

输出一个JSON数组：

```json
[
  {
    "angle_title": "角度标题（必须具体到人名/数字/机制/矛盾）",
    "stance": "核心立意",
    "reasoning": "这个角度深在哪里/为什么有说服力",
    "product_facts": ["事实1", "事实2"],
    "dimension": "切入维度标签"
  }
]
```

直接输出JSON数组，不要任何说明。""")

        return {"system": system, "user": "".join(user_parts)}


def format_rag_context_for_skill(
    knowledge_items: List[KnowledgeContext],
    max_chars: int = 6000,
) -> str:
    """
    格式化RAG上下文供SkillAgent使用

    Args:
        knowledge_items: RAG检索到的知识条目
        max_chars: 最大字符数

    Returns:
        格式化后的上下文字符串
    """
    if not knowledge_items:
        return ""

    parts = []
    total_chars = 0

    for i, item in enumerate(knowledge_items, 1):
        source_type = getattr(item, 'source_type', 'database')
        if source_type == 'supplementary':
            prefix = f"【补充资料 {i}】"
        else:
            prefix = f"【参考资料 {i}】"

        part = f"""{prefix}
标题: {item.title}
来源: {item.author} | {item.date}
内容:
{item.content}
"""
        part_chars = len(part)

        if total_chars + part_chars > max_chars:
            remaining = max_chars - total_chars
            if remaining > 200:
                part = f"""{prefix}
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


def format_case_for_few_shot(case: Dict[str, Any]) -> str:
    """
    格式化案例供Few-shot使用

    Args:
        case: 策略案例字典

    Returns:
        格式化的案例字符串
    """
    return f"""【案例标题】: {case.get('title', '')}

【策略概要】:
- 开篇方式: {case.get('annotation', {}).get('opening_approach', '未知')}
- 结构模式: {case.get('annotation', {}).get('structural_pattern', '未知')}
- 收尾方式: {case.get('annotation', {}).get('closing_approach', '未知')}
- 核心张力: {case.get('annotation', {}).get('core_tension', '未知')}
"""