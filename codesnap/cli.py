"""Command-line interface for codesnap."""

import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel

from codesnap import __version__
from codesnap.config import Config, Language, ProfileManager
from codesnap.core import CodeSnapshotter
from codesnap.formatters import OutputFormat
from codesnap.utils import copy_to_clipboard, detect_language

console = Console()


class CommonOptions:
    """Common options for the CLI."""

    @staticmethod
    def path_option(f):
        return click.argument("path", type=click.Path(exists=True, path_type=Path), default=".")(f)

    @staticmethod
    def language_option(f):
        return click.option(
            "-l",
            "--language",
            type=click.Choice(["javascript", "typescript", "python"], case_sensitive=False),
            help="Project language (auto-detected if not specified)",
        )(f)

    @staticmethod
    def config_option(f):
        return click.option(
            "-f", "--config-file", type=click.Path(exists=True), help="Config file path"
        )(f)

    @staticmethod
    def output_options(f):
        f = click.option(
            "-o", "--output", type=click.Path(), help="Output file (stdout if not specified)"
        )(f)
        f = click.option(
            "-c", "--clipboard", is_flag=True, help="Copy output to clipboard instead of stdout"
        )(f)
        return f

    @staticmethod
    def token_options(f):
        f = click.option("--max-tokens", type=int, help="Maximum tokens to include")(f)
        f = click.option(
            "--model-encoding",
            type=click.Choice(["cl100k_base", "o200k_base"], case_sensitive=False),
            help="Encoding that the models use to create tokens.",
            default="o200k_base",
            show_default=True,
        )(f)
        f = click.option(
            "--token-buffer",
            type=int,
            default=100,
            help="Buffer to leave for token limit (prevents exact cutoffs)",
        )(f)
        f = click.option(
            "--count-tokens/--no-count-tokens",
            default=True,
            help="Enable/disable token counting (faster without counting)",
        )(f)
        return f

    @staticmethod
    def tree_options(f):
        f = click.option("--no-tree", is_flag=True, help="Skip directory tree")(f)
        f = click.option(
            "--tree-depth", type=int, help="Maximum depth to display in directory tree"
        )(f)
        f = click.option(
            "--tree-style",
            type=click.Choice(["ascii", "unicode"]),
            default="unicode",
            help="Style to use for directory tree",
        )(f)
        return f

    @staticmethod
    def file_selection_options(f):
        f = click.option("--ignore", multiple=True, help="Additional ignore patterns")(f)
        f = click.option(
            "--include", multiple=True, help="Explicitly include files matching pattern"
        )(f)
        f = click.option(
            "--exclude", multiple=True, help="Explicitly exclude files matching pattern"
        )(f)
        f = click.option(
            "--include-ext", multiple=True, help="Additional file extensions to include"
        )(f)
        f = click.option(
            "-s", "--search-term", multiple=True, help="Include files containing these search terms"
        )(f)
        return f

    @staticmethod
    def format_options(f):
        f = click.option(
            "--output-format",
            type=click.Choice(["markdown", "text", "json"]),
            default="markdown",
            help="Output format",
        )(f)
        f = click.option(
            "--header/--no-header", default=True, help="Include/exclude header information"
        )(f)
        f = click.option(
            "--footer/--no-footer", default=True, help="Include/exclude footer information"
        )(f)
        return f

    @staticmethod
    def file_content_options(f):
        f = click.option("--max-file-lines", type=int, help="Maximum lines to include per file")(f)
        f = click.option("--max-line-length", type=int, help="Maximum length for each line")(f)
        return f

    @staticmethod
    def profile_options(f):
        f = click.option("--profile", help="Load settings from named profile in config file")(f)
        f = click.option(
            "--save-profile", help="Save current settings to named profile in config file"
        )(f)
        return f

    @staticmethod
    def verbosity_options(f):
        f = click.option(
            "-v", "--verbose", count=True, help="Increase verbosity (can be used multiple times)"
        )(f)
        f = click.option("-q", "--quiet", is_flag=True, help="Suppress all non-essential output")(f)
        return f

    @staticmethod
    def summarization_options(f):
        f = click.option(
            "--summarize",
            is_flag=True,
            help="Generate summaries for each file using an LLM",
        )(f)
        f = click.option(
            "--llm-provider",
            type=click.Choice(["auto", "openai", "anthropic"]),
            default="auto",
            help="LLM provider to use for summarization",
        )(f)
        f = click.option(
            "--summary-sentences",
            type=int,
            default=3,
            help="Number of sentences to include in each file summary",
        )(f)
        return f

    @staticmethod
    def import_analysis_options(f):
        f = click.option(
            "--analyze-imports",
            is_flag=True,
            help="Analyze and include import relationships between files",
        )(f)
        f = click.option(
            "--import-diagram",
            is_flag=True,
            help="Include a Mermaid diagram of import relationships",
        )(f)
        return f

    @staticmethod
    def apply_all(f):
        """Apply all common options to a function."""
        f = CommonOptions.path_option(f)
        f = CommonOptions.language_option(f)
        f = CommonOptions.config_option(f)
        f = CommonOptions.output_options(f)
        f = CommonOptions.token_options(f)
        f = CommonOptions.tree_options(f)
        f = CommonOptions.file_selection_options(f)
        f = CommonOptions.format_options(f)
        f = CommonOptions.file_content_options(f)
        f = CommonOptions.profile_options(f)
        f = CommonOptions.verbosity_options(f)
        f = CommonOptions.import_analysis_options(f)
        f = CommonOptions.summarization_options(f)
        return f


