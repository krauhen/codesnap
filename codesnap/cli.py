"""Command-line interface for codesnap."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from codesnap import __version__
from codesnap.config import Config, Language
from codesnap.core import CodeSnapshotter
from codesnap.utils import copy_to_clipboard, detect_language

console = Console()


@click.command()
@click.version_option(version=__version__, prog_name="codesnap")
@click.argument("path", type=click.Path(exists=True, path_type=Path), default=".")
@click.option(
    "-l",
    "--language",
    type=click.Choice(["javascript", "typescript", "python"], case_sensitive=False),
    help="Project language (auto-detected if not specified)",
)
@click.option("-f", "--config-file", type=click.Path(exists=True), help="Config file path")
@click.option("-o", "--output", type=click.Path(), help="Output file (stdout if not specified)")
@click.option(
    "-c", "--clipboard", is_flag=True, help="Copy output to clipboard instead of stdout"
    "--model-encoding",
    type=click.Choice(["cl100k_base", "o200k_base"], case_sensitive=False),
    help="Encoding that the models use to create tokens.",
    default="o200k_base",
    show_default=True,
)
@click.option("--max-tokens", type=int, help="Maximum tokens to include")
@click.option("--no-tree", is_flag=True, help="Skip directory tree")
@click.option("--ignore", multiple=True, help="Additional ignore patterns")
@click.option("--include-ext", multiple=True, help="Additional file extensions to include")
def main(
    path: Path,
    language: Optional[str],
    config_file: Optional[str],
    output: Optional[str],
    clipboard: bool,
    max_tokens: Optional[int],
    model_encoding: Optional[str],
    no_tree: bool,
    ignore: tuple[str, ...],
    include_ext: tuple[str, ...],
) -> None:
    """
    Generate LLM-friendly code snapshots.

    PATH: Project root path (default: current directory)
    """
    try:
        # Auto-detect language if not specified
        if not language:
            detected_lang = detect_language(path)
            if not detected_lang:
                console.print(
                    "[red]Error:[/red] Could not auto-detect language. "
                    "Please specify with -l/--language"
                )
                sys.exit(1)
            language = detected_lang
            console.print(f"[dim]Auto-detected language: {language}[/dim]")

        # Load configuration
        config = Config.from_file(config_file) if config_file else Config()

        # Apply CLI overrides
        if ignore:
            config.ignore_patterns.extend(ignore)
        if include_ext:
            config.include_extensions.extend(include_ext)

        # Create snapshotter
        lang_enum = Language(language.lower())
        snapshotter = CodeSnapshotter(path, lang_enum, config, model_encoding)

        # Generate snapshot
        with console.status("[bold blue]Generating code snapshot..."):
            snapshot = snapshotter.create_snapshot(
                max_tokens=max_tokens, show_tree=not no_tree
            )

        # Output handling
        if clipboard:
            if copy_to_clipboard(snapshot.content):
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
            console.print(
                f"[green]✓[/green] Code snapshot written to [bold]{output}[/bold]"
            )
        else:
            console.print(snapshot.content)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()