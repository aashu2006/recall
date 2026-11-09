from datetime import date

from scripts import seed
from tests.fake_db import FakeDb

TODAY = date(2026, 11, 9)


def test_seed_creates_sharma_bracket_order_and_deliveries():
    db = FakeDb()

    out = seed.seed(db, TODAY, {"sharma": "+91 99999 11111"})

    assert len(db.clients) == 3
    sharma = db.client_by_phone("919999911111")
    assert sharma["name"] == "Sharma Steels" and "Sharma ji" in sharma["aliases"]
    [bracket] = [o for o in db.open_orders(sharma["id"]) if o["item"] == "bracket"]
    assert (bracket["quantity"], bracket["rate"], bracket["unit"]) == (200, 45, "pcs")
    assert len(db.deliveries_between(TODAY, TODAY)) == 2
    assert len(db.deliveries_between(date(2026, 11, 10), date(2026, 11, 10))) == 2
    # every order has its 'created' history row
    assert sorted(c["order_id"] for c in db.changes if c["field"] == "created") == sorted(out["orders"])


def test_seed_is_rerunnable():
    db = FakeDb()
    seed.seed(db, TODAY)

    out = seed.seed(db, TODAY)

    assert out == {"clients": {}, "orders": []} and len(db.clients) == 3
