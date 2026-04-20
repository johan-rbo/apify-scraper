import csv
from rich.console import Console
from rich.table import Table
from rich import box

def run(output_file: str = "output.csv"):
    console = Console()

    with open(output_file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        flagged = bool(row["notes"])
        color = "yellow" if flagged else "green"
        status = row["notes"] if flagged else "✓ Match"

        console.rule(f"[bold {color}]{row['name']}[/] — {row['site_page']} · {row['position']}")

        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column(style="bold dim", width=14)
        table.add_column()

        table.add_row("Status", f"[{color}]{status}[/]")
        table.add_row("LinkedIn", row["linkedin_url"] or "[dim]Not found[/]")
        table.add_row("Law School", row["law_school"] or "[dim]—[/]")
        table.add_row("JD Year", row["jd_year"] or "[dim]—[/]")
        table.add_row("Work History", row["formatted_work_history"] or "[dim]—[/]")

        console.print(table)
        console.print()


if __name__ == "__main__":
    run()
