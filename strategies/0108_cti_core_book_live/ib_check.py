"""Read-only IBKR connection + safety check. NO orders are placed.

Connects to a locally running TWS/Gateway, verifies the account is PAPER (id starts
with 'DU'), and prints the account equity. This is the gate before any adapter work:
if this fails, the API socket is not enabled or the port is wrong.

TWS paper default port = 7497 (TWS live = 7496; Gateway paper = 4002). We only try
paper ports so we can never accidentally touch a live account.
Run: .venv/Scripts/python.exe strategies/0108_cti_core_book_live/ib_check.py
"""
from __future__ import annotations

from ib_async import IB, util

PAPER_PORTS = [7497, 4002]   # TWS-paper, Gateway-paper. Live ports deliberately excluded.
CLIENT_ID = 17


def main() -> None:
    ib = IB()
    connected_port = None
    for port in PAPER_PORTS:
        try:
            ib.connect("127.0.0.1", port, clientId=CLIENT_ID, timeout=8, readonly=True)
            connected_port = port
            break
        except Exception as e:  # noqa: BLE001
            print(f"  port {port}: not reachable ({type(e).__name__}: {e})")
    if connected_port is None:
        print("\nNO CONNECTION. In TWS: Configure -> API -> Settings -> 'Enable ActiveX and "
              "Socket Clients', Socket port 7497, add 127.0.0.1 to Trusted IPs, uncheck "
              "'Read-Only API' only when we later place orders.")
        return

    accounts = ib.managedAccounts()
    print(f"\nConnected on port {connected_port}. Managed accounts: {accounts}")
    is_paper = all(a.startswith("DU") for a in accounts) and len(accounts) > 0
    print(f"PAPER account? {'YES (DU*)' if is_paper else 'NO -- STOP, this looks like a live account!'}")

    if not is_paper:
        ib.disconnect()
        return

    summ = {s.tag: s.value for s in ib.accountSummary() if s.tag in
            ("NetLiquidation", "TotalCashValue", "AvailableFunds", "BuyingPower", "Currency")}
    print("Account summary:", summ)
    print(f"Server version: {ib.client.serverVersion()}  | TWS time: {ib.reqCurrentTime()}")
    ib.disconnect()
    print("\nOK -> connection + paper check passed. Safe to proceed to instrument mapping.")


if __name__ == "__main__":
    util.logToConsole(level=40)  # ERROR only, keep output clean
    main()
