from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, papers, search
import uvicorn

app = FastAPI(title="PaperSloth Multi-Modal RAG API", version="1.0.0")

# --- CORS Configuration ---
# This is required so your Vite React frontend (running on port 5173) 
# can securely make API calls to this backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(search.router, prefix="/api/search", tags=["RAG Search"])
app.include_router(papers.router, prefix="/api/papers", tags=["Paper Management"])

# --- Health Check Route ---
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Welcome to the PaperSloth API!"}



def main():
    print("🚀 Starting PaperSloth Backend Server...")
    # This points to the 'app' object inside 'backend/main.py'
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()