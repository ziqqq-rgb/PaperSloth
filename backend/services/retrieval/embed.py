import ollama
from core.config import settings


def embed_query(text: str) -> list[float]:
    resp = ollama.embed(
        model=settings.embed_model,
        input=f"search_query: {text}",
    )
    return resp["embeddings"][0]


def hybrid_scale(
    dense: list[float],
    sparse: dict,
    alpha: float,
) -> tuple[list[float], dict]:
    """
    Scale dense and sparse vectors by alpha so they sum to 1.
    alpha=1 → dense only, alpha=0 → sparse only.
    """
    return (
        [v * alpha for v in dense],
        {
            "indices": sparse["indices"],
            "values":  [v * (1 - alpha) for v in sparse["values"]],
        },
    )