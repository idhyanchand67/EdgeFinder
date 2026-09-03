"""Renders hit-rate results into a single self-contained report.html."""
import json
import math

from . import config


def _clean(value):
    """NaN/NaT don't survive json.dumps as valid JSON - normalize to None."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def render(results: list[dict], meta: dict, log_df=None) -> None:
    template = config.TEMPLATE_HTML.read_text(encoding="utf-8")
    data_json = json.dumps(results)
    meta_json = json.dumps(meta)

    if log_df is not None and len(log_df):
        recent_log = log_df.sort_values("logged_at", ascending=False).head(50)
        log_records = [{k: _clean(v) for k, v in row.items()} for row in recent_log.to_dict("records")]
    else:
        log_records = []
    log_json = json.dumps(log_records)

    html = template.replace(
        "/*PROP_DATA_JSON*/[]/*PROP_DATA_JSON*/", f"/*PROP_DATA_JSON*/{data_json}/*PROP_DATA_JSON*/"
    ).replace(
        "/*META_JSON*/{}/*META_JSON*/", f"/*META_JSON*/{meta_json}/*META_JSON*/"
    ).replace(
        "/*PICK_LOG_JSON*/[]/*PICK_LOG_JSON*/", f"/*PICK_LOG_JSON*/{log_json}/*PICK_LOG_JSON*/"
    )

    config.REPORT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {config.REPORT_HTML} ({len(results)} props across {len(meta.get('sports', []))} sport(s))")
