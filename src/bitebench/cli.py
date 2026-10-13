"""Unified command entry point."""

import json as json_module

import typer

from bitebench.environment import doctor

app = typer.Typer(help="BITE-Bench: auditable research tools.")
env_app = typer.Typer(help="Environment diagnostics.")
app.add_typer(env_app, name="env")


@env_app.command("doctor")
def env_doctor(json: bool = typer.Option(False, "--json")) -> None:
    report = doctor()
    if json:
        typer.echo(json_module.dumps(report, indent=2))
    else:
        for name, value in report.items():
            typer.echo(f"{name}: {value}")


data_app = typer.Typer(help="Food data validation.")
app.add_typer(data_app, name="data")


@data_app.command("validate")
def validate_foods(
    input: str = typer.Option(..., "--input"), allow_synthetic: bool = False
) -> None:
    from pathlib import Path

    from bitebench.core.validation import load_foods

    try:
        foods = load_foods(Path(input), allow_synthetic)
    except (ValueError, OSError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        json_module.dumps(
            {
                "status": "PASS",
                "rows": len(foods),
                "synthetic_rows": sum(f.is_synthetic for f in foods.values()),
            }
        )
    )
