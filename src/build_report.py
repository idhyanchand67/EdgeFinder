"""Renders hit-rate results into a single self-contained report.html."""
import json

from . import config


def render(results: list[dict], meta: dict) -> None:
    template = config.TEMPLATE_HTML.read_text(encoding="utf-8")
    data_json = json.dumps(results)
    meta_json = json.dumps(meta)

    html = template.replace(
        "/*PROP_DATA_JSON*/[]/*PROP_DATA_JSON*/", f"/*PROP_DATA_JSON*/{data_json}/*PROP_DATA_JSON*/"
    ).replace(
        "/*META_JSON*/{}/*META_JSON*/", f"/*META_JSON*/{meta_json}/*META_JSON*/"
    )

    config.REPORT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {config.REPORT_HTML} ({len(results)} props across {len(meta.get('sports', []))} sport(s))")
