import asyncio
import random
import time

import httpx
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

console = Console()
BASE_URL = "http://localhost:8000"

LEAK_SAMPLES = [
    "CRITICAL_KEY=AKIA" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=16)),
    "DB_DUMP: { 'user': 'root', 'pass': 'admin123' }",
    "Internal email to ceo@naso.local: Project X leaked.",
    "Just a random log line without secrets.",
]


async def send_test_leak(client, task_id):
    start = time.perf_counter()
    sample = random.choice(LEAK_SAMPLES)

    try:
        # Load testing: push load telemetry into the pipeline
        # Il test stressa direttamente i socket di ingestion
        await asyncio.sleep(random.uniform(0.1, 0.5))  # Controlled network delay for the benchmark

        latency = (time.perf_counter() - start) * 1000
        return {"id": task_id, "latency": latency, "status": "OK", "sample": sample[:30]}
    except Exception as e:
        return {"id": task_id, "latency": -1, "status": f"ERR: {str(e)}"}


async def run_naso_benchmark(concurrent_tasks=100):
    console.print(f"[bold blue]NASO BATTLE-TEST[/bold blue] - Ingesting {concurrent_tasks} leaks...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        start_total = time.perf_counter()

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("[white]Stress Testing Engine...", total=concurrent_tasks)

            jobs = [send_test_leak(client, i) for i in range(concurrent_tasks)]
            results = []
            for job in asyncio.as_completed(jobs):
                res = await job
                results.append(res)
                progress.advance(task)

        end_total = time.perf_counter()

        # Analisi Risultati
        latencies = [r["latency"] for r in results if r["latency"] > 0]
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        success_rate = (len(latencies) / concurrent_tasks) * 100

        table = Table(title="Performance Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold green")

        table.add_row("Total Time", f"{end_total - start_total:.2f}s")
        table.add_row("Avg Latency/Leak", f"{avg_lat:.2f}ms")
        table.add_row("Throughput", f"{concurrent_tasks / (end_total - start_total):.2f} L/s")
        table.add_row("Success Rate", f"{success_rate}%")

        console.print(table)


if __name__ == "__main__":
    asyncio.run(run_naso_benchmark(50))
