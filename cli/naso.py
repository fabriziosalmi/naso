import os
import random
import sys
import time

import click
import psutil
from art import tprint
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

console = Console()
NASO_CI = os.getenv("NASO_CI", "0") == "1"


def smart_sleep(seconds):
    if not NASO_CI:
        time.sleep(seconds)


def crumble_text(text):
    """Effetto Crumble: il testo si dissolve in particelle."""
    chars = list(text)
    for _ in range(len(chars)):
        idx = random.randint(0, len(chars) - 1)
        if chars[idx] != " ":
            chars[idx] = random.choice([".", "*", " ", "°", "·"])
        sys.stdout.write(f"\r\033[K{''.join(chars)}")
        sys.stdout.flush()
        smart_sleep(0.02)
    print("\r\033[K", end="")


def generate_benchmark_table():
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("COMPONENT", style="dim", width=20)
    table.add_column("LATENCY", justify="right")
    table.add_column("THROUGHPUT", justify="right")
    table.add_column("LOAD")

    cpu_usage = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent

    table.add_row("Core Engine", "0.02ms", "145k req/s", f"[green]{cpu_usage}%")
    table.add_row("Async DB", "0.45ms", "12k q/s", f"[yellow]{mem}%")
    table.add_row("ES Cluster", "1.20ms", "8.5k docs/s", "[green]12%")
    table.add_row("Tor Pool", "450ms", "5 nodes", "[blue]ACTIVE")

    return table


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    """
    NASO ELITE CLI - Advanced Forensic Interface.

    Usa -h o --help per la documentazione.
    """
    pass


@cli.command()
def splash():
    """Visualizza lo splash screen FAAANG 100x."""
    console.clear()
    tprint("NASO", font="isometric1")
    console.print("[bold blue]>[/bold blue] [bold white]NASO FORENSIC OS v4.0.1-STABLE[/bold white]", justify="center")
    console.print("[dim]Initialising neural interface...[/dim]", justify="center")
    smart_sleep(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None, style="blue"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        t1 = progress.add_task("[white]Calibrating TLS 1.3 Handshake...", total=100)
        t2 = progress.add_task("[white]Syncing Tor Identity Pool...", total=100)

        while not progress.finished:
            progress.update(t1, advance=random.uniform(0.5, 2) if not NASO_CI else 100)
            progress.update(t2, advance=random.uniform(0.3, 1.5) if not NASO_CI else 100)
            smart_sleep(0.05)


@cli.command()
def monitor():
    """Monitoraggio Real-Time con estetica hacker."""
    console.clear()
    layout = Layout()
    layout.split_column(Layout(name="header", size=3), Layout(name="body"), Layout(name="footer", size=3))

    layout["header"].update(
        Panel("[bold cyan]NASO LIVE MONITOR - PERFORMANCE & FORENSICS[/bold cyan]", border_style="blue")
    )

    with Live(layout, refresh_per_second=4, screen=True):
        while True:
            layout["body"].update(generate_benchmark_table())
            layout["footer"].update(
                Text(
                    f"System Epoch: {time.time()} | Integrity: 100% | Auth: ROOT", style="dim italic", justify="center"
                )
            )
            smart_sleep(0.25)
            if NASO_CI:
                break  # Exit monitor immediately in CI


@cli.command()
@click.argument("target")
def scan(target):
    """Esegue una scansione forense con effetto crumble sul leak."""
    if not target:
        console.print("[bold red]ERROR:[/bold red] Target mancante.")
        sys.exit(1)

    try:
        console.print(f"[bold red]![/bold red] Initiating deep scan for: [bold cyan]{target}[/bold cyan]")
        smart_sleep(2)

        leaks = [
            f"CRITICAL: Found {target} credentials in BreachForums dump.",
            f"WARNING: SSL Certificate for {target} expiring in 48h.",
            f"INFO: Internal project name '{target}-alpha' detected on GitHub.",
        ]

        for leak in leaks:
            console.print(f"\n[bold yellow]DETECTED:[/bold yellow] {leak}")
            smart_sleep(1)
            console.print("[dim]Cleaning forensic traces...[/dim]")
            crumble_text(leak)
            console.print("[green]DONE[/green]")
    except Exception as e:
        console.print(f"[bold red]CRITICAL FAILURE:[/bold red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
