"""
services/retrieval/__init__.py
──────────────────────────────
RetrievalService: the single object instantiated at startup (lifespan) and
stored on app.state.retrieval.

Public API (unchanged):
    svc.build_filter(...)  → dict
    svc.search(...)        → dict
    svc.stream(...)        → Generator[str]
    svc.fetch_parents(...) → list[dict]   (used by agents)
"""

import json
import pickle
from pathlib import Path
from typing import Generator, Optional

from pinecone import Pinecone

from core.config import settings
from services.retrieval.embed import embed_query, hybrid_scale
from services.retrieval.generate import (
    _GEN_CONFIG,
    build_prompt,
    build_rag_model,
    build_tutor_model,
    stream_text,
    strip_thinking,
)
from services.retrieval.search import (
    build_filter,
    build_reranker,
    fetch_parents,
    rerank,
)


class RetrievalService:
    def __init__(self):
        # ── Pinecone ─────────────────────────────────────────────────────────
        pc         = Pinecone(api_key=settings.pinecone_api_key)
        self.index = pc.Index(settings.pinecone_index)

        # ── Gemini models ─────────────────────────────────────────────────────
        self.model = build_rag_model()
        self.flash = build_tutor_model()

        # ── BM25 ─────────────────────────────────────────────────────────────
        bm25_path = Path(settings.bm25_model_path)
        if not bm25_path.exists():
            raise FileNotFoundError(
                f"BM25 model not found at {bm25_path}. "
                "Run 01b_batch_ingest.ipynb Section 6 first."
            )
        with open(bm25_path, "rb") as f:
            self.bm25 = pickle.load(f)

        # ── Cross-encoder reranker ────────────────────────────────────────────
        self._reranker = build_reranker()

        print("✅ RetrievalService ready")

    # ── Delegate to module-level functions ────────────────────────────────────

    def build_filter(
        self,
        course_code:   Optional[str] = None,
        year:          Optional[int] = None,
        semester:      Optional[str] = None,
        question_type: Optional[str] = None,
        min_marks:     Optional[int] = None,
    ) -> dict:
        return build_filter(course_code, year, semester, question_type, min_marks)

    @staticmethod
    def fetch_parents(parent_ids: list[str]) -> list[dict]:
        return fetch_parents(parent_ids)

    # ── Core pipeline (shared by search + stream) ─────────────────────────────

    def _run_pipeline(
        self,
        query:        str,
        filters:      dict,
        top_k:        int   = 20,
        rerank_top_n: int   = 5,
        alpha:        float = 0.7,
    ) -> tuple[list[dict], str]:
        dense  = embed_query(query)
        sparse = self.bm25.encode_queries([query])[0]
        d, s   = hybrid_scale(dense, sparse, alpha)

        results = self.index.query(
            vector           = d,
            sparse_vector    = s,
            top_k            = top_k,
            include_metadata = True,
            filter           = filters or None,
        )

        if not results.matches:
            return [], ""

        top_matches = rerank(self._reranker, query, results.matches, top_n=rerank_top_n)
        parent_ids  = list({m.metadata["parent_id"] for m in top_matches})
        parents     = fetch_parents(parent_ids)
        prompt      = build_prompt(query, parents)
        return parents, prompt

    # ── Standard search ───────────────────────────────────────────────────────

    def search(
        self,
        query:        str,
        filters:      dict,
        top_k:        int   = 20,
        rerank_top_n: int   = 5,
        alpha:        float = 0.7,
    ) -> dict:
        parents, prompt = self._run_pipeline(query, filters, top_k, rerank_top_n, alpha)

        if not parents:
            return {"answer": "No relevant questions found.", "sources": [], "cached": False}

        raw    = self.model.generate_content(prompt, generation_config=_GEN_CONFIG).text
        answer = strip_thinking(raw)
        return {"answer": answer, "sources": parents, "cached": False}

    # ── Streaming search (SSE) ────────────────────────────────────────────────

    def stream(
        self,
        query:        str,
        filters:      dict,
        top_k:        int   = 20,
        rerank_top_n: int   = 5,
        alpha:        float = 0.7,
    ) -> Generator[str, None, None]:
        """
        Yields SSE strings:
          data: {"type":"sources","sources":[...]}
          data: {"type":"token","token":"..."}
          data: {"type":"done"}
          data: {"type":"error","message":"..."}
        """
        try:
            parents, prompt = self._run_pipeline(query, filters, top_k, rerank_top_n, alpha)

            if not parents:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No relevant questions found.'})}\n\n"
                return

            slim_sources = [{k: v for k, v in p.items() if k != "full_text"} for p in parents]
            yield f"data: {json.dumps({'type': 'sources', 'sources': slim_sources})}\n\n"

            yield from stream_text(self.model, prompt)

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"