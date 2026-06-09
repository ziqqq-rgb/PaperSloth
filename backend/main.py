from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, papers, search
from services.retrieval import RetrievalService


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.retrieval = RetrievalService()
    yield

app = FastAPI(
    title="PaperSloth Multi-Modal RAG API",
    version="1.0.0",
    lifespan=lifespan,         
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,    prefix="/auth", tags=["Authentication"])
app.include_router(search.router,  prefix="/api",  tags=["RAG Search"])
app.include_router(papers.router,  prefix="/api",  tags=["Paper Management"])


@app.get("/")
def health_check():
    return {"status": "ok", "message": "PaperSloth API running"}

if __name__ == "__main__":
    import uvicorn
    print("Starting PaperSloth Backend...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)