@click.command()
@click.version_option(version=__version__, prog_name="codesnap")
@CommonOptions.apply_all
def main(**kwargs) -> None:
    """Generate LLM-friendly code snapshots."""
    try:
        run_cli(**kwargs)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if kwargs.get("verbose", 0) > 1:
            import traceback

            console.print(traceback.format_exc())
        sys.exit(1)


def run_cli(
    path: Path,
    language: str | None,
    config_file: str | None,
    output: str | None,
    clipboard: bool,
    max_tokens: int | None,
    model_encoding: str,
    token_buffer: int,
    count_tokens: bool,
    no_tree: bool,
    tree_depth: int | None,
    tree_style: str,
    ignore: tuple[str, ...],
    include: tuple[str, ...],
    exclude: tuple[str, ...],
    include_ext: tuple[str, ...],
    search_term: tuple[str, ...],
    output_format: str,
    header: bool,
    footer: bool,
    max_file_lines: int | None,
    max_line_length: int | None,
    profile: str | None,
    save_profile: str | None,
    verbose: int,
    quiet: bool,
    analyze_imports: bool = False,
    import_diagram: bool = False,
    summarize: bool = False,
    llm_provider: str = "auto",
    summary_sentences: int = 3,
) -> None:
    verbosity = 0 if quiet else verbose + 1

    # 1. Language detection
    if not language:
        language = _detect_language_or_exit(path, verbosity)

    # 2. Load/merge config
    config = _load_config(
        config_file,
        profile,
        save_profile,
        verbosity,
        ignore,
        include,
        exclude,
        include_ext,
        search_term,
        max_file_lines,
        max_line_length,
    )

    # 3. Snapshotter
    lang_enum = Language(language.lower())
    snapshotter = CodeSnapshotter(
        path, lang_enum, config, model_encoding, count_tokens=count_tokens
    )

    # 4. Summarization
    file_summaries = _maybe_summarize(
        snapshotter, summarize, llm_provider, summary_sentences, verbosity
    )

    # 5. Import Analysis
    import_analysis = _maybe_analyze_imports(path, snapshotter, analyze_imports, verbosity)

    # 6. Generate Snapshot
    snapshot = _generate_snapshot(
        snapshotter,
        output_format,
        max_tokens,
        token_buffer,
        no_tree,
        tree_depth,
        tree_style,
        header,
        footer,
        file_summaries,
        import_analysis,
        import_diagram,
        verbosity,
    )

    # 7. Output
    _handle_output(snapshot, output, clipboard, verbosity)


def _detect_language_or_exit(path: Path, verbosity: int) -> str:
    detected_lang = detect_language(path)
    if not detected_lang:
        console.print(
            "[red]Error:[/red] Could not auto-detect language. Please specify with -l/--language"
        )
        sys.exit(1)
    if verbosity > 0:
        console.print(f"[dim]Auto-detected language: {detected_lang}[/dim]")
    return detected_lang


def _load_config(
    config_file,
    profile,
    save_profile,
    verbosity,
    ignore,
    include,
    exclude,
    include_ext,
    search_term,
    max_file_lines,
    max_line_length,
) -> Config:
    """Load configuration, apply profile, CLI overrides, and optionally save profile."""
    config = Config.from_file(config_file) if config_file else Config()

    _apply_profile(config, config_file, profile, verbosity)
    _apply_cli_overrides(
        config, ignore, include, exclude, include_ext, search_term, max_file_lines, max_line_length
    )
    _maybe_save_profile(config, config_file, save_profile, verbosity)

    return config


