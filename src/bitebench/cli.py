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
    input: str = typer.Option(..., "--input"),
    allow_synthetic: bool = False,
    strict: bool = False,
    ledger: str = "data/reviews/food_review_ledger.csv",
) -> None:
    from pathlib import Path

    from bitebench.core.validation import load_foods

    if strict:
        from bitebench.data.curation import data_report

        report = data_report(Path(input), Path(ledger))
        typer.echo(json_module.dumps(report, ensure_ascii=False))
        if report["status"] != "PASS":
            raise typer.Exit(2)
        return
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


@data_app.command("usda-search")
def usda_search(
    query: str = typer.Option(...), limit: int = 5, demo: bool = False
) -> None:
    from bitebench.data.usda_client import SourceError, USDAClient, configured_key

    try:
        with USDAClient("DEMO_KEY" if demo else configured_key()) as client:
            payload = client.search(query, limit)
        typer.echo(json_module.dumps(payload, ensure_ascii=False))
    except SourceError as error:
        typer.echo(
            json_module.dumps(
                {
                    "status": "BLOCKED",
                    "reason_code": error.reason_code,
                    "http_status": error.status_code,
                }
            )
        )
        raise typer.Exit(2) from error


@data_app.command("usda-fetch")
def usda_fetch(
    fdc_id: int = typer.Option(...), out: str = "data/raw/usda", demo: bool = False
) -> None:
    from pathlib import Path

    from bitebench.data.usda_client import SourceError, USDAClient, configured_key

    try:
        with USDAClient("DEMO_KEY" if demo else configured_key(), Path(out)) as client:
            payload = client.fetch(fdc_id)
        typer.echo(json_module.dumps(payload, ensure_ascii=False))
    except SourceError as error:
        typer.echo(
            json_module.dumps(
                {
                    "status": "BLOCKED",
                    "reason_code": error.reason_code,
                    "http_status": error.status_code,
                }
            )
        )
        raise typer.Exit(2) from error


@data_app.command("report")
def report_food_data(
    input: str = typer.Option(...),
    out: str = "outputs/reports/food_data_quality.json",
    ledger: str = "data/reviews/food_review_ledger.csv",
) -> None:
    from pathlib import Path

    from bitebench.data.curation import data_report

    report = data_report(Path(input), Path(ledger))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json_module.dumps(report, ensure_ascii=False, indent=2) + "\n")
    typer.echo(json_module.dumps(report, ensure_ascii=False))


review_app = typer.Typer(help="Food source review queues and receipt auditing.")
app.add_typer(review_app, name="review")


@review_app.command("prepare")
def prepare_review(
    manifest: str = "data/curated/food_candidate_manifest.csv",
    out: str = "data/reviews",
    demo: bool = False,
    network_budget: int | None = None,
    food_id: str | None = None,
) -> None:
    from pathlib import Path

    from bitebench.data.curation import prepare
    from bitebench.data.usda_client import USDAClient, configured_key

    key = "DEMO_KEY" if demo else configured_key()
    is_demo = key == "DEMO_KEY"
    network_budget = (
        (2 if is_demo else 96) if network_budget is None else network_budget
    )
    if network_budget < 0 or (is_demo and network_budget > 4):
        raise typer.BadParameter(
            "network budget must be nonnegative; demo smoke is limited to four requests"
        )
    with USDAClient(key) as client:
        report = prepare(
            Path(manifest),
            Path(out),
            client,
            network_budget,
            {food_id} if food_id else None,
        )
    typer.echo(json_module.dumps(report, ensure_ascii=False))


@review_app.command("queue")
def human_queue(
    out: str = "docs/HUMAN_ACTIONS.md",
    queue: str = "data/reviews/human_action_queue.jsonl",
    only_actionable: bool = True,
) -> None:
    from pathlib import Path

    from bitebench.data.curation import write_human_queue

    write_human_queue(Path(queue), Path(out), only_actionable)
    typer.echo(f"Wrote pending actions to {out}")


@review_app.command("audit")
def audit_review(
    ledger: str = "data/reviews/food_review_ledger.csv",
    food_data: str = "data/curated/foodbench48.csv",
    strict: bool = False,
) -> None:
    from pathlib import Path

    from bitebench.data.curation import data_report

    report = data_report(Path(food_data), Path(ledger))
    typer.echo(json_module.dumps(report, ensure_ascii=False))
    if strict and report["status"] != "PASS":
        raise typer.Exit(2)


menu_app = typer.Typer(help="Reviewed daily menu validation.")
app.add_typer(menu_app, name="menu")


@menu_app.command("validate")
def validate_menus(
    input: str = typer.Option(...),
    food_data: str = "data/curated/foodbench48.csv",
    ledger: str = "data/reviews/food_review_ledger.csv",
) -> None:
    from pathlib import Path

    from bitebench.data.menus import menu_report

    report = menu_report(Path(input), Path(food_data), Path(ledger))
    typer.echo(json_module.dumps(report, ensure_ascii=False))
    if report["status"] != "PASS":
        raise typer.Exit(2)


@review_app.command("view")
def review_view(
    cards: str = "data/reviews/review_cards.json",
    out: str = "outputs/reports/food_review.html",
) -> None:
    from pathlib import Path

    from bitebench.data.review_ui import render_review_cards

    render_review_cards(Path(cards), Path(out))
    typer.echo(f"Wrote offline human review cards to {out}; no approvals recorded.")
