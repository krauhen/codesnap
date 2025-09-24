"""Command-line interface for codesnap.

This module defines the CLI for codesnap, which generates LLM-friendly codebase snapshots
for pasting into ChatGPT, Claude, or similar large language models.

The CLI favors a copy-to-clipboard workflow for fast use with LLMs, but also supports
file output when automation or storage is required. Include/exclude patterns give users
control over the snapshot scope, and optional summarization condenses file content via LLMs.
"""

import sys
from pathlib import Path

import click
from rich.console import Console

from codesnap import __version__
from codesnap.config import Config, Language
from codesnap.core import CodeSnapshotter
from codesnap.formatters import OutputFormat
from codesnap.utils import copy_to_clipboard, detect_language

console = Console()


def include_option(f):
    """Decorator to add the --include option to a Click command.

    Args:
        f (function): The function to decorate.

    Returns:
        function: Decorated function with the `--include` option added.
    """
    return click.option(
        "--include",
        multiple=True,
        help=(
            "Glob pattern(s) for files to always include in the snapshot. "
            "Use this to force inclusion of important files that may otherwise be excluded."
        ),
    )(f)


def exclude_option(f):
    """Decorator to add the --exclude option to a Click command.

    Args:
        f (function): The function to decorate.

    Returns:
        function: Decorated function with the `--exclude` option added.
    """
    return click.option(
        "--exclude",
        multiple=True,
        help=(
            "Glob pattern(s) for files or folders to exclude from the snapshot. "
            "Commonly used for build artifacts, large generated files, or irrelevant code."
        ),
    )(f)


def search_term_option(f):
    """Decorator to add the --search-term option to a Click command.

    Args:
        f (function): The function to decorate.

    Returns:
        function: Decorated function with the `--search-term` option added.
    """
    return click.option(
        "-s",
        "--search-term",
        multiple=True,
        help=(
            "Only include files whose name or path contains the given keyword(s). "
            "Useful for focusing snapshots on parts of a large codebase."
        ),
    )(f)


def output_option(f):
    """Decorator to add output-related options to a Click command.

    Adds:
        - `-o/--output`: Write snapshot to a file.
        - `-c/--clipboard`: Copy snapshot to clipboard.

    Args:
        f (function): Function to decorate.

    Returns:
        function: Decorated function with output options added.
    """
    f = click.option(
        "-o",
        "--output",
        type=click.Path(),
        help=(
            "Write snapshot result to a file. "
            "Mainly for automation or archiving. "
            "If neither this nor --clipboard is set, output prints to stdout."
        ),
    )(f)
    f = click.option(
        "-c",
        "--clipboard",
        is_flag=True,
        help=(
            "Copy the snapshot directly to clipboard (recommended for LLM workflow)."
        ),
    )(f)
    return f


def language_option(f):
    """Decorator to add the --language option.

    Args:
        f (function): Function to decorate.

    Returns:
        function: Decorated function with `--language` option added.
    """
    return click.option(
        "-l",
        "--language",
        type=click.Choice(["javascript", "typescript", "python"], case_sensitive=False),
        help=(
            "Explicit project language (overrides auto-detection). "
            "Use this option if auto-detection guesses wrong."
        ),
    )(f)


def max_tokens_option(f):
    """Decorator to add the --max-tokens option.

    Args:
        f (function): Function to decorate.

    Returns:
        function: Decorated function with `--max-tokens` option added.
    """
    return click.option(
        "--max-tokens",
        type=int,
        help=(
            "Maximum number of tokens allowed in the output. "
            "Ensures snapshot fits within your LLM's context window."
        ),
    )(f)


def model_encoding_option(f):
    """Decorator to add the --model-encoding option.

    Args:
        f (function): Function to decorate.

    Returns:
        function: Decorated function with `--model-encoding` option added.
    """
    return click.option(
        "--model-encoding",
        type=click.Choice(["cl100k_base", "o200k_base"], case_sensitive=False),
        default="o200k_base",
        show_default=True,
        help=(
            "Set tokenizer encoding to match your LLM (o200k_base for GPT-4+, cl100k_base for GPT-3.5)."
        ),
    )(f)


