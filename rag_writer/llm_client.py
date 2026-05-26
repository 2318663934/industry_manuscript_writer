#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM调用模块 - 支持多种大模型
"""
import os
import json
from typing import Dict, Any, Optional, List, Iterator
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .config import settings


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    model: str
    usage: Dict[str, int]
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMClient(ABC):
    """LLM客户端基类"""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """生成文本"""
        pass

    @abstractmethod
    def generate_stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式生成文本"""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "请安装 openai 库: pip install openai\n"
                "或者使用其他支持的模型"
            )

        api_key = api_key or settings.llm.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("未设置OpenAI API Key")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or settings.llm.base_url,
        )
        self.model = model or settings.llm.model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """生成文本"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
        )

    def generate_stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式生成文本"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def generate_with_system(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        """带系统提示词的生成"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )


class ClaudeClient(BaseLLMClient):
    """Claude客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "请安装 anthropic 库: pip install anthropic"
            )

        api_key = api_key or settings.llm.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("未设置Anthropic API Key")

        self.client = Anthropic(api_key=api_key)
        # Claude模型映射
        self.model = model or "claude-3-5-haiku-20241017"
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """生成文本"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text if response.content else ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    def generate_stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式生成文本"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def generate_with_system(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        """带系统提示词的生成"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text if response.content else ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )


class SiliconFlowClient(BaseLLMClient):
    """SiliconFlow客户端（支持多种模型）"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://api.siliconflow.cn/v1",
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装 openai 库: pip install openai")

        api_key = api_key or settings.llm.api_key or os.getenv("SILICONFLOW_API_KEY")
        if not api_key:
            raise ValueError("未设置SiliconFlow API Key")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model or "Qwen/Qwen2.5-7B-Instruct"
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """生成文本"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )

    def generate_stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式生成文本"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def generate_with_system(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        """带系统提示词的生成"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )


class ZhipuClient(BaseLLMClient):
    """智谱AI客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4",
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装 openai 库: pip install openai")

        api_key = api_key or settings.llm.api_key or os.getenv("ZHIPU_API_KEY")
        if not api_key:
            raise ValueError("未设置智谱AI API Key")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model or "glm-4"
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """生成文本"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )

    def generate_with_system(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        """带系统提示词的生成"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )


class MiniMaxClient(BaseLLMClient):
    """MiniMax AI客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://api.minimax.chat/v1",
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装 openai 库: pip install openai")

        api_key = api_key or settings.llm.api_key or os.getenv("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("未设置MiniMax API Key")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        # MiniMax常用模型
        self.model = model or "MiniMax-M2.7"
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """生成文本"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )

    def generate_stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式生成文本"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def generate_with_system(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        """带系统提示词的生成"""
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )


# 客户端工厂
class LLMClientFactory:
    """LLM客户端工厂"""

    _clients = {
        "openai": OpenAIClient,
        "claude": ClaudeClient,
        "siliconflow": SiliconFlowClient,
        "zhipu": ZhipuClient,
        "minimax": MiniMaxClient,
    }

    @classmethod
    def create(cls, provider: Optional[str] = None, **kwargs) -> BaseLLMClient:
        """
        创建LLM客户端

        Args:
            provider: 提供商名称 (openai/claude/siliconflow/zhipu)
            **kwargs: 传递给客户端的其他参数

        Returns:
            LLM客户端实例
        """
        provider = provider or settings.llm.provider
        client_class = cls._clients.get(provider)

        if client_class is None:
            supported = ', '.join(cls._clients.keys())
            raise ValueError(f"不支持的提供商: {provider}，支持的: {supported}")

        return client_class(**kwargs)

    @classmethod
    def register(cls, name: str, client_class: type):
        """注册新的客户端类型"""
        cls._clients[name] = client_class


def create_llm_client(provider: Optional[str] = None, **kwargs) -> BaseLLMClient:
    """创建LLM客户端（便捷函数）"""
    return LLMClientFactory.create(provider, **kwargs)


if __name__ == "__main__":
    # 测试连接
    import sys

    if len(sys.argv) > 1:
        provider = sys.argv[1] if len(sys.argv) > 1 else None
        try:
            client = create_llm_client(provider)
            print(f"✓ {provider or '默认'} 客户端创建成功")

            # 测试生成
            response = client.generate("你好，请介绍一下你自己", max_tokens=100)
            print(f"✓ 生成测试成功 (使用模型: {response.model})")
            print(f"响应: {response.content[:200]}...")
            print(f"用量: {response.usage}")

        except ValueError as e:
            print(f"配置错误: {e}")
        except ImportError as e:
            print(f"缺少依赖: {e}")
        except Exception as e:
            print(f"错误: {e}")
    else:
        print("用法: python llm_client.py <provider>")
        print("支持的provider: openai, claude, siliconflow, zhipu")
