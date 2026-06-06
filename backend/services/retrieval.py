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

from services.agents import TUTOR_SYSTEM
from core.config import settings
from core.database import execute_query


class RetrievalService:
    def __init__(self):
        # ── Pinecone ─────────────────────────────────────────────────────────
        pc          = Pinecone(api_key=settings.pinecone_api_key)
        self.index  = pc.Index(settings.pinecone_index)

        # ── Gemini ───────────────────────────────────────────────────────────
        genai.configure(api_key=settings.gemini_api_key)

        self.flash = genai.GenerativeModel(

                        settings.gemini_flash_model,
                        system_instruction=TUTOR_SYSTEM,
        )
        
        self.model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction=(
                "You are a UTP past year exam assistant. "
                "You will be given exam questions and a student query. "
                "Output ONLY the matching question text with its marks and source. "
                "Do not explain, reason, analyse, or compare items. "
                "Do not repeat these instructions. "
                "Begin your response immediately with the answer."
            ),
        )

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
        if semester:      f["semester"]       = {"$eq": semester}  # Pinecone filter unchanged
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
    def _url_to_base64(url: str) -> str:
        """Fetch image from Supabase storage and return as base64 data URI."""
        import requests, base64, mimetypes
        from core.config import settings

        # Fix malformed URL if needed
        clean_url = url.replace("/rest/v1/storage/", "/storage/")

        headers = {
            "apikey": settings.supabase_key,
            "Authorization": f"Bearer {settings.supabase_key}",
        }
        try:
            resp = requests.get(clean_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                mime = resp.headers.get("content-type", "image/png").split(";")[0]
                b64 = base64.b64encode(resp.content).decode()
                return f"data:{mime};base64,{b64}"
        except Exception:
            pass
        return clean_url  # fallback to original URL

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

        results = []
        for r in (rows or []):
            raw_urls = r[4] or {}
            b64_urls = {
                label: RetrievalService._url_to_base64(url)
                for label, url in raw_urls.items()
            }
            results.append({
                "parent_id":       r[0],
                "question_number": r[1],
                "full_text":       r[2],
                "total_marks":     r[3],
                "image_urls":      b64_urls,
                "course_code":     r[5],
                "semester":        r[6],
                "year":            r[7],
            })

        return results
    # ── Build prompt ──────────────────────────────────────────────────────────

    # Generation config shared by every Gemini call.
    # thinking_budget=0 disables chain-of-thought output on Gemini 2.x / Gemma models
    # so the model never leaks its reasoning steps into the response.
    _GEN_CONFIG = {
        "temperature": 0.1,
    }

    @staticmethod
    def _build_prompt(query: str, parents: list[dict]) -> str:
        context_parts = []
        for doc in parents:
            header = (
                f"[{doc['course_code']} | {doc['semester']} {doc['year']} | "
                f"Q{doc['question_number']} | {doc['total_marks']} marks]"
            )
            context_parts.append(f"{header}\n{doc['full_text']}")

        context = "\n\n---\n\n".join(context_parts)

        return f"EXAM QUESTIONS:\n{context}\n\nSTUDENT: {query}"

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

    # ── Strip thinking preamble ───────────────────────────────────────────────
    #
    # Gemma/Gemini thinking models output their chain-of-thought as bullet-point
    # paragraphs before the real answer.  Every thinking line starts with "* ".
    # The actual answer is the first paragraph that isn't all bullet lines.

    @staticmethod
    def _strip_thinking(text: str) -> str:
        """
        Remove chain-of-thought preamble from Gemma/Gemini output.

        The model outputs thinking as bullet lines starting with '*'.
        We skip every leading line that is blank or starts with '*',
        then return everything from the first real content line onward.
        This handles all observed variants:
          - thinking ends with a blank line before the answer
          - answer starts on the line immediately after the last bullet
          - last bullet has the answer text appended inline (we lose that
            inline fragment but keep the clean answer that follows)
        """
        text = text.strip()
        if not text.startswith('*'):
            return text     # no thinking preamble

        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('*'):
                return '\n'.join(lines[i:]).strip()

        return text         # entire response was bullets — return as-is

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

        raw    = self.model.generate_content(prompt, generation_config=self._GEN_CONFIG).text
        answer = self._strip_thinking(raw)
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
        Yields SSE-formatted strings:
          data: {"type":"sources","sources":[...]}   ← appears first
          data: {"type":"token","token":"..."}       ← answer streams in
          data: {"type":"done"}
          data: {"type":"error","message":"..."}
        """
        try:
            parents, prompt = self._run_pipeline(query, filters, top_k, rerank_top_n, alpha)

            if not parents:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No relevant questions found.'})}\n\n"
                return

            slim_sources = [
                {k: v for k, v in p.items() if k != "full_text"}
                for p in parents
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': slim_sources})}\n\n"

            # Buffer the full response so we can strip thinking before the
            # frontend sees a single token.  The latency cost is acceptable —
            # the model was going to finish before meaningful streaming anyway.
            full_text = ""
            for chunk in self.model.generate_content(
                prompt, stream=True, generation_config=self._GEN_CONFIG
            ):
                if chunk.text:
                    full_text += chunk.text

            clean = self._strip_thinking(full_text)

            # Re-stream in small chunks so the frontend still animates
            CHUNK = 40
            for i in range(0, len(clean), CHUNK):
                yield f"data: {json.dumps({'type': 'token', 'token': clean[i:i+CHUNK]})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"