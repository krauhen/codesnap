"""LLM-based code summarization functionality."""

import asyncio
import os
from pathlib import Path

import httpx


class LLMProvider:
    """Base class for LLM providers."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or self._get_api_key()

    def _get_api_key(self) -> str | None:
        """Get API key from environment variables."""
        return None

    async def summarize_code(self, code: str, file_path: str, num_sentences: int = 3) -> str:
        """Summarize code using the LLM provider."""
        raise NotImplementedError("Subclasses must implement this method")


class OpenAIProvider(LLMProvider):
    """OpenAI API provider for code summarization."""

    def _get_api_key(self) -> str | None:
        return os.environ.get("OPENAI_API_KEY")

    async def summarize_code(self, code: str, file_path: str, num_sentences: int = 3) -> str:
        """Summarize code using OpenAI API."""
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        # Determine file type for better context
        file_ext = Path(file_path).suffix

        # Create a simple prompt
        prompt = f"Summarize this {file_ext} code in {num_sentences} sentences:\n\n{code}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    json={
                        "model": os.environ.get("CODESNAP_LLM_MODEL", "gpt-4o"),
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a code analysis assistant that provides concise, technical summaries of code files.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 150,
                    },
                )

                if response.status_code != 200:
                    return f"Error: Failed to get summary (Status {response.status_code})"

                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Error: {str(e)}"


class AnthropicProvider(LLMProvider):
    """Anthropic API provider for code summarization."""

    def _get_api_key(self) -> str | None:
        return os.environ.get("ANTHROPIC_API_KEY")

    async def summarize_code(self, code: str, file_path: str, num_sentences: int = 3) -> str:
        """Summarize code using Anthropic API."""
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable."
            )

        # Determine file type for better context
        file_ext = Path(file_path).suffix

        # Create a simple prompt
        prompt = f"Summarize this {file_ext} code in {num_sentences} sentences:\n\n{code}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": os.environ.get("CODESNAP_LLM_MODEL", "claude-3-opus-20240229"),
                        "max_tokens": 150,
                        "temperature": 0.3,
                        "system": "You are a code analysis assistant that provides concise, technical summaries of code files.",
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )

                if response.status_code != 200:
                    return f"Error: Failed to get summary (Status {response.status_code})"

                data = response.json()
                return data["content"][0]["text"].strip()
        except Exception as e:
            return f"Error: {str(e)}"


class CodeSummarizer:
    """Manages code summarization using different LLM providers."""

    def __init__(self, provider_name: str | None = None):
        """Initialize the code summarizer with the specified provider."""
        self.provider_name = provider_name or os.environ.get("CODESNAP_LLM_PROVIDER", "auto")
        self.provider = self._get_provider()

    def _get_provider(self) -> LLMProvider:
        """Get the appropriate LLM provider based on configuration."""
        if self.provider_name == "auto":
            # Try to determine provider based on available API keys
            if os.environ.get("ANTHROPIC_API_KEY"):
                return AnthropicProvider()
            if os.environ.get("OPENAI_API_KEY"):
                return OpenAIProvider()
            raise ValueError("No API keys found for any supported LLM provider.")
        if self.provider_name == "anthropic":
            return AnthropicProvider()
        if self.provider_name == "openai":
            return OpenAIProvider()
        raise ValueError(f"Unsupported LLM provider: {self.provider_name}")

    async def summarize_file(self, file_path: Path, num_sentences: int = 3) -> str:
        """Summarize a single file."""
        try:
            code = file_path.read_text(encoding="utf-8")
            return await self.provider.summarize_code(code, str(file_path.name), num_sentences)
        except UnicodeDecodeError:
            return "Binary file (cannot summarize)"
        except Exception as e:
            return f"Error summarizing file: {str(e)}"

    async def summarize_files(self, files: list[Path], num_sentences: int = 3) -> dict[str, str]:
        """Summarize multiple files concurrently."""
        tasks = []
        for file_path in files:
            tasks.append(self.summarize_file(file_path, num_sentences))

        summaries = await asyncio.gather(*tasks)
        return {
            str(file_path): summary for file_path, summary in zip(files, summaries, strict=False)
        }
