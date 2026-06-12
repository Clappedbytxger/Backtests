"""Live-Paper-Forward des Football-Value-Betting-Programms (Phase 3, 0065).

Täglicher Tick (idealerweise morgens an Spieltagen, KEIN Echtgeld):

    .\\.venv\\Scripts\\python.exe scripts\\football_live_paper.py            # Scan + Report
    .\\.venv\\Scripts\\python.exe scripts\\football_live_paper.py --report   # nur Report (0 Credits)
    .\\.venv\\Scripts\\python.exe scripts\\football_live_paper.py --list-sports

Ablauf je Tick:
1. **Scan** (nur Ligen mit Spielen in den nächsten 48h — der kostenlose
   /events-Check spart Credits in spielfreien Wochen): Pinnacle-Quoten
   snapshotten, eingefrorene Regel (Shin-De-Vig, EV > 2 %, Cap 20 %)
   anwenden, neue Paper-Wetten loggen (beste Soft-Book-Quote je Outcome,
   ¼-Kelly-Stake dokumentiert).
2. **Closing-Pass:** angepfiffene offene Wetten gegen den LETZTEN
   Pinnacle-Snapshot vor Anpfiff schließen → CLV.
3. **Settlement:** Ergebnisse via /scores (2 Credits, nur wenn nötig) →
   Paper-P&L (Sekundärmetrik).
4. **Report:** Gate-Fortschritt (vorab registriert in 0065-REPORT.md):
   Median-CLV ≥ +1 % bei ≥ 150 Wetten (validierte Ligen) UND
   mittlerer CLV nach 1%-Slippage-Äquivalent > 0.

State (CSV, eingecheckt = der Forward-Log ist git-versioniert):
``strategies/0065_football_live_paper/state/``.

Quota-Budget: Gratis-Tier ~500 Credits/Monat; /odds = 1 Credit je Liga-Call.
Der Events-Vorfilter hält den Verbrauch bei ~Spieltagen × aktive Ligen.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.clv import clv_summary  # noqa: E402
from quantlab.odds_live import (  # noqa: E402
    OUTCOMES, OddsApiClient, fair_close_prob, find_value_bets, h2h_odds,
    kelly_stake,
)

STATE = ROOT / "strategies" / "0065_football_live_paper" / "state"
STATE.mkdir(parents=True, exist_ok=True)
BETS_CSV = STATE / "paper_bets.csv"
SNAPS_CSV = STATE / "pinnacle_snapshots.csv"
QUOTA_JSON = STATE / "quota.json"

LOOKAHEAD_H = 48  # nur Events innerhalb dieses Fensters scannen/wetten

# tier "validated" = Ligen aus den Backtest-Panels 0063/0064 (Gate-relevant);
# tier "extension" = Sommer-Ligen, separat berichtet (zusätzlicher Cross-OOS,
# fließt NICHT ins Gate).
LEAGUES: dict[str, tuple[str, str]] = {
    # sport_key: (div, tier)
    "soccer_epl": ("E0", "validated"),
    "soccer_efl_champ": ("E1", "validated"),
    "soccer_england_league1": ("E2", "validated"),
    "soccer_england_league2": ("E3", "validated"),
    "soccer_germany_bundesliga": ("D1", "validated"),
    "soccer_germany_bundesliga2": ("D2", "validated"),
    "soccer_spain_la_liga": ("SP1", "validated"),
    "soccer_spain_segunda_division": ("SP2", "validated"),
    "soccer_italy_serie_a": ("I1", "validated"),
    "soccer_italy_serie_b": ("I2", "validated"),
    "soccer_france_ligue_one": ("F1", "validated"),
    "soccer_france_ligue_two": ("F2", "validated"),
    "soccer_netherlands_eredivisie": ("N1", "validated"),
    "soccer_portugal_primeira_liga": ("P1", "validated"),
    "soccer_belgium_first_div": ("B1", "validated"),
    "soccer_turkey_super_league": ("T1", "validated"),
    "soccer_greece_super_league": ("G1", "validated"),
    "soccer_spl": ("SC0", "validated"),
    # Sommer-Ligen (Saison Apr-Nov): überbrücken die EU-Sommerpause
    "soccer_sweden_allsvenskan": ("SWE", "extension"),
    "soccer_norway_eliteserien": ("NOR", "extension"),
    "soccer_finland_veikkausliiga": ("FIN", "extension"),
    "soccer_usa_mls": ("MLS", "extension"),
    "soccer_brazil_campeonato": ("BRA", "extension"),
    "soccer_japan_j_league": ("JPN", "extension"),
}

BET_COLUMNS = [
    "bet_id", "placed_at", "sport_key", "div", "tier", "commence_time",
    "home", "away", "outcome", "bookmaker", "odds", "fair_p_bet", "ev",
    "stake", "pin_h", "pin_d", "pin_a", "status", "closed_at",
    "fair_p_close", "close_staleness_h", "clv", "result", "ret",
]


def load_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns)


def now_utc() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(timezone.utc))


def scan(client: OddsApiClient, bets: pd.DataFrame, snaps: pd.DataFrame,
         min_credits: int = 25) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ligen mit nahen Spielen pollen, Snapshots + neue Paper-Wetten loggen."""
    ts = now_utc()
    horizon = ts + timedelta(hours=LOOKAHEAD_H)
    new_bets, new_snaps = [], []

    for sport_key, (div, tier) in LEAGUES.items():
        # Kostenloser Vorfilter: lohnt der 1-Credit-/odds-Call?
        try:
            events = client.get_events(sport_key)
        except Exception as exc:
            print(f"  {div}: /events fehlgeschlagen ({str(exc)[:60]}) -> skip")
            continue
        upcoming = [
            e for e in events
            if ts <= pd.Timestamp(e["commence_time"]) <= horizon
        ]
        if not upcoming:
            continue
        if client.remaining is not None and client.remaining < min_credits:
            print(f"  Quota-Guard: nur noch {client.remaining} Credits -> Scan-Stopp")
            break

        try:
            odds_events = client.get_odds(sport_key)
        except Exception as exc:
            print(f"  {div}: /odds fehlgeschlagen ({str(exc)[:60]}) -> skip")
            continue

        n_alerts = 0
        for event in odds_events:
            kickoff = pd.Timestamp(event["commence_time"])
            if not (ts <= kickoff <= horizon):
                continue
            pin = h2h_odds(event, "pinnacle")
            if pin is not None:
                new_snaps.append({
                    "snapshot_at": ts.isoformat(), "event_id": event["id"],
                    "sport_key": sport_key, "commence_time": event["commence_time"],
                    "home": event["home_team"], "away": event["away_team"],
                    "pin_h": pin[0], "pin_d": pin[1], "pin_a": pin[2],
                })
            for alert in find_value_bets(event):
                bet_id = f"{alert['event_id']}_{alert['outcome']}"
                if len(bets) and (bets["bet_id"] == bet_id).any():
                    continue  # schon gewettet (erste Sichtung zählt)
                stake = kelly_stake(alert["fair_p_bet"], alert["odds"])
                if stake <= 0:
                    continue
                new_bets.append({
                    "bet_id": bet_id, "placed_at": ts.isoformat(),
                    "sport_key": sport_key, "div": div, "tier": tier,
                    "commence_time": alert["commence_time"],
                    "home": alert["home"], "away": alert["away"],
                    "outcome": alert["outcome"], "bookmaker": alert["bookmaker"],
                    "odds": alert["odds"], "fair_p_bet": alert["fair_p_bet"],
                    "ev": alert["ev"], "stake": stake,
                    "pin_h": alert["pin_h"], "pin_d": alert["pin_d"],
                    "pin_a": alert["pin_a"], "status": "open",
                    "closed_at": "", "fair_p_close": np.nan,
                    "close_staleness_h": np.nan, "clv": np.nan,
                    "result": "", "ret": np.nan,
                })
                n_alerts += 1
                bets = pd.concat([bets, pd.DataFrame([new_bets[-1]])],
                                 ignore_index=True)
        flag = f", {n_alerts} ALERT(S)" if n_alerts else ""
        print(f"  {div} ({tier}): {len(upcoming)} Spiele <{LOOKAHEAD_H}h, "
              f"{len(odds_events)} mit Quoten{flag}")

    if new_snaps:
        snaps = pd.concat([snaps, pd.DataFrame(new_snaps)], ignore_index=True)
    return bets, snaps


