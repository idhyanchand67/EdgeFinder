"""Renders hit-rate results into a single self-contained report.html."""
import json
from datetime import datetime, timezone

from . import config


def render(results: list[dict], stats_df, lookback: int, min_games: int) -> None:
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "lookback": lookback,
        "min_games": min_games,
        "stats_rows": int(len(stats_df)),
        "seasons": sorted(int(s) for s in stats_df["season"].unique()),
    }

    template = config.TEMPLATE_HTML.read_text(encoding="utf-8")
    data_json = json.dumps(results)
    meta_json = json.dumps(meta)

    html = template.replace(
        "/*PROP_DATA_JSON*/[]/*PROP_DATA_JSON*/", f"/*PROP_DATA_JSON*/{data_json}/*PROP_DATA_JSON*/"
    ).replace(
        "/*META_JSON*/{}/*META_JSON*/", f"/*META_JSON*/{meta_json}/*META_JSON*/"
    )

    config.REPORT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {config.REPORT_HTML} ({len(results)} props)")
