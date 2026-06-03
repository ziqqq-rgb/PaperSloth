"""
services/retrieval.py
─────────────────────
Wraps the full RAG pipeline from 02_retrieval.ipynb into a class.
Heavy objects (reranker, BM25, Pinecone) are loaded ONCE at startup
via the lifespan hook in main.py — not per request.
"""

import json
import pickle
import re
from collections import deque
from pathlib import Path
from typing import Generator, Optional

import google.generativeai as genai
import ollama
from pinecone import Pinecone
from sentence_transformers import CrossEncoder

from core.config import settings
from core.database import execute_query


class RetrievalService:
    def __init__(self):
        # ── Pinecone ─────────────────────────────────────────────────────────
        pc          = Pinecone(api_key=settings.pinecone_api_key)
        self.index  = pc.Index(settings.pinecone_index)

        # ── Gemini ───────────────────────────────────────────────────────────
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

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
        self.reranker = CrossEncoder(settings.reranker_model)

        print("✅ RetrievalService ready")

    # ── Embedding ─────────────────────────────────────────────────────────────

    def embed_query(self, text: str) -> list[float]:
        resp = ollama.embed(
            model=settings.embed_model,
            input=f"search_query: {text}",
        )
        return resp["embeddings"][0]

    # ── Hybrid scale ──────────────────────────────────────────────────────────

    @staticmethod
    def _hybrid_scale(dense: list, sparse: dict, alpha: float):
        return (
            [v * alpha for v in dense],
            {
                "indices": sparse["indices"],
                "values":  [v * (1 - alpha) for v in sparse["values"]],
            },
        )

    # ── Metadata filter builder ───────────────────────────────────────────────

    @staticmethod
    def build_filter(
        course_code:   Optional[str] = None,
        year:          Optional[int] = None,
        semester:      Optional[str] = None,
        question_type: Optional[str] = None,
        min_marks:     Optional[int] = None,
    ) -> dict:
        f = {}
        if course_code:   f["course_code"]   = {"$eq": course_code}
        if year:          f["year"]           = {"$eq": year}
        if semester:      f["semester"]       = {"$eq": semester}
        if question_type: f["question_type"]  = {"$eq": question_type}
        if min_marks:     f["marks"]          = {"$gte": min_marks}
        return f

    # ── Rerank ────────────────────────────────────────────────────────────────

    def rerank(self, query: str, matches: list, top_n: int = 5) -> list:
        if not matches:
            return []
        passages = [m.metadata.get("text_preview", "") for m in matches]
        scores   = self.reranker.predict([(query, p) for p in passages])
        ranked   = sorted(zip(matches, scores), key=lambda x: x[1], reverse=True)
        return [m for m, _ in ranked[:top_n]]

    # ── Parent fetch ──────────────────────────────────────────────────────────

    @staticmethod
    def fetch_parents(parent_ids: list[str]) -> list[dict]:
        if not parent_ids:
            return []
        rows = execute_query(
            """
            SELECT parent_id, question_number, full_text, total_marks,
                   image_urls, course_code, semester, year
            FROM   parent_chunks
            WHERE  parent_id = ANY(%s)
            """,
            (parent_ids,),
        )
        return [
            {
                "parent_id":       r[0],
                "question_number": r[1],
                "full_text":       r[2],
                "total_marks":     r[3],
                "image_urls":      r[4] or {},
                "course_code":     r[5],
                "semester":        r[6],
                "year":            r[7],
            }
            for r in (rows or [])
        ]

    # ── Build prompt ──────────────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(query: str, parents: list[dict]) -> str:
        system = (
            "You are PaperSloth, a study assistant for UTP students. "
            "You help students find and understand past year exam questions.\n"
            "When answering:\n"
            "- Present questions with their number and marks\n"
            "- Always state which semester/year the question is from\n"
            "- If no relevant questions are found, say so clearly\n"
            "- Do not make up questions\n"
        )
        context_parts = []
        for doc in parents:
            header = (
                f"[{doc['course_code']} | {doc['semester']} {doc['year']} | "
                f"Q{doc['question_number']} | {doc['total_marks']} marks]"
            )
            context_parts.append(f"{header}\n{doc['full_text']}")

        return (
            f"{system}\n\nPAST YEAR QUESTIONS:\n"
            + "\n\n---\n\n".join(context_parts)
            + f"\n\nSTUDENT QUERY: {query}\n\nAnswer:"
        )

    # ── Core pipeline ─────────────────────────────────────────────────────────

    def _run_pipeline(
        self,
        query:         str,
        filters:       dict,
        top_k:         int   = 20,
        rerank_top_n:  int   = 5,
        alpha:         float = 0.7,
    ) -> tuple[list[dict], str]:
        """
        Returns (parents, prompt) — shared by both search() and stream().
        """
        dense  = self.embed_query(query)
        sparse = self.bm25.encode_queries([query])[0]
        d, s   = self._hybrid_scale(dense, sparse, alpha)

        results = self.index.query(
            vector           = d,
            sparse_vector    = s,
            top_k            = top_k,
            include_metadata = True,
            filter           = filters or None,
        )

        if not results.matches:
            return [], ""

        top_matches = self.rerank(query, results.matches, top_n=rerank_top_n)
        parent_ids  = list({m.metadata["parent_id"] for m in top_matches})
        parents     = self.fetch_parents(parent_ids)
        prompt      = self._build_prompt(query, parents)
        return parents, prompt

    # ── Standard (non-streaming) search ──────────────────────────────────────

    def search(
        self,
        query:         str,
        filters:       dict,
        top_k:         int   = 20,
        rerank_top_n:  int   = 5,
        alpha:         float = 0.7,
    ) -> dict:
        parents, prompt = self._run_pipeline(query, filters, top_k, rerank_top_n, alpha)

        if not parents:
            return {"answer": "No relevant questions found.", "sources": [], "cached": False}

        answer = self.model.generate_content(prompt).text
        return {
            "answer":  answer,
            "sources": parents,
            "cached":  False,
        }

    # ── Streaming search (SSE) ────────────────────────────────────────────────

    def stream(
        self,
        query:         str,
        filters:       dict,
        top_k:         int   = 20,
        rerank_top_n:  int   = 5,
        alpha:         float = 0.7,
    ) -> Generator[str, None, None]:
        """
        Yields SSE-formatted strings.
        Frontend receives:
          data: {"type":"sources","sources":[...]}   ← appears first
          data: {"type":"token","token":"Based"}     ← answer streams in
          data: {"type":"done"}                      ← stream complete
          data: {"type":"error","message":"..."}     ← on failure
        """
        try:
            parents, prompt = self._run_pipeline(query, filters, top_k, rerank_top_n, alpha)

            if not parents:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No relevant questions found.'})}\n\n"
                return

            # Send sources first — frontend can render them immediately
            slim_sources = [
                {k: v for k, v in p.items() if k != "full_text"}
                for p in parents
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': slim_sources})}\n\n"

            # Stream tokens from Gemini
            for chunk in self.model.generate_content(prompt, stream=True):
                if chunk.text:
                    yield f"data: {json.dumps({'type': 'token', 'token': chunk.text})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"