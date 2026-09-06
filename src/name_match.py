"""Normalizes player names so odds-book spellings match nflverse's."""
import re

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = name.lower().strip()
    name = name.replace(".", "").replace("'", "")
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    parts = [p for p in name.split() if p not in _SUFFIXES]
    return " ".join(parts)


def build_name_index(stats_df):
    """Maps normalized player name -> list of distinct player_ids in stats_df."""
    index = {}
    for player_id, name in stats_df[["player_id", "player_display_name"]].drop_duplicates().itertuples(index=False):
        key = normalize_name(name)
        index.setdefault(key, set()).add(player_id)
    return index


def resolve_player_id(name: str, teams, name_index: dict, stats_df) -> str | None:
    """Best-effort match: exact normalized name, tie-broken by team if ambiguous.
    `teams` is the set of stats-abbreviations eligible for this prop (normally
    the game's home and away team, since a name collision could be either
    player) - a single string is also accepted for a one-team hint."""
    key = normalize_name(name)
    candidates = name_index.get(key)
    if not candidates:
        return None
    if len(candidates) == 1:
        return next(iter(candidates))
    if teams:
        teams_norm = {teams.strip().upper()} if isinstance(teams, str) else {t.strip().upper() for t in teams if t}
        for pid in candidates:
            rows = stats_df[stats_df["player_id"] == pid]
            if not rows.empty and str(rows["team"].iloc[-1]).strip().upper() in teams_norm:
                return pid
    return next(iter(candidates))
