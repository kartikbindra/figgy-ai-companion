#!/usr/bin/env python3
"""
Figgy Interactive Terminal CLI
Test chat, persona switching, fusion mixing, and memory recall from your terminal.
"""

import sys
import json
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

console = Console()
API_BASE = "http://localhost:8000"
CONVERSATION_ID = "cli-test-session"


def print_banner():
    banner_text = """
 [bold magenta]FIGGY[/bold magenta] — [italic cyan]The Unhinged Handheld AI Companion[/italic cyan]
 [dim]Type your message to chat, or use commands:[/dim]
   [yellow]/persona <name>[/yellow]       Switch active persona (dark_comedian, existentialist, first_principles, ted_mosby, homelander)
   [yellow]/intensity <0.1-1.0>[/yellow]  Set persona intensity
   [yellow]/fusion <p1=0.6 p2=0.4>[/yellow] Mix personalities with custom weights
   [yellow]/memories[/yellow]             Inspect stored user memories
   [yellow]/status[/yellow]               Show active personality settings & device state
   [yellow]/exit[/yellow]                 Quit CLI
"""
    console.print(Panel(banner_text, border_style="magenta", expand=False))


def check_backend():
    try:
        resp = httpx.get(f"{API_BASE}/health", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            console.print(f"[green]✓ Connected to Figgy Backend (v{data.get('version')})[/green]")
            llm_info = data.get("llm_status", {})
            provider = data.get("llm_provider", "unknown")
            console.print(f"[dim]LLM Provider: {provider} | Status: {llm_info.get('status')}[/dim]\n")
            return True
        console.print("[red]✗ Backend returned non-200 status[/red]")
        return False
    except Exception as e:
        console.print(f"[red]✗ Could not connect to Figgy backend at {API_BASE}[/red]")
        console.print("[yellow]Make sure the backend is running: `uvicorn app.main:app --port 8000`[/yellow]\n")
        return False


def switch_persona(persona_name: str):
    try:
        resp = httpx.post(
            f"{API_BASE}/v1/persona",
            json={"mode": "single", "persona": persona_name},
            timeout=5.0
        )
        if resp.status_code == 200:
            data = resp.json()
            console.print(f"[bold green]Switched to {data.get('name')}![/bold green] (LED: {data.get('device_command', {}).get('parameters', {}).get('color')})")
        else:
            console.print(f"[red]Error: {resp.text}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to switch persona: {e}[/red]")


def set_intensity(val: float):
    try:
        # Get current persona
        p_resp = httpx.get(f"{API_BASE}/v1/persona", timeout=5.0).json()
        current = p_resp.get("active_persona") or "dark_comedian"
        resp = httpx.post(
            f"{API_BASE}/v1/persona",
            json={"mode": "single", "persona": current, "intensity": val},
            timeout=5.0
        )
        if resp.status_code == 200:
            console.print(f"[bold green]Intensity set to {val:.2f}[/bold green]")
        else:
            console.print(f"[red]Error: {resp.text}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to set intensity: {e}[/red]")


def set_fusion(arg: str):
    try:
        # Format: dark_comedian=0.6 existentialist=0.4
        weights = {}
        for part in arg.split():
            if "=" in part:
                k, v = part.split("=", 1)
                weights[k.strip()] = float(v.strip())

        if not weights:
            console.print("[yellow]Usage: /fusion dark_comedian=0.7 existentialist=0.3[/yellow]")
            return

        resp = httpx.post(
            f"{API_BASE}/v1/persona",
            json={"mode": "fusion", "fusion_weights": weights},
            timeout=5.0
        )
        if resp.status_code == 200:
            console.print(f"[bold green]Fusion mode active! Weights: {weights}[/bold green]")
        else:
            console.print(f"[red]Error: {resp.text}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to configure fusion: {e}[/red]")


def list_memories():
    try:
        resp = httpx.get(f"{API_BASE}/v1/memory", timeout=5.0)
        if resp.status_code == 200:
            memories = resp.json()
            if not memories:
                console.print("[dim]No persistent memories stored yet.[/dim]")
                return
            console.print(Panel("[bold]Stored Memories in SQLite:[/bold]", border_style="blue"))
            for m in memories:
                console.print(f" • [cyan]({m['category']})[/cyan] [bold]{m['key']}[/bold]: {m['content']}")
            console.print("")
        else:
            console.print(f"[red]Error: {resp.text}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to retrieve memories: {e}[/red]")


def stream_chat(user_msg: str):
    url = f"{API_BASE}/v1/chat/stream"
    payload = {
        "message": user_msg,
        "conversation_id": CONVERSATION_ID,
        "device_id": "cli-user"
    }

    console.print("[bold magenta]Figgy:[/bold magenta] ", end="")
    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    console.print(f"\n[red]Server returned {response.status_code}: {response.read().decode()}[/red]")
                    return

                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        try:
                            data = json.loads(data_str)
                            if "token" in data:
                                console.print(data["token"], end="")
                                sys.stdout.flush()
                            elif data.get("done"):
                                break
                            elif "error" in data:
                                console.print(f"\n[red]{data['error']}[/red]")
                                break
                        except Exception:
                            continue
        console.print("\n")
    except Exception as e:
        console.print(f"\n[red]Stream failed: {e}[/red]\n")


def main():
    print_banner()
    check_backend()

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/bold green]").strip()
            if not user_input:
                continue

            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                console.print("[magenta]Figgy: Leaving so soon? Try not to make any boring choices.[/magenta]")
                break

            if user_input.startswith("/persona "):
                name = user_input.split(" ", 1)[1].strip()
                switch_persona(name)
                continue

            if user_input.startswith("/intensity "):
                val = float(user_input.split(" ", 1)[1].strip())
                set_intensity(val)
                continue

            if user_input.startswith("/fusion "):
                arg = user_input.split(" ", 1)[1].strip()
                set_fusion(arg)
                continue

            if user_input in ("/memories", "/memory", "/m"):
                list_memories()
                continue

            if user_input in ("/status", "/s"):
                p_resp = httpx.get(f"{API_BASE}/v1/persona").json()
                console.print(Panel(json.dumps(p_resp, indent=2), title="Active Settings"))
                continue

            if user_input in ("/help", "/h"):
                print_banner()
                continue

            # Standard chat turn with streaming
            stream_chat(user_input)

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
