"""Command-line interface for pii-cleaner."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from pii_cleaner import __version__
from pii_cleaner.config import load_config, validate_config, CleanerConfig
from pii_cleaner.processors.csv_processor import CSVProcessor, CSVProcessResult
from pii_cleaner.processors.pdf_processor import PDFProcessor, PDFProcessResult
from pii_cleaner.redactors.text_redactor import TextRedactor
from pii_cleaner.reporters.run_reporter import RunReport, FileResult, load_report
from pii_cleaner.utils.file_utils import (
    clean_path, collect_files, is_supported, make_output_path, peer_clean_dir,
    split_csv_sections,
)

logger = logging.getLogger(__name__)
console = Console()
error_console = Console(stderr=True, style="red")

app = typer.Typer(
    name="pii-cleaner",
    help="Redact PII from CSV and PDF bank/credit card statements.",
    add_completion=False,
)

redact_app = typer.Typer(help="Redact PII from files or folders.")
app.add_typer(redact_app, name="redact")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pii-cleaner version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging.")] = False,
) -> None:
    """PII Cleaner - Redact PII from bank statements and credit card records."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _load_config_or_exit(config_path: Path | None) -> CleanerConfig:
    try:
        return load_config(config_path)
    except Exception as e:
        error_console.print(f"[red]Failed to load config: {e}[/red]")
        raise typer.Exit(1)


def _build_processors(config: CleanerConfig) -> tuple[CSVProcessor, PDFProcessor]:
    redactor = TextRedactor(config)
    csv_proc = CSVProcessor(config, redactor)
    pdf_proc = PDFProcessor(config, redactor)
    return csv_proc, pdf_proc


def _start_run() -> tuple[str, str]:
    """Return (run_id, started_at) for a new run."""
    return str(uuid.uuid4()), datetime.now(timezone.utc).isoformat()


def _print_dry_run_notice() -> None:
    console.print(Panel("[yellow]DRY RUN mode - no files will be written. Pass --apply to write output.[/yellow]"))


def _make_csv_file_result(
    input_path: Path, out_path: Path, result: CSVProcessResult
) -> FileResult:
    return FileResult(
        input_path=str(input_path),
        output_paths=[str(out_path)] if result.output_path else [],
        file_type="csv",
        success=result.success,
        rows_or_pages=result.rows_processed,
        fields_changed=result.fields_changed,
        entities_by_type=result.entities_by_type,
        warnings=result.warnings,
        error=result.error,
        input_hash=result.input_hash,
        output_hash=result.output_hash,
    )


def _make_pdf_file_result(input_path: Path, result: PDFProcessResult) -> FileResult:
    return FileResult(
        input_path=str(input_path),
        output_paths=[str(p) for p in result.output_paths],
        file_type="pdf",
        success=result.success,
        rows_or_pages=result.pages_processed,
        fields_changed=0,
        entities_by_type=result.entities_by_type,
        warnings=result.warnings,
        error=result.error,
        input_hash=result.input_hash,
        output_hash=None,
    )


def _finalize_run(
    run_id: str,
    started_at: str,
    dry_run: bool,
    config: Path | None,
    file_results: list[FileResult],
    report_dir: Path,
    cfg: CleanerConfig,
) -> None:
    report = RunReport(
        run_id=run_id,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc).isoformat(),
        dry_run=dry_run,
        config_path=str(config) if config else None,
        files=file_results,
    )
    _print_run_summary(report)
    if cfg.create_audit_report and not dry_run:
        report_path = report_dir / f"report_{run_id[:8]}.json"
        report.save(report_path)
        console.print(f"[dim]Report saved: {report_path}[/dim]")
    if report.failed_files:
        raise typer.Exit(1)


def _print_run_summary(report: RunReport) -> None:
    table = Table(title="Run Summary", show_header=True, header_style="bold cyan")
    table.add_column("File", style="dim")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Rows/Pages")
    table.add_column("Fields Changed")
    table.add_column("Entities Found")

    for fr in report.files:
        status = "[green]OK[/green]" if fr.success else "[red]FAILED[/red]"
        total_entities = sum(fr.entities_by_type.values())
        table.add_row(
            Path(fr.input_path).name,
            fr.file_type,
            status,
            str(fr.rows_or_pages),
            str(fr.fields_changed),
            str(total_entities),
        )

    console.print(table)

    summary = report.aggregate_entities
    if summary:
        ent_table = Table(title="Entities Detected", show_header=True, header_style="bold magenta")
        ent_table.add_column("Entity Type")
        ent_table.add_column("Count", justify="right")
        for ent, count in sorted(summary.items(), key=lambda x: -x[1]):
            ent_table.add_row(ent, str(count))
        console.print(ent_table)

    color = "green" if report.failed_files == 0 else "red"
    console.print(
        Panel(
            f"[{color}]Files: {report.total_files} processed, "
            f"{report.successful_files} succeeded, "
            f"{report.failed_files} failed[/{color}]",
            title="Complete",
        )
    )

    all_warnings = [(Path(fr.input_path).name, w) for fr in report.files for w in fr.warnings]
    if all_warnings:
        console.print()
        for fname, msg in all_warnings:
            console.print(f"[yellow]⚠ {fname}:[/yellow] {msg}")


