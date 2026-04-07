import importlib

from gateway.rag import embeddings


class _DummyVectors:
    def __init__(self, size):
        self.size = size


class _DummyParams:
    def __init__(self, size):
        self.vectors = _DummyVectors(size)


class _DummyConfig:
    def __init__(self, size):
        self.params = _DummyParams(size)


class _DummyCollectionInfo:
    def __init__(self, size):
        self.config = _DummyConfig(size)


def test_resolve_local_embedding_model_ignores_legacy_openai_name(monkeypatch):
    monkeypatch.delenv("LOCAL_EMBEDDING_MODEL", raising=False)
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")

    assert embeddings._resolve_local_embedding_model() == embeddings.DEFAULT_LOCAL_EMBEDDING_MODEL


def test_local_sentence_transformer_embedding_encodes_query(monkeypatch):
    calls = {}

    class DummySentenceTransformer:
        transformers_model = None

        def __init__(self, model_name, **kwargs):
            calls["model_name"] = model_name
            calls["kwargs"] = kwargs

        def encode(self, texts, **kwargs):
            calls["texts"] = texts
            calls["encode_kwargs"] = kwargs
            return [[0.1, 0.2, 0.3]]

        def get_sentence_embedding_dimension(self):
            return 3

    monkeypatch.setattr(embeddings, "SentenceTransformer", DummySentenceTransformer)

    model = embeddings.LocalSentenceTransformerEmbedding(
        model_name="demo/local-embed",
        device="cpu",
        configured_dimension=3,
    )

    vector = model.get_query_embedding("hello world")

    assert vector == [0.1, 0.2, 0.3]
    assert calls["model_name"] == "demo/local-embed"
    assert calls["texts"] == ["hello world"]
    assert calls["encode_kwargs"]["prompt_name"] == "query"


def test_validate_collection_embedding_dimension_rejects_mismatch(monkeypatch):
    monkeypatch.setattr(embeddings, "get_embed_dimension", lambda: 1536)

    try:
        embeddings.validate_collection_embedding_dimension(
            _DummyCollectionInfo(1024),
            "esg_docs",
        )
    except RuntimeError as exc:
        assert "Embedding dimension mismatch" in str(exc)
    else:
        raise AssertionError("expected dimension mismatch to raise")


def test_get_embed_model_defaults_to_local_provider(monkeypatch):
    class DummyLocalEmbedding:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def get_dimension(self):
            return self.kwargs["configured_dimension"]

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "demo/local-embed")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "384")
    monkeypatch.setattr(embeddings, "LocalSentenceTransformerEmbedding", DummyLocalEmbedding)
    embeddings.reset_embed_model()

    model = embeddings.get_embed_model()

    assert isinstance(model, DummyLocalEmbedding)
    assert model.kwargs["model_name"] == "demo/local-embed"
    assert embeddings.get_embed_dimension() == 384

    embeddings.reset_embed_model()
