import asyncio
import psutil
import threading
from src.console import console
from concurrent.futures import ThreadPoolExecutor

running_subprocesses = set()
thread_executor: ThreadPoolExecutor = None


async def cleanup():
    """Ensure all running tasks, threads, and subprocesses are properly cleaned up before exiting."""
    console.print("[yellow]Cleaning up tasks before exiting...[/yellow]")

    # ✅ Step 1: Shutdown ThreadPoolExecutor **before checking for threads**
    global thread_executor
    if thread_executor:
        console.print("[yellow]Shutting down thread pool executor...[/yellow]")
        thread_executor.shutdown(wait=True)  # Ensure threads terminate before proceeding
        thread_executor = None  # Remove reference

    # 🔹 Step 1: Stop the monitoring thread safely
    # if not stop_monitoring.is_set():
    #    console.print("[yellow]Stopping thread monitor...[/yellow]")
    #    stop_monitoring.set()  # Tell monitoring thread to stop

    # 🔹 Step 2: Wait for the monitoring thread to exit completely
    # if monitor_thread and monitor_thread.is_alive():
    #    console.print("[yellow]Waiting for monitoring thread to exit...[/yellow]")
    #    monitor_thread.join(timeout=3)  # Ensure complete shutdown
    #    if monitor_thread.is_alive():
    #        console.print("[red]Warning: Monitoring thread did not exit in time.[/red]")

    # 🔹 Step 3: Terminate all tracked subprocesses
    while running_subprocesses:
        proc = running_subprocesses.pop()
        if proc.returncode is None:  # If still running
            console.print(f"[yellow]Terminating subprocess {proc.pid}...[/yellow]")
            proc.terminate()  # Send SIGTERM first
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)  # Wait for process to exit
            except asyncio.TimeoutError:
                console.print(f"[red]Subprocess {proc.pid} did not exit in time, force killing.[/red]")
                proc.kill()  # Force kill if it doesn't exit

        # 🔹 Close process streams safely
        for stream in (proc.stdout, proc.stderr, proc.stdin):
            if stream:
                try:
                    stream.close()
                except Exception:
                    pass

    # 🔹 Step 4: Ensure subprocess transport cleanup
    await asyncio.sleep(0.1)

    # 🔹 Step 5: Cancel all running asyncio tasks **gracefully**
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    console.print(f"[yellow]Cancelling {len(tasks)} remaining tasks...[/yellow]")

    for task in tasks:
        task.cancel()

    # Stage 1: Give tasks a moment to cancel themselves
    await asyncio.sleep(0.1)

    # Stage 2: Gather tasks with exception handling
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
            console.print(f"[red]Error during cleanup: {result}[/red]")

    # 🔹 Step 6: Kill all remaining threads and orphaned processes
    kill_all_threads()

    console.print("[green]Cleanup completed. Exiting safely.[/green]")


def kill_all_threads():
    """Forcefully kill any lingering threads and subprocesses before exit."""
    console.print("[yellow]Checking for remaining background threads...[/yellow]")

    # 🔹 Kill any lingering subprocesses
    current_process = psutil.Process()
    children = current_process.children(recursive=True)

    for child in children:
        console.print(f"[yellow]Terminating process {child.pid}...[/yellow]")
        child.terminate()

    _, still_alive = psutil.wait_procs(children, timeout=3)
    for child in still_alive:
        console.print(f"[red]Force killing stubborn process: {child.pid}[/red]")
        child.kill()

    # 🔹 Remove references to completed threads
    for thread in threading.enumerate():
        if not thread.is_alive():
            del thread

    # 🔹 Print remaining active threads
    active_threads = [t for t in threading.enumerate()]
    console.print(f"[bold yellow]Remaining active threads:[/bold yellow] {len(active_threads)}")
    for t in active_threads:
        console.print(f"  - {t.name} (Alive: {t.is_alive()})")

    console.print("[green]Thread cleanup completed.[/green]")