def count_tokens_option(f):
    """Decorator to add the --count-tokens/--no-count-tokens options.

    Args:
        f (function): Function to decorate.

    Returns:
        function: Decorated function with token counting option.
    """
    return click.option(
        "--count-tokens/--no-count-tokens",
        default=True,
        help=(
            "Enable or disable token counting. "
            "Counting guarantees token budget enforcement. "
            "Disable for faster runs if exact token count is not required."
        ),
    )(f)


def tree_options(f):
    """Decorator to add directory tree related options.

    Args:
        f (function): Function to decorate.

    Returns:
        function: Decorated function with tree options.
    """
    f = click.option(
        "--no-tree",
        is_flag=True,
        help="Omit the directory tree from output (useful for very large trees).",
    )(f)
    f = click.option(
        "--tree-depth",
        type=int,
        help="Maximum depth of the directory tree to display (e.g., 2 for shallow view).",
    )(f)
    f = click.option(
        "--tree-style",
        type=click.Choice(["ascii"]),
        default="ascii",
        show_default=True,
        help="Tree style (ascii characters). Limited to ASCII for maximum compatibility.",
    )(f)
    return f


def summarize_options(f):
    """Decorator to add summarization related options.

    Args:
        f (function): Function to decorate.

    Returns:
        function: Decorated function with summarization options.
    """
    f = click.option(
        "--summarize",
        is_flag=True,
        help=(
            "Summarize each file with an LLM to condense context "
            "for prompt efficiency and high-level understanding."
        ),
    )(f)
    f = click.option(
        "--llm-provider",
        type=click.Choice(["auto", "openai", "anthropic"]),
        default="auto",
        show_default=True,
        help="Choose LLM provider for summarization (auto selects from configured API keys).",
    )(f)
    f = click.option(
        "--summary-sentences",
        type=int,
        default=3,
        show_default=True,
        help="Number of sentences per per-file summary.",
    )(f)
    return f


