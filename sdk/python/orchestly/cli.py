"""
Orchestly CLI

Usage:
    orchestly serve       Start the Orchestly platform (backend API server)
    orchestly init NAME   Initialize a new Orchestly project
    orchestly version     Show version
"""

import os
import sys
import typer

app = typer.Typer(
    name="orchestly",
    help="Orchestly — open-source AI agent orchestration platform",
    add_completion=False,
)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
    workers: int = typer.Option(1, help="Number of worker processes"),
):
    """Start the Orchestly API server."""
    try:
        import uvicorn
    except ImportError:
        typer.echo("Error: uvicorn is required. Install with: pip install orchestly[server]")
        raise typer.Exit(1)

    typer.echo(f"Starting Orchestly on {host}:{port}...")
    typer.echo(f"  Dashboard: http://localhost:{port}")
    typer.echo(f"  API docs:  http://localhost:{port}/docs")
    typer.echo("")

    uvicorn.run(
        "backend.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )


@app.command()
def init(
    name: str = typer.Argument(..., help="Project name"),
):
    """Initialize a new Orchestly project with boilerplate files."""
    project_dir = os.path.join(os.getcwd(), name)

    if os.path.exists(project_dir):
        typer.echo(f"Error: directory '{name}' already exists.")
        raise typer.Exit(1)

    os.makedirs(project_dir)
    os.makedirs(os.path.join(project_dir, "agents"))

    # Create a minimal agent file
    agent_code = '''"""Example Orchestly agent."""

from orchestly import register_agent, task


@register_agent(
    name="hello_agent",
    capabilities=["greeting"],
)
class HelloAgent:

    @task(timeout=30)
    async def greeting(self, data: dict) -> dict:
        name = data.get("name", "World")
        return {"message": f"Hello, {name}!"}
'''

    with open(os.path.join(project_dir, "agents", "hello_agent.py"), "w") as f:
        f.write(agent_code)

    # Create .env.example
    env_example = """# Orchestly Configuration
ORCHESTLY_API_URL=http://localhost:8000
ORCHESTLY_API_KEY=

# LLM Provider Keys (add the ones you use)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
"""

    with open(os.path.join(project_dir, ".env.example"), "w") as f:
        f.write(env_example)

    typer.echo(f"Created new Orchestly project: {name}/")
    typer.echo(f"  agents/hello_agent.py  - Example agent")
    typer.echo(f"  .env.example           - Environment template")
    typer.echo("")
    typer.echo("Next steps:")
    typer.echo(f"  cd {name}")
    typer.echo(f"  cp .env.example .env   # Add your API keys")
    typer.echo(f"  orchestly serve        # Start the platform")


@app.command()
def version():
    """Show Orchestly version."""
    from orchestly import __version__
    typer.echo(f"orchestly {__version__}")


if __name__ == "__main__":
    app()
