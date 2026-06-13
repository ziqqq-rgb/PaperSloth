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

# If the model's generated answer is essentially just this phrase (after
# stripping thinking/whitespace), treat it as "no match" even though
# retrieval/reranking returned candidates above the relevance threshold.
# This catches cases where the reranker passes lexically-similar-but-
# semantically-unrelated questions, and the generation model (per
# RAG_SYSTEM's RELEVANCE RULE) correctly declines to use them.
_NO_MATCH_PHRASE = "no relevant questions found"


def _model_says_no_match(answer: str) -> bool:
    normalized = answer.strip().strip(".").lower()
    return normalized == _NO_MATCH_PHRASE


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
    def fetch_parents(parent_ids: list[str], include_images: bool = True) -> list[dict]:
        """
        include_images=True (default) preserves prior behaviour for callers
        like fetch_paper/tutor_mode that display one question with its images
        inline. Search/stream pipelines pass include_images=False internally
        — see _run_pipeline.
        """
        return fetch_parents(parent_ids, include_images=include_images)

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

        # Skip base64 image encoding here — for search/stream the frontend
        # can load images from the raw Supabase URLs independently, instead
        # of waiting for every image to be downloaded and embedded into the
        # SSE payload (which previously added several seconds + multiple MB
        # per request).
        parents = fetch_parents(parent_ids, include_images=False)
        prompt  = build_prompt(query, parents)
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

        # The reranker passed candidates above the relevance threshold, but
        # the generation model itself decided none actually match the query
        # (per RAG_SYSTEM's RELEVANCE RULE). In that case, don't show the
        # unrelated sources alongside the "not found" message.
        if _model_says_no_match(answer):
            return {"answer": "No relevant questions found.", "sources": [], "cached": False}

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

            # Generate up-front (non-streamed) so we can check whether the
            # model itself declined to match anything before committing to
            # the 'sources' event. This trades a little perceived latency
            # for not showing unrelated sources next to "not found".
            raw    = self.model.generate_content(prompt, generation_config=_GEN_CONFIG).text
            answer = strip_thinking(raw)

            if _model_says_no_match(answer):
                yield f"data: {json.dumps({'type': 'error', 'message': 'No relevant questions found.'})}\n\n"
                return

            slim_sources = [{k: v for k, v in p.items() if k != "full_text"} for p in parents]
            yield f"data: {json.dumps({'type': 'sources', 'sources': slim_sources})}\n\n"

            CHUNK = 40
            for i in range(0, len(answer), CHUNK):
                yield f"data: {json.dumps({'type': 'token', 'token': answer[i:i+CHUNK]})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"