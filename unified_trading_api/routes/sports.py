"""Sports fixture REST endpoints for initial page load.

GET /api/sports/fixtures — today's fixtures with status, scores, odds
GET /api/sports/fixtures/{fixture_id} — single fixture detail
GET /api/sports/leagues — active leagues with fixture counts

Mock mode: returns generated data from SPORTS_INSTRUMENT_SPECS.
Real mode: reads from GCS instruments + tick data buckets.
"""

from __future__ import annotations

import logging
import random
import time

from fastapi import APIRouter, Query, Request
from unified_api_contracts.registry.representative_sample import (  # noqa: qg-deep-import — UAC internal facade
    SPORTS_INSTRUMENT_SPECS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sports", tags=["sports"])

# Mock fixture data generated from SPORTS_INSTRUMENT_SPECS
_MOCK_LEAGUES = [
    {
        "league_id": "EPL",
        "name": "English Premier League",
        "country": "England",
        "fixture_count": 10,
    },
    {"league_id": "LA_LIGA", "name": "La Liga", "country": "Spain", "fixture_count": 10},
    {"league_id": "BUNDESLIGA", "name": "Bundesliga", "country": "Germany", "fixture_count": 9},
    {"league_id": "SERIE_A", "name": "Serie A", "country": "Italy", "fixture_count": 10},
    {"league_id": "LIGUE_1", "name": "Ligue 1", "country": "France", "fixture_count": 10},
]

_MOCK_FIXTURES: list[dict[str, object]] = []


def _ensure_mock_fixtures() -> list[dict[str, object]]:
    """Lazily generate mock fixtures from SPORTS_INSTRUMENT_SPECS."""
    if _MOCK_FIXTURES:
        return _MOCK_FIXTURES

    statuses = ["NS", "1H", "HT", "2H", "FT"]
    teams = [
        ("Arsenal", "ARS"),
        ("Chelsea", "CHE"),
        ("Man City", "MCI"),
        ("Liverpool", "LIV"),
        ("Barcelona", "BAR"),
        ("Real Madrid", "RMA"),
        ("Bayern Munich", "BAY"),
        ("Dortmund", "DOR"),
        ("AC Milan", "MIL"),
        ("Juventus", "JUV"),
        ("PSG", "PSG"),
        ("Lyon", "LYO"),
        ("Man United", "MUN"),
        ("Tottenham", "TOT"),
        ("Newcastle", "NEW"),
        ("Aston Villa", "AVL"),
    ]
    leagues = ["EPL", "LA_LIGA", "BUNDESLIGA", "SERIE_A", "LIGUE_1"]

    for i, spec in enumerate(SPORTS_INSTRUMENT_SPECS):
        sym = str(spec.get("symbol", spec.get("event_id", f"fixture-{i}")))
        home_idx = (i * 2) % len(teams)
        away_idx = (i * 2 + 1) % len(teams)
        status = statuses[i % len(statuses)]
        minute = random.randint(1, 90) if status in ("1H", "2H") else (45 if status == "HT" else None)  # nosec B311

        fixture: dict[str, object] = {
            "fixture_id": f"SF-{1000 + i}",
            "canonical_key": sym,
            "league_id": leagues[i % len(leagues)],
            "status": status,
            "minute": minute,
            "kickoff": f"2026-04-15T{14 + (i % 8)}:00:00Z",
            "home_team": teams[home_idx][0],
            "home_short": teams[home_idx][1],
            "away_team": teams[away_idx][0],
            "away_short": teams[away_idx][1],
            "score": {
                "home": random.randint(0, 3) if status not in ("NS",) else 0,  # nosec B311
                "away": random.randint(0, 2) if status not in ("NS",) else 0,  # nosec B311
            },
            "odds": {
                "FT Result": {
                    "betfair_exchange": {
                        "home": round(1.5 + random.random() * 2, 2),  # nosec B311
                        "draw": round(2.8 + random.random() * 1.5, 2),  # nosec B311
                        "away": round(3.0 + random.random() * 3, 2),  # nosec B311
                    },
                    "pinnacle": {
                        "home": round(1.5 + random.random() * 2, 2),  # nosec B311
                        "draw": round(2.8 + random.random() * 1.5, 2),  # nosec B311
                        "away": round(3.0 + random.random() * 3, 2),  # nosec B311
                    },
                },
            },
            "stats": {
                "home": {"possession": 50, "shots": 0, "shots_on_target": 0, "corners": 0},
                "away": {"possession": 50, "shots": 0, "shots_on_target": 0, "corners": 0},
            },
            "venue": str(spec.get("venue", "BETFAIR")),
        }
        _MOCK_FIXTURES.append(fixture)

    return _MOCK_FIXTURES


@router.get("/fixtures")
async def get_fixtures(
    request: Request,
    league: str = Query(None, description="Filter by league_id"),
    status: str = Query(None, description="Filter by status (NS, 1H, HT, 2H, FT)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """List today's fixtures with current status, scores, odds."""
    fixtures = _ensure_mock_fixtures()

    filtered = fixtures
    if league:
        filtered = [f for f in filtered if f.get("league_id") == league]
    if status:
        filtered = [f for f in filtered if f.get("status") == status]

    start = (page - 1) * page_size
    end = start + page_size
    page_data = filtered[start:end]

    return {
        "data": page_data,
        "meta": {
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
            "timestamp": time.time(),
        },
    }


@router.get("/fixtures/{fixture_id}")
async def get_fixture_detail(
    request: Request,
    fixture_id: str,
) -> dict[str, object]:
    """Get single fixture detail with full stats, events, lineups."""
    fixtures = _ensure_mock_fixtures()
    match = next((f for f in fixtures if f.get("fixture_id") == fixture_id), None)
    if not match:
        return {"error": "Fixture not found", "status": "not_found"}
    return {"data": match, "meta": {"timestamp": time.time()}}


@router.get("/fixtures/{fixture_id}/odds")
async def get_fixture_odds_history(
    request: Request,
    fixture_id: str,
) -> dict[str, object]:
    """Get odds history for a fixture across bookmakers (time series)."""
    # Mock: generate synthetic odds history
    history: list[dict[str, object]] = []
    base_home = 1.8
    base_draw = 3.2
    base_away = 4.5
    now = time.time()
    for i in range(20):
        ts = now - (20 - i) * 300  # every 5 minutes going back
        history.append(
            {
                "timestamp": ts,
                "bookmaker": "betfair_exchange",
                "home": round(base_home + random.gauss(0, 0.05), 2),  # nosec B311
                "draw": round(base_draw + random.gauss(0, 0.08), 2),  # nosec B311
                "away": round(base_away + random.gauss(0, 0.1), 2),  # nosec B311
            }
        )
    return {"data": history, "meta": {"fixture_id": fixture_id, "timestamp": now}}


@router.get("/leagues")
async def get_leagues(
    request: Request,
) -> dict[str, object]:
    """List active leagues with fixture counts."""
    return {"data": _MOCK_LEAGUES, "meta": {"timestamp": time.time()}}


_MOCK_STANDINGS: dict[str, list[dict[str, object]]] = {}


def _ensure_mock_standings() -> dict[str, list[dict[str, object]]]:
    if _MOCK_STANDINGS:
        return _MOCK_STANDINGS

    epl_teams = [
        ("Arsenal", 71, 23, 2, 3, 65, 22),
        ("Man City", 67, 20, 7, 1, 62, 25),
        ("Liverpool", 65, 20, 5, 3, 58, 21),
        ("Chelsea", 52, 15, 7, 6, 48, 35),
        ("Tottenham", 50, 15, 5, 8, 52, 38),
        ("Man United", 45, 13, 6, 9, 39, 32),
        ("Newcastle", 44, 13, 5, 10, 42, 35),
        ("Aston Villa", 43, 12, 7, 9, 40, 34),
        ("Brighton", 40, 11, 7, 10, 38, 37),
        ("West Ham", 38, 10, 8, 10, 35, 40),
    ]
    _MOCK_STANDINGS["EPL"] = [
        {
            "rank": i + 1,
            "team_name": t[0],
            "points": t[1],
            "played": t[2] + t[3] + t[4],
            "wins": t[2],
            "draws": t[3],
            "losses": t[4],
            "goals_for": t[5],
            "goals_against": t[6],
            "goals_diff": t[5] - t[6],
            "form": random.choice(["WWDWL", "WDWWW", "LWDWW", "WDLWW", "DLWWD"]),  # nosec B311
        }
        for i, t in enumerate(epl_teams)
    ]
    return _MOCK_STANDINGS


@router.get("/standings/{league_id}")
async def get_standings(
    request: Request,
    league_id: str,
) -> dict[str, object]:
    """Get league standings table."""
    standings = _ensure_mock_standings()
    league_standings = standings.get(league_id, [])
    return {"data": league_standings, "meta": {"league_id": league_id, "timestamp": time.time()}}


@router.get("/fixtures/{fixture_id}/predictions")
async def get_fixture_predictions(
    request: Request,
    fixture_id: str,
) -> dict[str, object]:
    """Get model predictions for a fixture."""
    fixtures = _ensure_mock_fixtures()
    match = next((f for f in fixtures if f.get("fixture_id") == fixture_id), None)
    if not match:
        return {"error": "Fixture not found", "status": "not_found"}

    prediction = {
        "fixture_id": fixture_id,
        "source": "unified-ml-v2",
        "home_win_prob": round(0.3 + random.random() * 0.3, 3),  # nosec B311
        "draw_prob": round(0.2 + random.random() * 0.15, 3),  # nosec B311
        "away_win_prob": round(0.2 + random.random() * 0.3, 3),  # nosec B311
        "btts_prob": round(0.4 + random.random() * 0.3, 3),  # nosec B311
        "over_25_prob": round(0.4 + random.random() * 0.25, 3),  # nosec B311
        "under_25_prob": round(0.3 + random.random() * 0.25, 3),  # nosec B311
        "xg_home": round(0.8 + random.random() * 1.2, 2),  # nosec B311
        "xg_away": round(0.6 + random.random() * 1.0, 2),  # nosec B311
        "model_version": "sports-v2.3.1",
        "confidence": round(0.6 + random.random() * 0.3, 3),  # nosec B311
    }
    return {"data": prediction, "meta": {"fixture_id": fixture_id, "timestamp": time.time()}}


@router.get("/fixtures/{fixture_id}/lineups")
async def get_fixture_lineups(
    request: Request,
    fixture_id: str,
) -> dict[str, object]:
    """Get confirmed lineups for a fixture."""
    mock_lineups = {
        "home": {
            "formation": "4-3-3",
            "players": [
                {"name": "Ederson", "number": 31, "position": "GK", "is_starter": True},
                {"name": "Walker", "number": 2, "position": "RB", "is_starter": True},
                {"name": "Dias", "number": 3, "position": "CB", "is_starter": True},
                {"name": "Akanji", "number": 25, "position": "CB", "is_starter": True},
                {"name": "Gvardiol", "number": 24, "position": "LB", "is_starter": True},
                {"name": "Rodri", "number": 16, "position": "CDM", "is_starter": True},
                {"name": "De Bruyne", "number": 17, "position": "CM", "is_starter": True},
                {"name": "Bernardo", "number": 20, "position": "CM", "is_starter": True},
                {"name": "Foden", "number": 47, "position": "RW", "is_starter": True},
                {"name": "Haaland", "number": 9, "position": "ST", "is_starter": True},
                {"name": "Doku", "number": 11, "position": "LW", "is_starter": True},
                {"name": "Ortega", "number": 18, "position": "GK", "is_starter": False},
                {"name": "Stones", "number": 5, "position": "CB", "is_starter": False},
                {"name": "Grealish", "number": 10, "position": "LW", "is_starter": False},
            ],
            "coach": "Pep Guardiola",
        },
        "away": {
            "formation": "4-3-3",
            "players": [
                {"name": "Alisson", "number": 1, "position": "GK", "is_starter": True},
                {"name": "Alexander-Arnold", "number": 66, "position": "RB", "is_starter": True},
                {"name": "Konate", "number": 5, "position": "CB", "is_starter": True},
                {"name": "Van Dijk", "number": 4, "position": "CB", "is_starter": True},
                {"name": "Robertson", "number": 26, "position": "LB", "is_starter": True},
                {"name": "Fabinho", "number": 3, "position": "CDM", "is_starter": True},
                {"name": "Thiago", "number": 6, "position": "CM", "is_starter": True},
                {"name": "Jones", "number": 17, "position": "CM", "is_starter": True},
                {"name": "Salah", "number": 11, "position": "RW", "is_starter": True},
                {"name": "Nunez", "number": 9, "position": "ST", "is_starter": True},
                {"name": "Diaz", "number": 7, "position": "LW", "is_starter": True},
                {"name": "Kelleher", "number": 62, "position": "GK", "is_starter": False},
                {"name": "Gomez", "number": 12, "position": "CB", "is_starter": False},
                {"name": "Jota", "number": 20, "position": "ST", "is_starter": False},
            ],
            "coach": "Arne Slot",
        },
    }
    return {"data": mock_lineups, "meta": {"fixture_id": fixture_id, "timestamp": time.time()}}


@router.get("/fixtures/{fixture_id}/results")
async def get_fixture_results(
    request: Request,
    fixture_id: str,
) -> dict[str, object]:
    """Get post-match results summary with predicted vs actual comparison."""
    fixtures = _ensure_mock_fixtures()
    match = next((f for f in fixtures if f.get("fixture_id") == fixture_id), None)
    if not match:
        return {"error": "Fixture not found", "status": "not_found"}

    score = match.get("score", {})
    home_goals = score.get("home", 0) if isinstance(score, dict) else 0
    away_goals = score.get("away", 0) if isinstance(score, dict) else 0
    total_goals = int(home_goals) + int(away_goals)
    result = "home" if int(home_goals) > int(away_goals) else ("away" if int(away_goals) > int(home_goals) else "draw")

    prediction = {
        "home_win_prob": round(0.3 + random.random() * 0.3, 3),  # nosec B311
        "draw_prob": round(0.2 + random.random() * 0.15, 3),  # nosec B311
        "away_win_prob": round(0.2 + random.random() * 0.3, 3),  # nosec B311
        "xg_home": round(0.8 + random.random() * 1.2, 2),  # nosec B311
        "xg_away": round(0.6 + random.random() * 1.0, 2),  # nosec B311
        "btts_prob": round(0.4 + random.random() * 0.3, 3),  # nosec B311
        "over_25_prob": round(0.4 + random.random() * 0.25, 3),  # nosec B311
    }

    return {
        "data": {
            "fixture_id": fixture_id,
            "result": result,
            "score": {"home": home_goals, "away": away_goals},
            "total_goals": total_goals,
            "btts": int(home_goals) > 0 and int(away_goals) > 0,
            "over_25": total_goals > 2,
            "prediction": prediction,
            "prediction_correct": {
                "result": (result == "home" and prediction["home_win_prob"] > 0.4)
                or (result == "draw" and prediction["draw_prob"] > 0.3)
                or (result == "away" and prediction["away_win_prob"] > 0.4),
                "btts": (int(home_goals) > 0 and int(away_goals) > 0) == (prediction["btts_prob"] > 0.5),
                "over_25": (total_goals > 2) == (prediction["over_25_prob"] > 0.5),
            },
            "pnl": {
                "result_bet_pnl": round(random.uniform(-500, 1500), 2),  # nosec B311
                "over_under_pnl": round(random.uniform(-300, 800), 2),  # nosec B311
                "btts_pnl": round(random.uniform(-200, 600), 2),  # nosec B311
                "total_pnl": round(random.uniform(-400, 2000), 2),  # nosec B311
            },
        },
        "meta": {"fixture_id": fixture_id, "timestamp": time.time()},
    }


@router.get("/history")
async def get_fixture_history(
    request: Request,
    league: str = Query(None, description="Filter by league"),
    date: str = Query(None, description="Filter by date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    """Get historical fixtures with results and P&L summary."""
    fixtures = _ensure_mock_fixtures()
    completed = [f for f in fixtures if f.get("status") == "FT"]

    if league:
        completed = [f for f in completed if f.get("league_id") == league]

    results = []
    for f in completed:
        score = f.get("score", {})
        h = score.get("home", 0) if isinstance(score, dict) else 0
        a = score.get("away", 0) if isinstance(score, dict) else 0
        results.append(
            {
                **{k: v for k, v in f.items() if k != "odds"},
                "result": "home" if int(h) > int(a) else ("away" if int(a) > int(h) else "draw"),
                "total_goals": int(h) + int(a),
                "fixture_pnl": round(random.uniform(-500, 1500), 2),  # nosec B311
            }
        )

    start = (page - 1) * page_size
    return {
        "data": results[start : start + page_size],
        "meta": {
            "total": len(results),
            "page": page,
            "page_size": page_size,
            "timestamp": time.time(),
        },
    }


@router.get("/fixtures/{fixture_id}/injuries")
async def get_fixture_injuries(
    request: Request,
    fixture_id: str,
) -> dict[str, object]:
    """Get injury/absence list for a fixture's teams."""
    mock_injuries = [
        {
            "player_name": "Kalvin Phillips",
            "team": "home",
            "reason": "Shoulder injury",
            "absence_type": "injured",
            "expected_return": "2026-05-01",
        },
        {
            "player_name": "Rasmus Hojlund",
            "team": "away",
            "reason": "Hamstring",
            "absence_type": "injured",
            "expected_return": "2026-04-20",
        },
    ]
    return {"data": mock_injuries, "meta": {"fixture_id": fixture_id, "timestamp": time.time()}}
