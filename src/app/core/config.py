"""Application configuration."""
import os
from pathlib import Path
from typing import Optional
from datetime import timezone, timedelta
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    """Application settings."""
    
    # Paths
    vault_path: Path = Path(os.getenv("VAULT_PATH", str(Path.home() / "my-brain")))
    memory_path: Path = Path(os.getenv("MEMORY_PATH", str(Path.home() / "my-brain" / "1. Notes")))
    chroma_path: Path = Path("/home/artur/friday/data/chroma_db")
    
    # Models
    embed_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embed_device: str = "cpu"  # Keep embeddings on CPU to save GPU for LLM
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-14B-Instruct")
    
    # Auth
    api_key: Optional[str] = os.getenv("FRIDAY_API_KEY", None)
    authorized_user: str = "artur"
    
    # Timezone (UTC-3 / BRT - Brasília Time)
    timezone_offset_hours: int = -3
    
    # RAG parameters
    top_k_obsidian: int = 5
    neighbor_range: int = 1
    top_k_web: int = 4
    top_k_memory: int = 5
    max_conversation_history: int = 10
    
    # Chunking
    chunk_max_chars: int = 2000
    chunk_overlap: int = 200
    
    # LLM
    llm_temperature: float = 0.3
    
    class Config:
        env_file = ".env"
    
    @property
    def user_timezone(self):
        """Get user's timezone as a timezone object."""
        return timezone(timedelta(hours=self.timezone_offset_hours))


settings = Settings()