@click.command()
@click.version_option(version=__version__, prog_name="codesnap")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
    default=".",
)
@language_option
@output_option
@max_tokens_option
@model_encoding_option
@count_tokens_option
@tree_options
@include_option
@exclude_option
@search_term_option
@summarize_options
def main(
    path: Path,
    language: str | None,
    output: str | None,
    clipboard: bool,
    max_tokens: int | None,
    model_encoding: str,
    count_tokens: bool,
    no_tree: bool,
    tree_depth: int | None,
    tree_style: str,
    include: tuple[str, ...],
    exclude: tuple[str, ...],
    search_term: tuple[str, ...],
    summarize: bool,
    llm_provider: str,
    summary_sentences: int,
) -> None:
    """Generate an LLM-friendly snapshot of a code project.

    Includes directory tree, file contents, and optionally file summaries,
    formatted for direct copy-paste into LLM prompts.

    Args:
        path: Path to the project root.
        language: Language override (if auto-detection fails).
        output: File path for saving snapshot.
        clipboard: If true, copy snapshot directly to clipboard.
        max_tokens: Maximum token budget for LLM context.
        model_encoding: Encoding scheme for tokenizer.
        count_tokens: Whether to enforce token budgeting.
        no_tree: If true, omit directory tree.
        tree_depth: Maximum depth of directory tree.
        tree_style: Directory tree style (ascii).
        include: Inclusion glob patterns.
        exclude: Exclusion glob patterns.
        search_term: Name keywords for file filtering.
        summarize: Whether to generate LLM-based summaries.
        llm_provider: Provider for summaries.
        summary_sentences: Sentences per summary.
    """
    try:
        run_cli(
            path=path,
            language=language,
            output=output,
            clipboard=clipboard,
            max_tokens=max_tokens,
            model_encoding=model_encoding,
            count_tokens=count_tokens,
            no_tree=no_tree,
            tree_depth=tree_depth,
            tree_style=tree_style,
            include=include,
            exclude=exclude,
            search_term=search_term,
            summarize=summarize,
            llm_provider=llm_provider,
            summary_sentences=summary_sentences,
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def run_cli(
    path: Path,
    language: str | None,
    output: str | None,
    clipboard: bool,
    max_tokens: int | None,
    model_encoding: str,
    count_tokens: bool,
    no_tree: bool,
    tree_depth: int | None,
    tree_style: str,
    include: tuple[str, ...],
    exclude: tuple[str, ...],
    search_term: tuple[str, ...],
    summarize: bool,
    llm_provider: str,
    summary_sentences: int,
) -> None:
    """Run main CLI workflow.

    Args:
        path: Project root path.
        language: Programming language override or auto-detect.
        output: Destination file path (optional).
        clipboard: If true, copy snapshot to clipboard.
        max_tokens: Maximum token count budget.
        model_encoding: Tokenizer encoding.
        count_tokens: If true, enforce LLM token budgeting.
        no_tree: Omit directory tree in snapshot.
        tree_depth: Max depth of tree.
        tree_style: Render style for tree.
        include: Glob patterns for forced-included files.
        exclude: Glob patterns for excluded files.
        search_term: Keyword filters applied to filenames.
        summarize: True if summarization should be applied.
        llm_provider: Which LLM provider to use.
        summary_sentences: Number of sentences per summary.
    """
    if not language:
        language = _detect_language_or_exit(path)

    config = Config(
        whitelist_patterns=list(include),
        exclude_patterns=list(exclude),
        search_terms=list(search_term),
    )
    lang_enum = Language(language.lower())
    snapshotter = CodeSnapshotter(
        path, lang_enum, config, model_encoding, count_tokens=count_tokens
    )

    file_summaries = _maybe_summarize(
        snapshotter, summarize, llm_provider, summary_sentences
    )

    snapshot = snapshotter.create_snapshot(
        max_tokens=max_tokens,
        show_tree=not no_tree,
        tree_depth=tree_depth,
        tree_style=tree_style,
        output_format=OutputFormat.TEXT,
        file_summaries=file_summaries,
    )

    _handle_output(snapshot, output, clipboard)


def _detect_language_or_exit(path: Path) -> str:
    """Detect or exit if language cannot be determined.

    Args:
        path: Project root.

    Returns:
        str: Detected language string.

    Raises:
        SystemExit: If detection fails.
    """
    detected_lang = detect_language(path)
    if not detected_lang:
        console.print(
            "[red]Error:[/red] Could not detect language. Specify with -l/--language."
        )
        sys.exit(1)
    return detected_lang


def _maybe_summarize(
    snapshotter: CodeSnapshotter, summarize: bool, llm_provider: str, summary_sentences: int
) -> dict[str, str]:
    """Conditionally summarize files with LLM.

    Args:
        snapshotter: Snapshotter instance.
        summarize: Whether to summarize.
        llm_provider: Provider for LLM calls.
        summary_sentences: Sentences per summary.

    Returns:
        dict[str, str]: Mapping of file path to summary text.
    """
    if not summarize:
        return {}
    try:
        import asyncio
        from codesnap.summarize import CodeSummarizer

        files = snapshotter._collect_files()
        summarizer = CodeSummarizer(llm_provider)
        return asyncio.run(summarizer.summarize_files(files, summary_sentences))
    except ImportError:
        console.print(
            "[yellow]Summarization requires httpx package. Install with: pip install httpx"
        )
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Summarization failed: {e}")
    return {}


def _handle_output(snapshot, output: str | None, clipboard: bool):
    """Output snapshot to clipboard, file, or stdout.

    Args:
        snapshot: Snapshot object (content, meta).
        output: Path to output file, or None.
        clipboard: If true, copy to clipboard instead of file/stdout.
    """
    if clipboard:
        if copy_to_clipboard(snapshot.content):
            console.print("[green]✓[/green] Snapshot copied to clipboard.")
        else:
            console.print("[red]Error:[/red] Clipboard copy failed.")
            sys.exit(1)
    elif output:
        Path(output).write_text(snapshot.content, encoding="utf-8")
        console.print(f"[green]✓[/green] Snapshot written to [bold]{output}[/bold]")
    else:
        console.print(snapshot.content)


class NullContext:
    """A context manager that does nothing."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


if __name__ == "__main__":
    main()