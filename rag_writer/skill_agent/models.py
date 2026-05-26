#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SkillAgent数据模型 - Pydantic定义

定义核心数据结构，包括：
- StrategyBlueprint: 策略蓝图（核心输出）
- StrategyCase: 策略案例库条目
- WritingInstructions: 编译后的写作指令
- ReflectionResult: 校验结果
"""

from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class WritingTone(str, Enum):
    """写作基调枚举"""

    PROFESSIONAL = "professional"  # 专业严肃
    CASUAL = "casual"  # 轻松随意
    AUTHORITATIVE = "authoritative"  # 权威指导
    ANALYTICAL = "analytical"  # 理性分析
    NARRATIVE = "narrative"  # 叙事故事


class ContentType(str, Enum):
    """内容类型枚举"""

    INDUSTRY_ANALYSIS = "行业分析"
    PRODUCT_REVIEW = "产品评测"
    TREND_INTERPRETATION = "趋势解读"
    DEEP_OBSERVATION = "深度观察"
    TECH_INTERPRETATION = "技术解读"
    COMPANY_PROFILE = "企业观察"
    INTERVIEW = "人物专访"


class OpeningApproach(str, Enum):
    """开篇方式枚举"""

    STORY_ENTRY = "故事切入"
    DATA_IMPACT = "数据震撼"
    QUESTION_RAISE = "问题引发"
    CONTRAST = "对比反差"
    QUOTE = "引用名言"
    SCENE = "场景描写"
    NEWS_HOOK = "新闻切入"


class ClosingApproach(str, Enum):
    """收尾方式枚举"""

    ELEVATION = "升华展望"
    QUESTION_CALLBACK = "问题回扣"
    ACTION_CALL = "行动呼吁"
    SUMMARY = "总结要点"
    OPEN_END = "留白思考"


class StructuralApproach(str, Enum):
    """结构手法枚举"""

    DATA_DRIVEN = "数据驱动"
    COMPARISON = "对比分析"
    CASE_STUDY = "案例映射"
    COUNTERINTUITIVE = "反常识切入"
    TIME_LINE = "时间线式"
    PROBLEM_SOLUTION = "问题-方案"
    CAUSE_EFFECT = "归因分析"


# ============ 策略蓝图相关模型 ============


class OpeningStrategy(BaseModel):
    """开篇策略"""

    approach: str = Field(
        description="开篇方式：故事切入/数据震撼/问题引发/对比反差/引用名言/场景描写"
    )
    hook_content: str = Field(description="钩子内容具体描述")
    lead_length: str = Field(description="引导段落长度建议，如：50字内/100字内/150字内")
    case_references: List[str] = Field(
        default_factory=list,
        description="引用的策略案例ID列表"
    )


class SectionStrategy(BaseModel):
    """单节写作策略"""

    section_id: str = Field(description="章节唯一标识，如：s1, s2")
    title: str = Field(description="章节标题")
    structural_approach: str = Field(
        default="递进式",
        description="结构手法：场景切入/举例说明/对比分析/数据驱动/问题解答/引用权威"
    )
    content_focus: str = Field(description="本节核心内容要点（必须具体到'看见了什么'）")
    hook_content: Optional[str] = Field(
        default=None,
        description="章节钩子：一句话让人想读这节，用具体场景/数字/冲突引发好奇"
    )
    style_guidance: str = Field(
        default="客观陈述，避免情绪化",
        description="风格指导：语气、句式、用词建议"
    )
    length_ratio: float = Field(
        default=0.2,
        ge=0.05,
        le=0.5,
        description="字数占比（相对于总长度）"
    )
    transition_to_next: Optional[str] = Field(
        default=None,
        description="如何过渡到下一节"
    )
    case_references: List[str] = Field(
        default_factory=list,
        description="引用的策略案例ID列表"
    )
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="策略置信度"
    )


class ClosingStrategy(BaseModel):
    """收尾策略"""

    approach: str = Field(
        description="收尾方式：升华展望/问题回扣/行动呼吁/总结要点/留白思考"
    )
    key_takeaway: str = Field(description="读者离开时的核心收获")
    ending_length: str = Field(description="结尾长度建议")
    case_references: List[str] = Field(default_factory=list)


class StrategyBlueprint(BaseModel):
    """
    策略蓝图 - SkillAgent核心输出

    这是SkillAgent生成的策略蓝图JSON Schema，
    包含完整的写作策略指导，用于引导RAGWriter生成文章。
    """

    version: str = Field(default="1.0", description="版本号")
    article_title: str = Field(default="", description="文章标题（新颖有吸引力）")
    topic: str = Field(description="写作话题")
    content_type: str = Field(
        description="内容类型：行业分析/产品评测/趋势解读/深度观察/技术解读"
    )
    target_audience: str = Field(description="目标读者画像")
    core_tension: str = Field(
        description="核心张力：这篇文章要抓住哪对核心矛盾或冲突"
    )
    supporting_points: List[str] = Field(
        default_factory=list,
        description="支持观点列表：3-5个简短有力的观点，阐明核心观点的关键维度"
    )
    writing_tone: WritingTone = Field(
        default=WritingTone.ANALYTICAL,
        description="写作基调"
    )

    # 结构化策略
    opening: OpeningStrategy = Field(description="开篇策略")
    sections: List[SectionStrategy] = Field(
        min_length=1,
        description="各节写作策略，至少1节"
    )
    closing: ClosingStrategy = Field(description="收尾策略")

    # 风格约束
    global_style_notes: List[str] = Field(
        default_factory=list,
        description="全局风格注意事项"
    )
    forbidden_patterns: List[str] = Field(
        default_factory=list,
        description="禁止的写作模式，如：'随着时代发展...'、'众所周知...'"
    )

    # 案例关联
    case_references: List[str] = Field(
        default_factory=list,
        description="引用的策略案例ID"
    )

    # 质量指标
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="整体策略置信度"
    )

    # 元数据
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="生成元信息：agent_version, generation_time, temperature等"
    )

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, v: List[SectionStrategy]) -> List[SectionStrategy]:
        """验证章节ID唯一性"""
        ids = [s.section_id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("章节ID必须唯一")
        return v

    def to_markdown(self) -> str:
        """转换为可读的Markdown格式（用于人工审核）"""
        title_display = self.article_title or self.topic
        md = f"""# 策略蓝图