def _apply_profile(
    config: Config, config_file: str | None, profile: str | None, verbosity: int
) -> None:
    """Load and merge settings from a profile if requested."""
    if not profile:
        return
    profile_manager = ProfileManager(config_file)
    profile_config = profile_manager.load_profile(profile)
    if profile_config:
        config.update(profile_config)
        if verbosity > 0:
            console.print(f"[dim]Loaded profile: {profile}[/dim]")
    else:
        console.print(f"[yellow]Warning:[/yellow] Profile '{profile}' not found")


def _apply_cli_overrides(
    config: Config,
    ignore,
    include,
    exclude,
    include_ext,
    search_term,
    max_file_lines,
    max_line_length,
) -> None:
    """Apply CLI option overrides to the configuration."""
    updates: dict[str, Any] = {}
    if ignore:
        updates["ignore_patterns"] = list(ignore)
    if include:
        updates["whitelist_patterns"] = list(include)
    if exclude:
        updates["exclude_patterns"] = list(exclude)
    if include_ext:
        updates["include_extensions"] = list(include_ext)
    if search_term:
        updates["search_terms"] = list(search_term)
    if max_file_lines is not None:
        updates["max_file_lines"] = max_file_lines
    if max_line_length is not None:
        updates["max_line_length"] = max_line_length
    config.update(updates)


def _maybe_save_profile(
    config: Config, config_file: str | None, save_profile: str | None, verbosity: int
) -> None:
    """Save updated configuration to a profile if requested."""
    if not save_profile:
        return
    profile_manager = ProfileManager(config_file)
    profile_manager.save_profile(save_profile, config)
    if verbosity > 0:
        console.print(f"[dim]Saved profile: {save_profile}[/dim]")


def _maybe_summarize(
    snapshotter, summarize, llm_provider, summary_sentences, verbosity
) -> dict[str, str]:
    if not summarize:
        return {}
    try:
        import asyncio

        from codesnap.summarize import CodeSummarizer

        if verbosity > 0:
            console.print("[dim]Generating file summaries using LLM...[/dim]")
        files = snapshotter._collect_files()
        summarizer = CodeSummarizer(llm_provider)
        summaries = asyncio.run(summarizer.summarize_files(files, summary_sentences))
        if verbosity > 0:
            console.print(f"[dim]Generated summaries for {len(summaries)} files[/dim]")
        return summaries
    except ImportError:
        console.print(
            "[yellow]Warning:[/yellow] Summarization requires httpx package. "
            "Install with: pip install httpx"
        )
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Failed to generate summaries: {e}")
    return {}


def _maybe_analyze_imports(path: Path, snapshotter, analyze_imports: bool, verbosity: int):
    if not analyze_imports:
        return None
    try:
        from codesnap.analyzer import ImportAnalyzer

        analyzer = ImportAnalyzer(path)
        analysis = analyzer.analyze_project(snapshotter._collect_files())
        if verbosity > 0:
            console.print("[dim]Analyzed import relationships between files[/dim]")
        return analysis
    except ImportError:
        console.print("[yellow]Warning:[/yellow] Import analysis requires the analyzer module")
    return None


def _generate_snapshot(
    snapshotter,
    output_format,
    max_tokens,
    token_buffer,
    no_tree,
    tree_depth,
    tree_style,
    header,
    footer,
    file_summaries,
    import_analysis,
    import_diagram,
    verbosity,
):
    output_format_enum = OutputFormat(output_format)
    with (
        console.status("[bold blue]Generating code snapshot...") if verbosity > 0 else NullContext()
    ):
        return snapshotter.create_snapshot(
            max_tokens=max_tokens,
            token_buffer=token_buffer,
            show_tree=not no_tree,
            tree_depth=tree_depth,
            tree_style=tree_style,
            show_header=header,
            show_footer=footer,
            output_format=output_format_enum,
            import_analysis=import_analysis,
            import_diagram=import_diagram,
            file_summaries=file_summaries,
        )


def _handle_output(snapshot, output: str | None, clipboard: bool, verbosity: int):
    if clipboard:
        if copy_to_clipboard(snapshot.content):
            if verbosity > 0:
                console.print(
                    Panel(
                        f"[green]✓[/green] Code snapshot copied to clipboard\n"
                        f"[dim]Characters: {len(snapshot.content):,}\n"
                        f"Files included: {snapshot.file_count}\n"
                        f"Approximate tokens: {snapshot.token_count:,}[/dim]",
                        title="Success",
                        border_style="green",
                    )
                )
        else:
            console.print("[red]Error:[/red] Failed to copy to clipboard")
            sys.exit(1)
    elif output:
        output_path = Path(output)
        output_path.write_text(snapshot.content, encoding="utf-8")
        if verbosity > 0:
            console.print(f"[green]✓[/green] Code snapshot written to [bold]{output}[/bold]")
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
