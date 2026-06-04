from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, papers, search
from services.retrieval import RetrievalService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs at startup: loads BM25, reranker, Pinecone — ONCE.
    Without this, request.app.state.retrieval throws AttributeError.
    """
    app.state.retrieval = RetrievalService()
    yield
    # nothing to cleanup on shutdown


app = FastAPI(
    title="PaperSloth Multi-Modal RAG API",
    version="1.0.0",
    lifespan=lifespan,           # ← was missing before
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route prefixes must match exactly what the frontend calls ────────────────
#
#   frontend/src/auth.ts  calls  /auth/register, /auth/login, /auth/me
#   frontend/src/search.ts calls /api/search, /api/subjects, /api/papers
#
#   prefix + router path = final URL
#   "/auth" + "/register"  = /auth/register          ✅
#   "/api"  + "/search"    = /api/search              ✅
#   "/api"  + "/subjects"  = /api/subjects            ✅
#   "/api"  + "/papers"    = /api/papers              ✅

app.include_router(auth.router,    prefix="/auth", tags=["Authentication"])
app.include_router(search.router,  prefix="/api",  tags=["RAG Search"])
app.include_router(papers.router,  prefix="/api",  tags=["Paper Management"])


@app.get("/")
def health_check():
    return {"status": "ok", "message": "PaperSloth API running"}


# Run directly:  python main.py
# Or via uvicorn: cd backend && uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting PaperSloth Backend...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)