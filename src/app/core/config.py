"""Application configuration."""
import os
from pathlib import Path
from typing import Optional
from datetime import timezone, timedelta
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


# Brain paths (Syncthing synced folder)
BRAIN_PATH = Path(os.getenv("BRAIN_PATH", str(Path.home() / "friday" / "brain")))


class Settings(BaseModel):
    """Application settings."""
    
    # Brain Paths (Syncthing synced - editable in Obsidian)
    brain_path: Path = BRAIN_PATH
    
    # RAG Knowledge Base (read-only for Friday)
    vault_path: Path = BRAIN_PATH / "1. Notes"
    
    # Friday's Data (read-write for Friday)
    friday_path: Path = BRAIN_PATH / "5. Friday"
    about_path: Path = BRAIN_PATH / "5. Friday" / "5.0 About"
    memories_path: Path = BRAIN_PATH / "5. Friday" / "5.1 Memories"
    journal_path: Path = BRAIN_PATH / "5. Friday" / "5.2 Journal"
    reports_path: Path = BRAIN_PATH / "5. Friday" / "5.3 Reports"
    reminders_path: Path = BRAIN_PATH / "5. Friday" / "5.4 Reminders"
    
    # User identity file (for "Who am I?" queries)
    user_profile_file: str = "Artur Gomes.md"
    
    # Legacy paths (kept for backwards compatibility)
    memory_path: Path = BRAIN_PATH / "5. Friday" / "5.1 Memories"
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
