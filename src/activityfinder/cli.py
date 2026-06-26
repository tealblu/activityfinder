from dotenv import load_dotenv
import typer
from datetime import datetime
from typing import Optional
from activityfinder.db import Database
from activityfinder.foursquare import FoursquareClient
from activityfinder.geocells import generate_geogrid
from activityfinder.indexer import Indexer
from activityfinder.models import Activity, ActivityCategory, SearchCriteria
from activityfinder.recommender import Recommender

load_dotenv()

_indexer: Indexer | None = None
_recommender: Recommender | None = None


def _get_indexer() -> Indexer:
    assert _indexer is not None
    return _indexer


def _get_recommender() -> Recommender:
    assert _recommender is not None
    return _recommender


main = typer.Typer()


@main.callback()
def _main(
    db: str = typer.Option("activityfinder.db", "--db", envvar="ACTIVITYFINDER_DB", show_default=True, help="SQLite database path"),
) -> None:
    """Activity Finder — index and discover local activities."""
    global _indexer, _recommender
    dbase = Database(db)
    _indexer = Indexer(db=dbase)
    _recommender = Recommender(_indexer)


@main.command()
def add(
    title: str = typer.Option(..., "--title", "-t", help="Activity title"),
    description: str = typer.Option(..., "--description", "-d", help="Activity description"),
    category: ActivityCategory = typer.Option(ActivityCategory.OTHER, "--category", "-c", help="Activity category"),
    location: str = typer.Option(..., "--location", "-l", help="Where it takes place"),
    cost: float = typer.Option(0.0, "--cost", "-m", help="Cost in dollars"),
    tags: Optional[list[str]] = typer.Option(None, "--tags", "-g", help="Searchable tags"),
    source: str = typer.Option("", "--source", help="Source of the listing"),
    url: str = typer.Option("", "--url", help="URL for more info"),
    start_time: str = typer.Option("", "--start-time", help="ISO format start time (default: now)"),
) -> None:
    """Index a new activity."""
    st = datetime.fromisoformat(start_time) if start_time else datetime.now()
    activity = Activity(
        title=title,
        description=description,
        category=category,
        location=location,
        cost=cost,
        tags=tags or [],
        source=source,
        url=url,
        start_time=st,
    )
    _get_indexer().index(activity)
    typer.echo(f"Indexed: {title}")


@main.command()
def search(
    query: str = typer.Option("", "--query", "-q", help="Free-text search"),
    category: Optional[list[str]] = typer.Option(None, "--category", "-c", help="Filter by category (can be used multiple times)"),
    max_cost: Optional[float] = typer.Option(None, "--max-cost", "-m", help="Maximum cost"),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Location filter"),
    tag: Optional[list[str]] = typer.Option(None, "--tag", "-g", help="Required tags"),
) -> None:
    """Search indexed activities."""
    criteria = SearchCriteria(
        query=query,
        categories=[ActivityCategory(c) for c in category] if category else [],
        max_cost=max_cost,
        location=location,
        tags=list(tag) if tag else [],
    )
    results = _get_recommender().search(criteria)
    if not results:
        typer.echo("No activities found.")
        return
    for a in results:
        cost_str = f"${a.cost:.2f}" if a.cost else "Free"
        typer.echo(f"{a.title} ({a.category.value}) — {cost_str}")
        typer.echo(f"  {a.description}")
        typer.echo(f"  {a.location}")
        if a.tags:
            typer.echo(f"  tags: {', '.join(a.tags)}")
        typer.echo()
    typer.echo(f"Found {len(results)} activity/activities.")


@main.command("list")
def list_activities() -> None:
    """List all indexed activities."""
    activities = _get_indexer().all()
    if not activities:
        typer.echo("No activities indexed.")
        return
    for a in activities:
        cost_str = f"${a.cost:.2f}" if a.cost else "Free"
        typer.echo(f"{a.title} ({a.category.value}) — {cost_str}")
    typer.echo(f"\nTotal: {len(activities)}")


@main.command()
def geogrid(
    location: str = typer.Argument(help="Location name"),
    precision: Optional[int] = typer.Option(None, "--precision", "-p", help="Geohash precision (auto if omitted)"),
    radius: Optional[float] = typer.Option(None, "--radius", "-r", help="Radius in km (auto if omitted)"),
) -> None:
    """Generate a geohash grid for LOCATION."""
    grid = generate_geogrid(location, precision=precision, radius_km=radius)
    typer.echo(f"Location: {grid.location}")
    typer.echo(f"Center:   {grid.latitude:.4f}, {grid.longitude:.4f}")
    if grid.cells:
        p = grid.cells[0].precision
        typer.echo(f"Precision: {p}{' (auto)' if precision is None else ''}")
    typer.echo(f"Cells:    {len(grid.cells)}")
    for c in grid.cells:
        typer.echo(f"  {c.geohash}  ({c.latitude:.4f}, {c.longitude:.4f})")


@main.command(name="foursquare-search")
def foursquare_search(
    location: str = typer.Argument(help="Location to search around (e.g. 'San Francisco')"),
    query: str = typer.Option("", "--query", "-q", help="Search term (e.g. 'coffee', 'museum')"),
    radius: int = typer.Option(1000, "--radius", "-r", help="Search radius in meters", show_default=True),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results (max 50)", show_default=True),
    category: Optional[list[str]] = typer.Option(None, "--category", "-c", help="Foursquare category ID filter (repeatable)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Search only; do not index results"),
) -> None:
    """Search Foursquare Places API and index results."""
    cat_str = ",".join(category) if category else None

    if dry_run:
        with FoursquareClient() as client:
            results = client.search_by_location(
                location=location,
                query=query,
                radius_m=radius,
                limit=limit,
                category_ids=cat_str,
            )
    else:
        results = _get_indexer().foursquare_search_and_index(
            location=location,
            query=query,
            radius_m=radius,
            limit=limit,
            category_ids=cat_str,
        )

    if not results:
        typer.echo("No places found on Foursquare.")
        return

    if not dry_run:
        typer.echo(f"Indexed {len(results)} place(s).\n")

    for a in results:
        cost_str = f"${a.cost:.2f}" if a.cost else "Free"
        typer.echo(f"{a.title} ({a.category.value}) — {cost_str}")
        typer.echo(f"  {a.description}")
        typer.echo(f"  {a.location}")
        if a.tags:
            typer.echo(f"  tags: {', '.join(a.tags)}")
        if a.url:
            typer.echo(f"  {a.url}")
        typer.echo()
    typer.echo(f"Found {len(results)} place(s).")
