# 0109 — On-Chain Smart-Money-Flow Regime-Overlay (I0102)

**Idee:** I0102 (Memo `ONCHAIN-WALLET-ALPHA-RESEARCH.md`, Batch 9). Der einzige
CTI-relevante Überlebende des On-Chain-Wallet-Memos: aggregierter On-Chain-Flow als
**Sizing-Overlay** auf den BTC/ETH-Sleeve — *nicht* Trade-Kopie (vermeidet Imitation
Penalty + Kostenwand). Geschwister-Mechanik von 0086 (Macro-Regime) / I0086 (MVRV) /
I0099 (Vol-Gate).

## Daten & Proxy-Disziplin

Das Memo verlangt **Nansen Smart-Money-Netflow** — kostenpflichtig **und** mit
PIT-Problem (Labels sind ex-post abgeleitet, Look-ahead-Falle wie I0086). Der freie,
**PIT-saubere** Proxy ist die **aggregierte Stablecoin-Supply-Änderung** (DefiLlama,
`stablecoins.llama.fi`, 2017-11 ff., täglich) — vom Memo selbst als **I0102 Variante 8
/ Erweiterung** gelistet. Ökonomik identisch: steigende aggregierte Stablecoin-Supply
= frisch gemintetes Kapital / „dry powder" = informierter Positionierungs-Anker
(Kohorten-Aggregat, Gesetz der großen Zahlen — exakt Nische A). Supply zum Datum t ist
am Datum t beobachtbar → kein Look-ahead. Signal `t-1`, Anwendung `t`.

BTC/ETH-Preis: Binance daily via ccxt (2018-01 .. 2026-06, n=3092).

**Wichtig:** Dies testet den **Mechanismus** (Aggregat-Flow → Sleeve-Sizing), nicht das
exakte Nansen-Signal. Das exakte Nansen-/Arkham-Signal bleibt `deferred (Daten-Blocker)`.

## Registrierte Regel (I0102)

7-Tage-Flow-Änderung, oberstes Tertil **und** steigend → Sleeve ×1,25; unterstes
Tertil **und** fallend → ×0,5; sonst ×1,0. Overlay, kein eigener Exit/Stop.

## Ergebnisse

**IC (Spearman, Flow-Änderung t-1 → Forward-Return):**

| Sleeve | Fenster | h=1d | h=7d |
| --- | --- | --- | --- |
| BTC | 7d | +0,036 (p=0,045) | **+0,121 (p<0,001)** |
| BTC+ETH | 7d | +0,043 (p=0,017) | **+0,133 (p<0,001)** |

Der Aggregat-Flow hat **echten positiven IC** zum Forward-Return — die Kern-These des
Memos (Aggregat-Flow ≫ Einzel-Wallet-Copy) hält **richtungsweisend**.

**Overlay-Backtest (registriertes 7d-Fenster):**

| Sleeve | Overlay-Sharpe | B&H-Sharpe | Overlay-MaxDD | B&H-MaxDD | Perm-p (Drift-Trap) | Ann. Mehrrendite-KI |
| --- | --- | --- | --- | --- | --- | --- |
| BTC | +0,68 | +0,61 | −0,80 | −0,81 | **0,153** | **[−8,3 %, +14,9 %]** |
| BTC+ETH | +0,71 | +0,60 | −0,86 | −0,88 | **0,078** | **[−5,8 %, +19,2 %]** |

Robustheits-Gitter (Fenster 3/7/14/30d): Overlay-Sharpe durchweg leicht über B&H
(+0,68…+0,81), MaxDD-Verbesserung durchweg marginal (1–2 Pp).

## Urteil: **Overlay (schwach) / kein validierter Edge** — bestätigt die ehrliche Memo-Erwartung

1. **IC real, Monetarisierung schwach — exakt die 0058-Lehre („hoher IC ≠ Portfolio-PnL").**
   IC h7 +0,12/+0,13 (p<0,001), aber als handelbares Sizing-Overlay nur +0,07–0,11
   Sharpe über B&H und **1–2 Pp** DD-Verbesserung.
2. **Permutation (Drift-Trap) NICHT bestanden:** Flow-*Timing* schlägt Zufalls-Timing
   gleicher Verteilung nicht signifikant (p=0,153 BTC / 0,078 BTC+ETH). Der Sharpe-Lift
   ist überwiegend gehaltenes Krypto-Beta, kein Timing-Skill.
3. **Bootstrap-KI der Mehrrendite kreuzt die Null** (beide Sleeves) — der einzige ehrliche
   „Edge>0"-Test fällt durch.
4. **Overlap-Vorbehalt (0046-Lehre):** der starke IC-h7-p-Wert ist durch überlappende
   7-Tage-Forward-Returns inflationiert; die positionsbasierte Permutation ist der ehrliche
   Read — und der ist insignifikant.
5. Die Memo-Behauptung „senkt DD im Bust" reproduziert sich **nur marginal**.

**Damit ist die zentrale Memo-Schlussfolgerung empirisch belegt:** I0102 ist bestenfalls
ein **schwaches Sizing-Overlay** („Sharpe-Beitrag, kein Standalone-Edge" — genau wie das
Memo selbst schrieb), kein eigenständiger Edge. Es übertrifft die bestehenden Overlays
(MVRV 0086/I0086, Vol-Gate I0099) nicht und rechtfertigt keinen Nansen-Kauf — der freie
Stablecoin-Proxy trägt den Mechanismus genauso (un-)gut.

## Status der übrigen Memo-Hypothesen (Reproduktions-Treue-Pflicht)

- **I0103** (Hyperliquid Slow-Swing-Following): `deferred (Daten-Blocker)` — survivorship-
  /PIT-saubere historische Leaderboard-Track-Records nicht frei beschaffbar (Hyperliquid-API
  liefert Live-Positionen, keine PIT-Historie selektierter Leader). **Nicht CTI-handelbar.**
- **I0104** (Treasury-/Entity-Accumulation): `deferred (Daten-Blocker)` — Arkham-Entity-Flows
  kostenpflichtig; freie survivorship-saubere Entity-Historie fehlt.
- **I0105** (Naiver Memecoin-Copy, Negativtest): `deferred (Daten-Blocker)` — braucht
  GMGN/Dune-Wallet-Tx + Memecoin-Tick-Preise mit PIT-Wallet-Selektion. Die Kostenwand
  (3,2–6,6 % RT) ist strukturell und vom Memo korrekt zitiert (verwandt 0012-0015/0069);
  kein freier Datensatz, um sie im eigenen Backtest zu beziffern.

Kein Reject dieser drei (Stufe-1-Originalform nicht reproduzierbar = `deferred`, nicht
`reject`, gemäß `RESEARCH-PROCESS.md` §Reproduktions-Treue-Pflicht).