def close_bets(bets: pd.DataFrame, snaps: pd.DataFrame) -> pd.DataFrame:
    """Angepfiffene offene Wetten gegen den letzten Pre-Kickoff-Snapshot schließen."""
    ts = now_utc()
    open_started = bets[(bets["status"] == "open")
                        & (pd.to_datetime(bets["commence_time"], utc=True) <= ts)]
    for idx, bet in open_started.iterrows():
        kickoff = pd.Timestamp(bet["commence_time"])
        s = snaps[snaps["event_id"] == bet["bet_id"].rsplit("_", 1)[0]].copy()
        if s.empty:
            continue
        s["snapshot_at"] = pd.to_datetime(s["snapshot_at"], utc=True)
        # Nur Snapshots NACH der Wette zählen als Schlusslinien-Proxy: der
        # Entry-Snapshot selbst würde CLV = EV setzen (mechanisch >= 2%,
        # geschmeichelt) — lieber kein CLV als ein verfälschter.
        placed = pd.Timestamp(bet["placed_at"])
        s = s[(s["snapshot_at"] <= kickoff)
              & (s["snapshot_at"] > placed)].sort_values("snapshot_at")
        if s.empty:
            bets.loc[idx, "status"] = "no_close"  # kein Post-Bet-Snapshot
            continue
        last = s.iloc[-1]
        close = np.array([last["pin_h"], last["pin_d"], last["pin_a"]])
        fp = fair_close_prob(close, bet["outcome"])
        bets.loc[idx, "fair_p_close"] = fp
        bets.loc[idx, "clv"] = bet["odds"] * fp - 1.0
        bets.loc[idx, "close_staleness_h"] = (
            (kickoff - last["snapshot_at"]).total_seconds() / 3600.0)
        bets.loc[idx, "closed_at"] = ts.isoformat()
        bets.loc[idx, "status"] = "closed"
    return bets


