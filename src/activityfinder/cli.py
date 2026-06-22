import click

from datetime import datetime

from activityfinder.indexer import Indexer
from activityfinder.models import Activity, ActivityCategory, SearchCriteria
from activityfinder.recommender import Recommender


_indexer = Indexer()
_recommender = Recommender(_indexer)


@click.group()
def main() -> None:
    """Activity Finder — index and discover local activities."""


@main.command()
@click.option("--title", "-t", required=True, help="Activity title")
@click.option("--description", "-d", required=True, help="Activity description")
@click.option(
    "--category",
    "-c",
    type=click.Choice([c.value for c in ActivityCategory]),
    default=ActivityCategory.OTHER.value,
    show_default=True,
    help="Activity category",
)
@click.option("--location", "-l", required=True, help="Where it takes place")
@click.option("--cost", "-m", type=float, default=0.0, help="Cost in dollars")
@click.option("--tags", "-g", multiple=True, help="Searchable tags")
@click.option("--source", default="", help="Source of the listing")
@click.option("--url", default="", help="URL for more info")
@click.option("--start-time", default="", help="ISO format start time (default: now)")
def add(
    title: str,
    description: str,
    category: str,
    location: str,
    cost: float,
    tags: tuple[str, ...],
    source: str,
    url: str,
    start_time: str,
) -> None:
    """Index a new activity."""
    st = datetime.fromisoformat(start_time) if start_time else datetime.now()
    activity = Activity(
        title=title,
        description=description,
        category=ActivityCategory(category),
        location=location,
        cost=cost,
        tags=list(tags),
        source=source,
        url=url,
        start_time=st,
    )
    _indexer.index(activity)
    click.echo(f"Indexed: {title}")


@main.command()
@click.option("--query", "-q", default="", help="Free-text search")
@click.option(
    "--category",
    "-c",
    multiple=True,
    help="Filter by category (can be used multiple times)",
)
@click.option("--max-cost", "-m", type=float, help="Maximum cost")
@click.option("--location", "-l", help="Location filter")
@click.option("--tag", "-g", multiple=True, help="Required tags")
def search(
    query: str,
    category: tuple[str, ...],
    max_cost: float | None,
    location: str | None,
    tag: tuple[str, ...],
) -> None:
    """Search indexed activities."""
    criteria = SearchCriteria(
        query=query,
        categories=[ActivityCategory(c) for c in category] if category else [],
        max_cost=max_cost,
        location=location,
        tags=list(tag),
    )
    results = _recommender.search(criteria)
    if not results:
        click.echo("No activities found.")
        return
    for a in results:
        cost_str = f"${a.cost:.2f}" if a.cost else "Free"
        click.echo(f"{a.title} ({a.category.value}) — {cost_str}")
        click.echo(f"  {a.description}")
        click.echo(f"  {a.location}")
        if a.tags:
            click.echo(f"  tags: {', '.join(a.tags)}")
        click.echo()
    click.echo(f"Found {len(results)} activity/activities.")


@main.command(name="list")
def list_activities() -> None:
    """List all indexed activities."""
    activities = _indexer.all()
    if not activities:
        click.echo("No activities indexed.")
        return
    for a in activities:
        cost_str = f"${a.cost:.2f}" if a.cost else "Free"
        click.echo(f"{a.title} ({a.category.value}) — {cost_str}")
    click.echo(f"\nTotal: {len(activities)}")
