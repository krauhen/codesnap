"""LLM-based code summarization functionality.

This module provides abstractions to summarize code files using LLM providers
(OpenAI or Anthropic). It defines a provider interface (`LLMProvider`),
concrete provider implementations, and a `CodeSummarizer` orchestration class.

The summaries are intended to provide condensed natural language descriptions
of file content, useful for providing high-level project context in LLM prompts.
"""

import asyncio
import os
from pathlib import Path
import httpx


class LLMProvider:
    """Base class for Large Language Model (LLM) providers.

    Defines API contract for summarizing code using a given provider backend.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize provider with API key.

        Args:
            api_key (str | None): API key string, or None to auto-retrieve from env.
        """
        self.api_key = api_key or self._get_api_key()

    def _get_api_key(self) -> str | None:
        """Retrieve API key from environment variables.

        Returns:
            str | None: API key if found, else None.
        """
        return None

    async def summarize_code(self, code: str, file_path: str, num_sentences: int = 3) -> str:
        """Summarize the given code.

        Args:
            code (str): File content as string.
            file_path (str): Relative path or identifier of the file.
            num_sentences (int, optional): Sentence count for summary. Defaults to 3.

        Returns:
            str: Summary text.

        Raises:
            NotImplementedError: To be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement this method")


class OpenAIProvider(LLMProvider):
    """OpenAI API provider for code summarization."""

    def _get_api_key(self) -> str | None:
        """Retrieve OpenAI API key from `OPENAI_API_KEY` environment variable."""
        return os.environ.get("OPENAI_API_KEY")

    async def summarize_code(self, code: str, file_path: str, num_sentences: int = 3) -> str:
        """Summarize code using the OpenAI API.

        Args:
            code (str): File contents.
            file_path (str): File name or path (used for context).
            num_sentences (int): Number of sentences for summary.

        Returns:
            str: LLM-generated summary or error message.
        """
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        file_ext = Path(file_path).suffix
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
        """Retrieve Anthropic API key from `ANTHROPIC_API_KEY` environment variable."""
        return os.environ.get("ANTHROPIC_API_KEY")

    async def summarize_code(self, code: str, file_path: str, num_sentences: int = 3) -> str:
        """Summarize code using the Anthropic API.

        Args:
            code (str): File contents.
            file_path (str): File name or path (used for context).
            num_sentences (int): Number of sentences for summary.

        Returns:
            str: LLM-generated summary or error string.
        """
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable."
            )

        file_ext = Path(file_path).suffix
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
    """Manages summarization with available LLM providers.

    Determines provider automatically if `auto` mode is enabled or uses
    explicit provider selection (`openai`, `anthropic`).
    """

    def __init__(self, provider_name: str | None = None):
        """Initialize the summarizer.

        Args:
            provider_name (str | None): Provider name (`auto`, `openai`, or `anthropic`).
                Defaults to environment variable `CODESNAP_LLM_PROVIDER` or `"auto"`.
        """
        self.provider_name = provider_name or os.environ.get("CODESNAP_LLM_PROVIDER", "auto")
        self.provider = self._get_provider()

    def _get_provider(self) -> LLMProvider:
        """Return appropriate LLM provider instance.

        Returns:
            LLMProvider: Provider instance chosen.

        Raises:
            ValueError: If no API key or unsupported provider specified.
        """
        if self.provider_name == "auto":
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
        """Summarize a single file asynchronously.

        Args:
            file_path (Path): File to summarize.
            num_sentences (int): Length of summary.

        Returns:
            str: LLM-produced summary.
        """
        try:
            code = file_path.read_text(encoding="utf-8")
            return await self.provider.summarize_code(code, str(file_path.name), num_sentences)
        except UnicodeDecodeError:
            return "Binary file (cannot summarize)"
        except Exception as e:
            return f"Error summarizing file: {str(e)}"

    async def summarize_files(self, files: list[Path], num_sentences: int = 3) -> dict[str, str]:
        """Summarize multiple files concurrently.

        Args:
            files (list[Path]): Files to summarize.
            num_sentences (int, optional): Sentence length of summaries. Defaults to 3.

        Returns:
            dict[str, str]: {file_path: summary}
        """
        tasks = []
        for file_path in files:
            tasks.append(self.summarize_file(file_path, num_sentences))
        summaries = await asyncio.gather(*tasks)
        return {
            str(file_path): summary for file_path, summary in zip(files, summaries, strict=False)
        }
