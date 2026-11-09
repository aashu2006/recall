"""Seed Supabase with 3 synthetic clients and open orders (demo data only, no real customers).

    cd backend && uv run python -m scripts.seed [--sharma-phone 9198xxxxxxxx] [--owner-phone ...]

Sharma Steels gets the open "200 bracket @ 45" order the demo voice note updates. Gupta
Fabricators gets two open MS sheet orders, so "MS sheet wala order 150 kar do" is ambiguous
and goes to the owner with both orders as buttons. Other orders are due today and tomorrow
(Asia/Kolkata) so the morning briefing has content.
Orders go through create_order, so each gets its 'created' order_changes row.
Skips any client whose phone already exists, so it is safe to re-run.
For the WhatsApp demo, pass the verified test numbers you will send voice notes from.
"""

import argparse
from datetime import date, datetime, timedelta

from app.db import Db, get_db, normalize_phone
from app.extract import IST

CLIENTS = [
    {
        "key": "sharma", "name": "Sharma Steels", "phone": "919800000001",
        "aliases": ["Sharma ji", "Sharma Steel", "शर्मा स्टील्स"],
        "orders": [
            {"item": "bracket", "quantity": 200, "unit": "pcs", "rate": 45, "days": 6},
            {"item": "angle", "spec": "40x40x5", "quantity": 300, "unit": "kg", "rate": 62, "days": 1},
        ],
    },
    {
        "key": "gupta", "name": "Gupta Fabricators", "phone": "919800000002",
        "aliases": ["Gupta ji", "गुप्ता जी"],
        "orders": [
            {"item": "MS sheet", "spec": "2mm", "quantity": 100, "unit": "pcs", "rate": 1150, "days": 0},
            {"item": "channel", "spec": "ISMC 75", "quantity": 40, "unit": "pcs", "rate": 890, "days": 1},
        ],
    },
    {
        "key": "patel", "name": "Patel Engineering Works", "phone": "919800000003",
        "aliases": ["Patel bhai", "पटेल भाई"],
        "orders": [
            {"item": "flange", "spec": "6 inch", "quantity": 25, "unit": "pcs", "rate": 420, "days": 0},
            {"item": "base plate", "spec": "10mm", "quantity": 60, "unit": "pcs", "rate": 275, "days": 4},
        ],
    },
]

# Created after every client's orders above, so those keep ids 1-6 in a fresh DB
# (eval/cases.json relies on that; the eval world is built from CLIENTS only).
EXTRA_ORDERS = {
    "gupta": [
        {"item": "MS sheet", "spec": "2mm", "quantity": 60, "unit": "pcs", "rate": 1100, "days": 4},
    ],
}


def seed(db: Db, today: date, phones: dict[str, str] | None = None) -> dict:
    """Create clients and orders. phones overrides a client's phone by key. Returns ids."""
    phones = phones or {}
    out = {"clients": {}, "orders": []}
    created = {}
    for c in CLIENTS:
        phone = normalize_phone(phones.get(c["key"]) or c["phone"])
        existing = db.client_by_phone(phone)
        if existing:
            print(f"skip {c['name']}: phone {phone} already belongs to client #{existing['id']}")
            continue
        client = db.create_client(c["name"], phone, c["aliases"])
        out["clients"][c["key"]] = client["id"]
        created[c["key"]] = (c["name"], client["id"])
        for o in c["orders"]:
            out["orders"].append(_create_order(db, c["name"], client["id"], o, today))
    for key, orders in EXTRA_ORDERS.items():
        if key in created:
            for o in orders:
                out["orders"].append(_create_order(db, *created[key], o, today))
    return out


def _create_order(db: Db, client_name: str, client_id: int, o: dict, today: date) -> int:
    fields = {k: v for k, v in o.items() if k != "days"}
    fields["delivery_date"] = today + timedelta(days=o["days"])
    order_id = db.create_order(client_id, fields)
    print(f"{client_name} #{client_id}: order #{order_id} {o['quantity']} {o['item']} "
          f"@ {o['rate']}, delivery {fields['delivery_date']}")
    return order_id


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for c in CLIENTS:
        parser.add_argument(f"--{c['key']}-phone", help=f"WhatsApp number for {c['name']} (default {c['phone']})")
    args = parser.parse_args(argv)
    phones = {c["key"]: getattr(args, f"{c['key']}_phone") for c in CLIENTS}
    seed(get_db(), datetime.now(IST).date(), phones)


if __name__ == "__main__":
    main()