@redact_app.command("file")
def redact_file(
    input_path: Annotated[Path, typer.Argument(help="Path to the input CSV or PDF file.")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output path.")] = None,
    config: Annotated[Optional[Path], typer.Option("--config", "-c", help="Config YAML file.")] = None,
    apply: Annotated[bool, typer.Option("--apply", help="Apply changes (default: dry-run preview).")] = False,
    force: Annotated[bool, typer.Option("--force", help="Allow overwriting input file.")] = False,
) -> None:
    """Redact PII from a single CSV or PDF file."""
    if not input_path.exists():
        error_console.print(f"Input file does not exist: {input_path}")
        raise typer.Exit(1)

    if not is_supported(input_path):
        error_console.print(f"Unsupported file type: {input_path.suffix}")
        raise typer.Exit(1)

    cfg = _load_config_or_exit(config)
    dry_run = not apply

    if dry_run:
        _print_dry_run_notice()

    if output is None:
        output = clean_path(peer_clean_dir(input_path.parent) / input_path.name)

    if not force and output.resolve() == input_path.resolve():
        error_console.print("Output path is the same as input. Use --force to overwrite.")
        raise typer.Exit(1)

    run_id, started_at = _start_run()
    csv_proc, pdf_proc = _build_processors(cfg)
    file_results = []

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task(f"Processing {input_path.name}...", total=1)

        suffix = input_path.suffix.lower()
        if suffix == ".csv":
            result = csv_proc.process(input_path, output, dry_run=dry_run)
            file_results.append(_make_csv_file_result(input_path, output, result))
        elif suffix == ".pdf":
            out_dir = output.parent if output.suffix == ".pdf" else output
            result = pdf_proc.process(input_path, out_dir, dry_run=dry_run)
            file_results.append(_make_pdf_file_result(input_path, result))

        progress.advance(task)

    _finalize_run(run_id, started_at, dry_run, config, file_results, output.parent, cfg)


@redact_app.command("folder")
def redact_folder(
    input_dir: Annotated[Path, typer.Argument(help="Directory containing CSV/PDF files.")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output directory.")] = None,
    config: Annotated[Optional[Path], typer.Option("--config", "-c", help="Config YAML file.")] = None,
    recursive: Annotated[bool, typer.Option("--recursive", "-r", help="Process subdirectories recursively.")] = False,
    apply: Annotated[bool, typer.Option("--apply", help="Apply changes (default: dry-run preview).")] = False,
    force: Annotated[bool, typer.Option("--force", help="Allow overwriting input files.")] = False,
) -> None:
    """Redact PII from all supported files in a folder."""
    if not input_dir.is_dir():
        error_console.print(f"Not a directory: {input_dir}")
        raise typer.Exit(1)

    cfg = _load_config_or_exit(config)
    dry_run = not apply

    if dry_run:
        _print_dry_run_notice()

    output_dir = output or peer_clean_dir(input_dir)

    supported, skipped = collect_files(
        input_dir,
        recursive=recursive,
        include_globs=cfg.include_globs,
        exclude_globs=cfg.exclude_globs,
    )

    if not supported:
        console.print("[yellow]No supported files found.[/yellow]")
        raise typer.Exit(0)

    if skipped:
        for s in skipped:
            console.print(f"[yellow]⚠ Skipping unsupported file: {s.name}[/yellow]")

    run_id, started_at = _start_run()
    csv_proc, pdf_proc = _build_processors(cfg)
    file_results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing files...", total=len(supported))

        for file_path in supported:
            progress.update(task, description=f"Processing {file_path.name}...")
            out_path = clean_path(make_output_path(file_path, input_dir, output_dir))

            suffix = file_path.suffix.lower()
            if suffix == ".csv":
                result = csv_proc.process(file_path, out_path, dry_run=dry_run)
                file_results.append(_make_csv_file_result(file_path, out_path, result))
            elif suffix == ".pdf":
                pdf_out_dir = output_dir / out_path.stem
                result = pdf_proc.process(file_path, pdf_out_dir, dry_run=dry_run)
                file_results.append(_make_pdf_file_result(file_path, result))

            progress.advance(task)

    _finalize_run(run_id, started_at, dry_run, config, file_results, output_dir, cfg)


@app.command("preview")
def preview_file(
    input_path: Annotated[Path, typer.Argument(help="Path to the file to preview.")],
    config: Annotated[Optional[Path], typer.Option("--config", "-c", help="Config YAML file.")] = None,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of lines to preview.")] = 20,
) -> None:
    """Preview PII redaction for a file without writing output."""
    if not input_path.exists():
        error_console.print(f"File not found: {input_path}")
        raise typer.Exit(1)

    cfg = _load_config_or_exit(config)
    csv_proc, pdf_proc = _build_processors(cfg)

    console.print(Panel(f"[cyan]Preview: {input_path.name}[/cyan]"))

    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        raw_text = input_path.read_text(encoding="utf-8-sig", errors="replace")
        sections = split_csv_sections(raw_text)
        rows_shown = 0
        for section_text in sections:
            if rows_shown >= lines:
                break
            df = csv_proc._parse_section(section_text)
            if df.empty:
                continue
            result_df, _, _ = csv_proc._process_dataframe(df)
            for idx in df.index:
                if rows_shown >= lines:
                    break
                row_had_change = False
                for col in df.columns:
                    orig = df.at[idx, col]
                    redacted = result_df.at[idx, col]
                    if orig != redacted:
                        console.print(f"[dim]Col={col} Row={idx}:[/dim] [red]{orig}[/red] → [green]{redacted}[/green]")
                        row_had_change = True
                if row_had_change:
                    rows_shown += 1
    elif suffix == ".pdf":
        import pdfplumber
        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages[:3]:
                text = page.extract_text() or ""
                result = pdf_proc.redactor.redact(text)
                console.print(f"\n[bold]--- Page {page.page_number} ---[/bold]")
                if result.changed:
                    console.print("[dim]Changes detected on this page.[/dim]")
                    orig_lines = text.split("\n")
                    red_lines = result.redacted.split("\n")
                    for ol, rl in zip(orig_lines[:lines], red_lines[:lines]):
                        if ol != rl:
                            console.print(f"  [red]{ol}[/red]")
                            console.print(f"  [green]{rl}[/green]")
                else:
                    console.print("[green]No PII detected on this page.[/green]")
    else:
        error_console.print(f"Unsupported file type: {suffix}")
        raise typer.Exit(1)


@app.command("validate-config")
def validate_config_cmd(
    config_path: Annotated[Path, typer.Argument(help="Path to the YAML config file.")],
) -> None:
    """Validate a configuration file."""
    if not config_path.exists():
        error_console.print(f"Config file not found: {config_path}")
        raise typer.Exit(1)

    is_valid, errors = validate_config(config_path)

    if is_valid:
        console.print(Panel("[green]✓ Configuration is valid![/green]"))
    else:
        console.print(Panel(f"[red]✗ Configuration has {len(errors)} error(s):[/red]"))
        for err in errors:
            console.print(f"  [red]• {err}[/red]")
        raise typer.Exit(1)


@app.command("report")
def show_report(
    run_artifact_path: Annotated[Path, typer.Argument(help="Path to a run report JSON file.")],
) -> None:
    """Display a previously saved run report."""
    if not run_artifact_path.exists():
        error_console.print(f"Report file not found: {run_artifact_path}")
        raise typer.Exit(1)

    try:
        data = load_report(run_artifact_path)
    except Exception as e:
        error_console.print(f"Failed to load report: {e}")
        raise typer.Exit(1)

    summary = data.get("summary", {})

    console.print(Panel(f"[cyan]Run Report: {run_artifact_path.name}[/cyan]"))
    console.print(f"Run ID: {data.get('run_id', 'N/A')}")
    console.print(f"Started: {data.get('started_at', 'N/A')}")
    console.print(f"Completed: {data.get('completed_at', 'N/A')}")
    console.print(f"Dry Run: {data.get('dry_run', False)}")

    table = Table(title="File Results", show_header=True, header_style="bold cyan")
    table.add_column("File")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Rows/Pages")
    table.add_column("Fields Changed")

    for fr in data.get("files", []):
        status = "[green]OK[/green]" if fr.get("success") else "[red]FAILED[/red]"
        table.add_row(
            Path(fr.get("input_path", "")).name,
            fr.get("file_type", ""),
            status,
            str(fr.get("rows_or_pages", 0)),
            str(fr.get("fields_changed", 0)),
        )

    console.print(table)

    if summary:
        console.print(
            f"\nTotal: {summary.get('total_files', 0)} files, "
            f"{summary.get('successful_files', 0)} succeeded, "
            f"{summary.get('failed_files', 0)} failed"
        )


if __name__ == "__main__":
    app()
