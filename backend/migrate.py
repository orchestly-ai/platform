#!/usr/bin/env python3
"""
Database Migration CLI

Simple CLI for managing database migrations with Alembic.
"""

import asyncio
import sys
from pathlib import Path

import typer
from alembic import command
from alembic.config import Config

from backend.database.session import init_db, close_db, engine
from backend.shared.config import get_settings

app = typer.Typer(help="Database migration management")


def get_alembic_config() -> Config:
    """Get Alembic configuration."""
    # Path to alembic.ini
    ini_path = Path(__file__).parent / "alembic.ini"

    config = Config(str(ini_path))

    # Override database URL from settings
    settings = get_settings()
    database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    config.set_main_option("sqlalchemy.url", database_url)

    return config


@app.command()
def upgrade(revision: str = "head"):
    """
    Upgrade database to a later version.

    Args:
        revision: Target revision (default: head)
    """
    typer.echo(f"🔄 Upgrading database to {revision}...")

    config = get_alembic_config()
    command.upgrade(config, revision)

    typer.echo(f"✅ Database upgraded to {revision}")


@app.command()
def downgrade(revision: str = "-1"):
    """
    Downgrade database to a previous version.

    Args:
        revision: Target revision (default: -1 for one step back)
    """
    typer.echo(f"🔄 Downgrading database to {revision}...")

    config = get_alembic_config()
    command.downgrade(config, revision)

    typer.echo(f"✅ Database downgraded to {revision}")


@app.command()
def current():
    """Show current database revision."""
    typer.echo("📍 Current database revision:")

    config = get_alembic_config()
    command.current(config, verbose=True)


@app.command()
def history():
    """Show migration history."""
    typer.echo("📜 Migration history:")

    config = get_alembic_config()
    command.history(config, verbose=True)


@app.command()
def create(message: str):
    """
    Create a new migration.

    Args:
        message: Migration description
    """
    typer.echo(f"📝 Creating new migration: {message}")

    config = get_alembic_config()
    command.revision(config, message=message, autogenerate=True)

    typer.echo("✅ Migration created")


@app.command()
def init():
    """Initialize database (create all tables without migrations)."""
    typer.echo("🚀 Initializing database...")

    async def _init():
        await init_db()
        typer.echo("✅ Database initialized")

    asyncio.run(_init())


@app.command()
def reset():
    """Reset database (drop all tables and recreate)."""
    confirm = typer.confirm("⚠️  This will DELETE ALL DATA! Continue?")

    if not confirm:
        typer.echo("❌ Aborted")
        return

    typer.echo("🔄 Resetting database...")

    async def _reset():
        from backend.database.session import Base

        # Drop all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            typer.echo("   Dropped all tables")

        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            typer.echo("   Created all tables")

        typer.echo("✅ Database reset complete")

    asyncio.run(_reset())


@app.command()
def stamp(revision: str = "head"):
    """
    Stamp database with a specific revision (without running migrations).

    Useful when initializing an existing database.

    Args:
        revision: Target revision (default: head)
    """
    typer.echo(f"🏷️  Stamping database with revision {revision}...")

    config = get_alembic_config()
    command.stamp(config, revision)

    typer.echo(f"✅ Database stamped with {revision}")


@app.command()
def check():
    """Check if database is up to date."""
    typer.echo("🔍 Checking database status...")

    config = get_alembic_config()

    # Get current revision
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    settings = get_settings()
    sync_url = settings.DATABASE_URL

    # Create sync engine for Alembic
    sync_engine = create_engine(sync_url)

    script = ScriptDirectory.from_config(config)
    with sync_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_rev = context.get_current_revision()

    head_rev = script.get_current_head()

    if current_rev == head_rev:
        typer.echo(f"✅ Database is up to date (revision: {current_rev})")
    else:
        typer.echo(f"⚠️  Database needs migration:")
        typer.echo(f"   Current: {current_rev or 'None'}")
        typer.echo(f"   Latest:  {head_rev}")
        typer.echo(f"\n   Run: python migrate.py upgrade")
        sys.exit(1)


if __name__ == "__main__":
    app()
