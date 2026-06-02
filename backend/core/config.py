from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # APIs
    gemini_api_key:  str
    pinecone_api_key: str
    supabase_url:    str = ""
    supabase_key:    str = ""

    # Database & cache
    database_url:    str
    redis_url:       str = "redis://localhost:6379"

    # Models
    bm25_model_path: str = "../rag pipeline/data/bm25_model.pkl"
    embed_model:     str = "nomic-embed-text-v2-moe:latest"
    gemini_model:    str = "gemma-4-31b-it"
    reranker_model:  str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    pinecone_index:  str = "papersloth"

    # Auth
    jwt_secret:       str = "3a24fe028611789807cfaf5430e5392c6bc3f2d619022149d427743df4625f49"
    jwt_expire_hours: int = 24

    class Config:
        env_file = ".env"


settings = Settings()