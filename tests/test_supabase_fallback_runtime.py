import gateway.db.supabase_client as supabase_module


def test_get_client_falls_back_to_in_memory_store(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.setattr(supabase_module, "_client", None)
    monkeypatch.setattr(supabase_module, "_in_memory_client", None)

    client = supabase_module.get_client()

    inserted = client.table("chat_history").insert({"session_id": "s1", "role": "user", "content": "hello"}).execute()
    fetched = client.table("chat_history").select("*").eq("session_id", "s1").execute()

    assert getattr(client, "backend", "") == "in_memory"
    assert inserted.data[0]["session_id"] == "s1"
    assert fetched.data[0]["content"] == "hello"


def test_in_memory_client_supports_update_and_delete(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.setattr(supabase_module, "_client", None)
    monkeypatch.setattr(supabase_module, "_in_memory_client", None)

    client = supabase_module.get_client()
    row = client.table("sessions").insert({"session_id": "demo"}).execute().data[0]
    updated = client.table("sessions").update({"user_id": "u1"}).eq("id", row["id"]).execute()
    deleted = client.table("sessions").delete().eq("id", row["id"]).execute()
    remaining = client.table("sessions").select("*").eq("id", row["id"]).execute()

    assert updated.data[0]["user_id"] == "u1"
    assert deleted.data[0]["id"] == row["id"]
    assert remaining.data == []


class _MissingTableError(RuntimeError):
    code = "PGRST205"

    def __init__(self, table_name: str):
        super().__init__(f"Could not find the table 'public.{table_name}' in the schema cache")


class _MissingTableQuery:
    def insert(self, payload):
        return self

    def update(self, payload):
        return self

    def select(self, fields="*"):
        return self

    def eq(self, key, value):
        return self

    def order(self, key, desc=False):
        return self

    def limit(self, value):
        return self

    def execute(self):
        raise _MissingTableError("daily_reviews")


class _MissingTableClient:
    def table(self, name):
        return _MissingTableQuery()


def test_generic_table_helpers_fall_back_when_supabase_table_missing(monkeypatch):
    monkeypatch.setattr(supabase_module, "_client", _MissingTableClient())
    monkeypatch.setattr(supabase_module, "_in_memory_client", None)
    monkeypatch.setattr(supabase_module, "_table_fallback_warnings", set())

    saved = supabase_module.save_table_row(
        "daily_reviews",
        {"review_id": "review-1", "generated_at": "2026-04-20T00:00:00Z", "report_text": "ok"},
    )
    listed = supabase_module.list_table_rows("daily_reviews", order_by="generated_at")
    latest = supabase_module.latest_table_row("daily_reviews", order_by="generated_at")

    assert saved[0]["review_id"] == "review-1"
    assert listed[0]["report_text"] == "ok"
    assert latest["review_id"] == "review-1"


def test_generic_update_helper_falls_back_when_supabase_table_missing(monkeypatch):
    monkeypatch.setattr(supabase_module, "_client", _MissingTableClient())
    monkeypatch.setattr(supabase_module, "_in_memory_client", None)
    monkeypatch.setattr(supabase_module, "_table_fallback_warnings", set())

    supabase_module.save_table_row(
        "watchlist",
        {"watchlist_id": "wl-1", "symbol": "AAPL", "enabled": True},
    )
    updated = supabase_module.update_table_row(
        "watchlist",
        {"note": "fallback update"},
        match={"watchlist_id": "wl-1"},
    )

    assert updated[0]["note"] == "fallback update"
