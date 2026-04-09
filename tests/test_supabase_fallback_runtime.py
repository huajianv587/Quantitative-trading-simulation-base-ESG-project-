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