def settle_bets(client: OddsApiClient, bets: pd.DataFrame) -> pd.DataFrame:
    """Ergebnisse via /scores für geschlossene, unsettelte Wetten (Paper-P&L)."""
    pending = bets[(bets["status"] == "closed") & (bets["result"] == "")]
    if isinstance(pending, pd.DataFrame) and pending.empty:
        return bets
    for sport_key in pending["sport_key"].unique():
        try:
            scores = client.get_scores(sport_key, days_from=3)
        except Exception as exc:
            print(f"  /scores {sport_key} fehlgeschlagen ({str(exc)[:60]})")
            continue
        results = {}
        for game in scores:
            if not game.get("completed") or not game.get("scores"):
                continue
            sc = {s["name"]: float(s["score"]) for s in game["scores"]}
            hg, ag = sc.get(game["home_team"]), sc.get(game["away_team"])
            if hg is None or ag is None:
                continue
            results[game["id"]] = "H" if hg > ag else ("A" if ag > hg else "D")
        for idx, bet in pending[pending["sport_key"] == sport_key].iterrows():
            event_id = bet["bet_id"].rsplit("_", 1)[0]
            if event_id in results:
                res = results[event_id]
                win = 1.0 if res == bet["outcome"] else 0.0
                bets.loc[idx, "result"] = res
                bets.loc[idx, "ret"] = bet["odds"] * win - 1.0
    return bets


