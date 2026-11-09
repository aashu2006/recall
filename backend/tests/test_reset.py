from scripts import reset


class FakeQuery:
    def __init__(self, sb, table):
        self.sb, self.table = sb, table

    def delete(self, *, count=None, returning=None):
        self.sb.calls.append(("delete", self.table, count.value, returning.value))
        return self

    def gte(self, column, value):
        self.sb.calls.append(("gte", self.table, column, value))
        return self

    def execute(self):
        return type("Res", (), {"count": self.sb.rows.get(self.table, 0)})()


class FakeSb:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def table(self, name):
        return FakeQuery(self, name)


def test_reset_deletes_children_before_parents():
    sb = FakeSb({"orders": 6, "order_changes": 9, "clients": 3})

    deleted = reset.reset(sb)

    order = [c[1] for c in sb.calls if c[0] == "delete"]
    assert order == ["order_changes", "reminders", "pending_confirmations", "wa_sends", "orders", "calls", "clients"]
    for child, parent in [("order_changes", "orders"), ("order_changes", "calls"), ("reminders", "orders"),
                          ("pending_confirmations", "calls"), ("pending_confirmations", "clients"),
                          ("orders", "clients"), ("calls", "clients")]:
        assert order.index(child) < order.index(parent)
    assert all(c[2:] == ("id", 0) for c in sb.calls if c[0] == "gte")  # every delete has a filter
    assert deleted["order_changes"] == 9 and deleted["reminders"] == 0


def test_main_asks_first_and_stops_on_no(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    monkeypatch.setattr(reset, "get_db", lambda: (_ for _ in ()).throw(AssertionError("db touched")))

    reset.main([])

    assert "Nothing deleted" in capsys.readouterr().out


def test_main_yes_skips_question(monkeypatch):
    sb = FakeSb({})
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(AssertionError("asked")))
    monkeypatch.setattr(reset, "get_db", lambda: type("Db", (), {"sb": sb})())

    reset.main(["--yes"])

    assert len([c for c in sb.calls if c[0] == "delete"]) == len(reset.TABLES)
