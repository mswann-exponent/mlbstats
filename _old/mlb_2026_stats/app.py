from flask import Flask, render_template, request, jsonify, Response
import csv
import io
from _old.mlb_2026_stats.models import init_db, get_conn

app = Flask(__name__)

def build_where_clause(season, start_date, end_date):
    clauses = []
    params = []

    if season:
        clauses.append("pgs.season = ?")
        params.append(season)

    if start_date:
        clauses.append("pgs.game_date >= ?")
        params.append(start_date)

    if end_date:
        clauses.append("pgs.game_date <= ?")
        params.append(end_date)

    where_sql = "WHERE " + " AND ".join(clauses) if clauses else ""
    return where_sql, params

def get_aggregated_stats(season="2026", start_date=None, end_date=None):
    conn = get_conn()
    cur = conn.cursor()

    where_sql, params = build_where_clause(season, start_date, end_date)

    query = f"""
    SELECT
        p.player_id,
        p.full_name,
        p.current_team,
        p.position,
        p.bats,
        p.throws,

        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.games ELSE 0 END) as hitting_games,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.at_bats ELSE 0 END) as at_bats,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.runs ELSE 0 END) as runs,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.hits ELSE 0 END) as hits,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.doubles ELSE 0 END) as doubles,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.triples ELSE 0 END) as triples,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.home_runs ELSE 0 END) as home_runs,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.rbi ELSE 0 END) as rbi,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.stolen_bases ELSE 0 END) as stolen_bases,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.walks ELSE 0 END) as walks,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.strikeouts ELSE 0 END) as hitting_strikeouts,
        SUM(CASE WHEN pgs.stat_group = 'hitting' THEN pgs.hit_by_pitch ELSE 0 END) as hit_by_pitch,

        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.games ELSE 0 END) as pitching_games,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.innings_pitched ELSE 0 END) as innings_pitched,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.wins ELSE 0 END) as wins,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.losses ELSE 0 END) as losses,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.saves ELSE 0 END) as saves,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.earned_runs ELSE 0 END) as earned_runs,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.hits_allowed ELSE 0 END) as hits_allowed,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.walks_allowed ELSE 0 END) as walks_allowed,
        SUM(CASE WHEN pgs.stat_group = 'pitching' THEN pgs.pitching_strikeouts ELSE 0 END) as pitching_strikeouts

    FROM player_game_stats pgs
    JOIN players p ON p.player_id = pgs.player_id
    {where_sql}
    GROUP BY p.player_id, p.full_name, p.current_team, p.position, p.bats, p.throws
    ORDER BY p.full_name
    """

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    result = []
    for row in rows:
        ab = row["at_bats"] or 0
        hits = row["hits"] or 0
        walks = row["walks"] or 0
        hbp = row["hit_by_pitch"] or 0
        doubles = row["doubles"] or 0
        triples = row["triples"] or 0
        home_runs = row["home_runs"] or 0

        singles = hits - doubles - triples - home_runs
        total_bases = singles + (doubles * 2) + (triples * 3) + (home_runs * 4)

        avg = round(hits / ab, 3) if ab > 0 else 0
        obp_den = ab + walks + hbp
        obp = round((hits + walks + hbp) / obp_den, 3) if obp_den > 0 else 0
        slg = round(total_bases / ab, 3) if ab > 0 else 0
        ops = round(obp + slg, 3)

        ip = row["innings_pitched"] or 0
        er = row["earned_runs"] or 0
        hits_allowed = row["hits_allowed"] or 0
        walks_allowed = row["walks_allowed"] or 0

        era = round((er * 9) / ip, 2) if ip > 0 else 0
        whip = round((walks_allowed + hits_allowed) / ip, 3) if ip > 0 else 0

        result.append({
            "player_id": row["player_id"],
            "full_name": row["full_name"],
            "current_team": row["current_team"],
            "position": row["position"],
            "bats": row["bats"],
            "throws": row["throws"],
            "hitting_games": row["hitting_games"] or 0,
            "at_bats": ab,
            "runs": row["runs"] or 0,
            "hits": hits,
            "doubles": doubles,
            "triples": triples,
            "home_runs": home_runs,
            "rbi": row["rbi"] or 0,
            "stolen_bases": row["stolen_bases"] or 0,
            "walks": walks,
            "hitting_strikeouts": row["hitting_strikeouts"] or 0,
            "avg": avg,
            "obp": obp,
            "slg": slg,
            "ops": ops,
            "pitching_games": row["pitching_games"] or 0,
            "innings_pitched": round(ip, 3),
            "wins": row["wins"] or 0,
            "losses": row["losses"] or 0,
            "saves": row["saves"] or 0,
            "earned_runs": er,
            "hits_allowed": hits_allowed,
            "walks_allowed": walks_allowed,
            "pitching_strikeouts": row["pitching_strikeouts"] or 0,
            "era": era,
            "whip": whip
        })

    return result

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/stats")
def api_stats():
    season = request.args.get("season", "2026")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    data = get_aggregated_stats(season=season, start_date=start_date, end_date=end_date)
    return jsonify({
        "count": len(data),
        "players": data
    })

@app.route("/download.csv")
def download_csv():
    season = request.args.get("season", "2026")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    data = get_aggregated_stats(season=season, start_date=start_date, end_date=end_date)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "player_id",
        "full_name",
        "current_team",
        "position",
        "bats",
        "throws",
        "hitting_games",
        "at_bats",
        "runs",
        "hits",
        "doubles",
        "triples",
        "home_runs",
        "rbi",
        "stolen_bases",
        "walks",
        "hitting_strikeouts",
        "avg",
        "obp",
        "slg",
        "ops",
        "pitching_games",
        "innings_pitched",
        "wins",
        "losses",
        "saves",
        "earned_runs",
        "hits_allowed",
        "walks_allowed",
        "pitching_strikeouts",
        "era",
        "whip"
    ])

    for p in data:
        writer.writerow([
            p["player_id"],
            p["full_name"],
            p["current_team"],
            p["position"],
            p["bats"],
            p["throws"],
            p["hitting_games"],
            p["at_bats"],
            p["runs"],
            p["hits"],
            p["doubles"],
            p["triples"],
            p["home_runs"],
            p["rbi"],
            p["stolen_bases"],
            p["walks"],
            p["hitting_strikeouts"],
            p["avg"],
            p["obp"],
            p["slg"],
            p["ops"],
            p["pitching_games"],
            p["innings_pitched"],
            p["wins"],
            p["losses"],
            p["saves"],
            p["earned_runs"],
            p["hits_allowed"],
            p["walks_allowed"],
            p["pitching_strikeouts"],
            p["era"],
            p["whip"]
        ])

    csv_data = output.getvalue()
    output.close()

    filename = f"mlb_aggregate_stats_{season}.csv"
    if start_date and end_date:
        filename = f"mlb_aggregate_stats_{season}_{start_date}_to_{end_date}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

if __name__ == "__main__":
    init_db()
    app.run(debug=False, use_reloader=False)