**文章标题：** {title_display}
**话题：** {self.topic}
**内容类型：** {self.content_type}
**目标受众：** {self.target_audience}
**写作基调：** {self.writing_tone.value}
**置信度：** {self.confidence:.0%}

---

## 核心观点

{self.core_tension}

---

## 支持观点

"""
        for i, point in enumerate(self.supporting_points, 1):
            md += f"{i}. {point}\n"

        md += f"""
---

## 开篇策略

**方式：** {self.opening.approach}
**钩子内容：** {self.opening.hook_content}
**引导长度：** {self.opening.lead_length}

---

## 章节结构

"""
        for sec in self.sections:
            md += f"""### {sec.section_id}. {sec.title}

- **结构手法：** {sec.structural_approach}
- **章节钩子：** {sec.hook_content or "（无）"}
- **内容重点：** {sec.content_focus}
- **风格指导：** {sec.style_guidance}
- **字数占比：** {sec.length_ratio:.0%}
- **过渡：** {sec.transition_to_next or "（无）"}

"""
        md += f"""---

## 收尾策略

**方式：** {self.closing.approach}
**核心收获：** {self.closing.key_takeaway}
**结尾长度：** {self.closing.ending_length}

---

## 风格约束

**注意事项：**
"""
        for note in self.global_style_notes:
            md += f"- {note}\n"

        md += "\n**禁止模式：**\n"
        for pattern in self.forbidden_patterns:
            md += f"- ~~{pattern}~~\n"

        return md


# ============ 策略案例库相关模型 ============


class SectionAnnotation(BaseModel):
    """章节策略标注"""

    section_title: str = Field(description="章节标题")
    position: int = Field(description="章节位置序号")
    structural_approach: str = Field(description="结构手法")
    content_focus: str = Field(description="内容重点")
    style_guidance: str = Field(description="风格指导")
    transition_to_next: Optional[str] = Field(default=None, description="过渡到下一节")
    notable_techniques: List[str] = Field(default_factory=list, description="亮点手法")


class ArticleAnnotation(BaseModel):
    """文章策略标注（离线标注格式）"""

    opening_approach: str = Field(description="开篇方式")
    opening_effectiveness: float = Field(
        ge=1.0, le=5.0, description="开篇效果评分1-5"
    )
    opening_analysis: Optional[str] = Field(
        default=None, description="开篇效果分析"
    )
    structural_pattern: str = Field(description="结构模式：递进式/并列式/对比式/时间线式")
    section_strategies: List[SectionAnnotation] = Field(
        default_factory=list, description="各节策略标注"
    )
    closing_approach: str = Field(description="收尾方式")
    closing_effectiveness: float = Field(
        ge=1.0, le=5.0, description="收尾效果评分1-5"
    )
    closing_analysis: Optional[str] = Field(default=None, description="收尾效果分析")
    style_features: List[str] = Field(default_factory=list, description="风格特征")
    notable_techniques: List[str] = Field(default_factory=list, description="亮点手法")
    core_tension: Optional[str] = Field(default=None, description="核心张力/矛盾")
    target_audience: Optional[str] = Field(default=None, description="目标受众")


class StrategyCase(BaseModel):
    """
    策略案例 - 策略案例库中的单个案例

    对应Milvus中存储的一条记录
    """

    case_id: str = Field(description="案例唯一标识，如：case_001")
    title: str = Field(description="文章标题")
    article_url: str = Field(default="", description="原文链接")
    content_type: str = Field(description="内容类型")
    target_audience: str = Field(default="", description="目标受众")

    # 标注内容
    annotation: ArticleAnnotation = Field(description="策略标注")

    # 向量检索用（可选，不存入Milvus）
    embedding: Optional[List[float]] = None

    # 质量指标
    quality_score: float = Field(
        ge=0.0, le=5.0, description="综合质量评分"
    )

    # 分类标签
    tags: List[str] = Field(default_factory=list, description="标签")

    # 时间戳
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="创建时间"
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON存储）"""
        return {
            "case_id": self.case_id,
            "title": self.title,
            "article_url": self.article_url,
            "content_type": self.content_type,
            "target_audience": self.target_audience,
            "annotation": self.annotation.model_dump(),
            "quality_score": self.quality_score,
            "tags": self.tags,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyCase":
        """从字典创建（从JSON加载）"""
        if isinstance(data.get("annotation"), dict):
            data["annotation"] = ArticleAnnotation(**data["annotation"])
        return cls(**data)


# ============ 校验与指令相关模型 ============


class IssueItem(BaseModel):
    """校验发现的问题项"""

    issue_type: str = Field(description="问题类型：完整性/一致性/可执行性/事实性")
    location: str = Field(description="问题位置，如：opening/sections[0]/closing")
    description: str = Field(description="问题描述")
    severity: str = Field(
        default="warning",
        description="严重程度：critical/warning/info"
    )


class ReflectionResult(BaseModel):
    """
    Self-Reflection校验结果
    """

    is_valid: bool = Field(description="策略蓝图是否通过校验")
    issues: List[IssueItem] = Field(
        default_factory=list, description="发现的问题列表"
    )
    suggestions: List[str] = Field(
        default_factory=list, description="修改建议"
    )
    confidence_adjustment: float = Field(
        default=0.0,
        ge=-0.5,
        le=0.5,
        description="基于校验结果的置信度调整"
    )
    overall_score: float = Field(
        ge=0.0, le=1.0, description="综合评分"
    )


class SectionInstruction(BaseModel):
    """分节写作指令"""

    section_id: str
    title: str
    instruction_text: str
    key_points: List[str] = Field(default_factory=list, description="必须涵盖的关键点")
    style_reminders: List[str] = Field(default_factory=list, description="风格提醒")


class WritingInstructions(BaseModel):
    """
    StrategyCompiler输出的写作指令

    供RAGWriter.write_from_blueprint()使用
    """

    topic: str
    content_type: str
    target_audience: str
    core_tension: str
    writing_tone: WritingTone

    # 完整写作指令文本
    instruction_text: str = Field(
        description="编译后的完整写作指令"
    )

    # 分节指令
    section_instructions: List[SectionInstruction] = Field(
        default_factory=list
    )

    # 风格约束
    style_constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="风格约束字典"
    )

    # RAG上下文（事实内容）
    rag_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="RAG检索的事实内容"
    )

    # 引用的策略案例
    case_references: List[str] = Field(
        default_factory=list,
        description="引用的策略案例ID"
    )