def report(bets: pd.DataFrame) -> None:
    """Gate-Fortschritt (vorab registriert in 0065-REPORT.md)."""
    print("\n=== Paper-Forward-Report ===")
    if bets.empty:
        print("Noch keine Paper-Wetten geloggt.")
        return
    for tier in ("validated", "extension"):
        sub = bets[bets["tier"] == tier]
        closed = sub.dropna(subset=["clv"])
        print(f"\n[{tier}] Wetten: {len(sub)} (offen {int((sub['status'] == 'open').sum())}, "
              f"mit CLV {len(closed)}, no_close {int((sub['status'] == 'no_close').sum())})")
        if len(closed) < 5:
            continue
        s = clv_summary(closed["clv"].to_numpy())
        # 1%-Slippage-Äquivalent: 0.01*(odds-1)*p_close je Wette
        slip = 0.01 * (closed["odds"] - 1.0) * closed["fair_p_close"]
        clv_net = (closed["clv"] - slip).mean()
        stale = closed["close_staleness_h"].median()
        print(f"  Median-CLV {s['median']:+.4f} [{s['median_ci_low']:+.4f},"
              f"{s['median_ci_high']:+.4f}]  mean {s['mean']:+.4f}  "
              f"frac>0 {s['frac_positive']:.2f}")
        print(f"  mean CLV nach 1%-Slippage: {clv_net:+.4f}  |  "
              f"Median Close-Staleness: {stale:.1f}h")
        settled = closed[closed["result"] != ""]
        if len(settled):
            print(f"  Paper-P&L (flat, sekundär): {settled['ret'].mean():+.4f}/Wette "
                  f"über {len(settled)} settled")
        if tier == "validated":
            n_ok = len(closed) >= 150
            med_ok = s["median"] >= 0.01
            slip_ok = clv_net > 0
            print(f"  GATE: n>=150: {len(closed)}/150 {'OK' if n_ok else '...'} | "
                  f"Median>=+1%: {'OK' if med_ok else 'NEIN'} | "
                  f"mean-nach-Slippage>0: {'OK' if slip_ok else 'NEIN'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Football Value Betting Live-Paper-Tick")
    ap.add_argument("--report", action="store_true", help="nur Report, keine API-Calls")
    ap.add_argument("--list-sports", action="store_true", help="Sport-Keys prüfen (0 Credits)")
    ap.add_argument("--no-settle", action="store_true", help="/scores-Calls sparen")
    args = ap.parse_args()

    bets = load_csv(BETS_CSV, BET_COLUMNS)
    snaps = load_csv(SNAPS_CSV, ["snapshot_at", "event_id", "sport_key",
                                 "commence_time", "home", "away",
                                 "pin_h", "pin_d", "pin_a"])

    if args.list_sports:
        client = OddsApiClient()
        keys = {s["key"]: s for s in client.get_sports()}
        for sport_key, (div, tier) in LEAGUES.items():
            status = "OK" if sport_key in keys else "FEHLT in API!"
            active = keys.get(sport_key, {}).get("active", "?")
            print(f"  {sport_key:<38} {div:>4} {tier:<10} {status} (active={active})")
        return

    if not args.report:
        client = OddsApiClient()
        print(f"=== Scan {now_utc().isoformat()} ===")
        bets, snaps = scan(client, bets, snaps)
        bets = close_bets(bets, snaps)
        if not args.no_settle:
            bets = settle_bets(client, bets)
        bets.to_csv(BETS_CSV, index=False)
        snaps.to_csv(SNAPS_CSV, index=False)
        QUOTA_JSON.write_text(json.dumps({
            "at": now_utc().isoformat(),
            "remaining": client.remaining, "used": client.used}))
        print(f"\nQuota: {client.used} verbraucht, {client.remaining} übrig diesen Monat")
    else:
        bets = close_bets(bets, snaps)  # Closing geht auch offline

    report(bets)


if __name__ == "__main__":
    main()
