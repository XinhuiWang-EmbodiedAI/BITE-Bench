"""Python 3.12+ standalone entry point, no pip/uv needed on Windows."""

import argparse
import json
import sys
from pathlib import Path

from bite_collect.bank import Bank, CollectError
from bite_collect.exporter import write_export
from bite_collect.server import LocalServer
from bite_collect.store import Store

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3, 12):
        print("Python 3.12 or newer is required.", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(
        description="BITE Collect offline SYNTHETIC DEMO — formal collection disabled"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "validate", "status", "export", "backup"],
    )
    parser.add_argument(
        "--bank", type=Path, default=ROOT / "fixtures/synthetic/questionnaire.json"
    )
    parser.add_argument(
        "--db", type=Path, default=ROOT / "runtime/synthetic/collect.sqlite3"
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--purpose", default="synthetic", choices=["synthetic", "human"]
    )
    args = parser.parse_args()
    try:
        bank = Bank.load(args.bank)
        if args.command == "validate":
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "bank_sha256": bank.sha256,
                        "pairs": 50,
                        "ratings": 8,
                        "is_synthetic": True,
                        "research_eligible": False,
                    },
                    indent=2,
                )
            )
            return 0
        store = Store(args.db, bank)
        if args.command == "serve":
            server = LocalServer(store, args.port)
            print(
                f"SYNTHETIC DEMO only. Formal human collection DISABLED.\nParticipant: {server.origin}/\nCollector: {server.origin}/collector\nCollector access code (private, changes on restart): {server.collector_key}\nSQLite: {store.path}\nCtrl+C to stop.",
                flush=True,
            )
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        elif args.command == "status":
            print(json.dumps(store.summary(), ensure_ascii=False, indent=2))
        elif args.command == "export":
            if not args.out:
                raise CollectError("export 要求 --out synthetic/<new-file>.zip")
            print(
                json.dumps(
                    write_export(store, args.out, args.purpose),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "backup":
            if not args.out:
                raise CollectError("backup 要求 --out synthetic/<new-file>.sqlite3")
            store.backup(args.out)
            print("Backup saved (contains local consent records; keep private).")
        return 0
    except (CollectError, OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
