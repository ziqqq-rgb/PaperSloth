from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # APIs
    gemini_api_key: str = os.getenv("GEMINI_API_KEY")
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY")
    supabase_url: str = os.getenv("SUPABASE_URL")
    supabase_key: str = os.getenv("SUPABASE_KEY")

    # Database & cache
    database_url: str = os.getenv("DATABASE_URL")
    redis_url: str = os.getenv("REDIS_URL")

    # Models
    bm25_model_path: str = "../rag pipeline/data/bm25_model.pkl"
    embed_model:     str = "nomic-embed-text-v2-moe:latest"
    gemini_model:    str = "gemma-4-31b-it"
    reranker_model:  str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    pinecone_index:  str = "papersloth"

    # Auth
    jwt_secret: str = os.getenv("JWT_SECRET_KEY")
    jwt_expire_hours: int = 24

    gemini_flash_model: str = "gemini-3.1-flash-lite"   
    gemini_model:       str = "gemma-4-31b-it" 

    class Config:
        env_file = ".env"


settings = Settings()