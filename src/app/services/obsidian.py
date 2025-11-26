"""Obsidian vault service."""
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger


class ObsidianService:
    """Service for Obsidian vault operations."""
    
    def __init__(self):
        """Initialize Obsidian service."""
        if not settings.vault_path.exists():
            raise RuntimeError(f"Vault path does not exist: {settings.vault_path}")
        
        if not settings.memory_path.exists():
            settings.memory_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created memory path: {settings.memory_path}")
        
        logger.info(f"Obsidian service initialized: {settings.vault_path}")
    
    def load_all_documents(self) -> List[dict]:
        """Load all markdown files from vault."""
        files = list(settings.vault_path.rglob("*.md"))
        docs = []
        for f in files:
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = f.read_text(errors="ignore")
            docs.append({"path": str(f), "text": text})
        logger.info(f"Loaded {len(docs)} documents from vault")
        return docs
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Markdown-aware chunking.
        Split by headings and handle long sections.
        """
        max_chars = settings.chunk_max_chars
        overlap = settings.chunk_overlap
        
        lines = text.splitlines()
        sections: List[str] = []
        current_heading: list[str] = []
        current_body: list[str] = []
        
        def flush_section():
            if not current_heading and not current_body:
                return
            section_text = ""
            if current_heading:
                section_text += "\n".join(current_heading) + "\n"
            if current_body:
                section_text += "\n".join(current_body)
            section_text = section_text.strip()
            if section_text:
                sections.append(section_text)
        
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                flush_section()
                current_heading.clear()
                current_body.clear()
                current_heading.append(line)
            else:
                current_body.append(line)
        
        flush_section()
        
        if not sections:
            sections = [text]
        
        chunks: List[str] = []
        
        for section in sections:
            if len(section) <= max_chars:
                chunks.append(section)
            else:
                start = 0
                n = len(section)
                while start < n:
                    end = min(start + max_chars, n)
                    chunk = section[start:end]
                    chunks.append(chunk)
                    if end == n:
                        break
                    start = end - overlap
        
        return chunks
    
    @staticmethod
    def sanitize_filename(title: str) -> str:
        """Convert title to valid filename."""
        title = re.sub(r'[<>:"/\\|?*]', '', title)
        title = title.replace(' ', '_')
        return title[:100]
    
    def create_memory_note(
        self,
        content: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Path:
        """Create a memory note in the vault."""
        if not title:
            first_line = content.split('\n')[0][:50]
            title = first_line if first_line else f"Memory_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        filename = self.sanitize_filename(title) + ".md"
        filepath = settings.memory_path / filename
        
        counter = 1
        while filepath.exists():
            filename = f"{self.sanitize_filename(title)}_{counter}.md"
            filepath = settings.memory_path / filename
            counter += 1
        
        frontmatter_lines = ["---"]
        frontmatter_lines.append(f"created: {datetime.now().isoformat()}")
        frontmatter_lines.append("type: memory")
        if tags:
            tags_str = ", ".join(tags)
            frontmatter_lines.append(f"tags: [{tags_str}]")
        frontmatter_lines.append("---")
        frontmatter_lines.append("")
        
        full_content = "\n".join(frontmatter_lines) + "\n" + content
        
        try:
            filepath.write_text(full_content, encoding="utf-8")
            logger.info(f"Created memory note: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to create memory note: {e}")
            raise
    
    def index_file(self, filepath: Path):
        """Index a single file into vector store."""
        from app.services.vector_store import vector_store
        from app.services.embeddings import embedding_service
        
        try:
            text = filepath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = filepath.read_text(errors="ignore")
        
        chunks = self.chunk_text(text)
        if not chunks:
            # Remove from index if file now has no content
            vector_store.remove_file(str(filepath))
            return 0
        
        embeddings = embedding_service.embed_texts(chunks)
        
        # Update (remove old + add new) instead of just adding
        vector_store.update_file(str(filepath), chunks, embeddings)
        logger.info(f"Indexed {len(chunks)} chunks from {filepath}")
        return len(chunks)


# Singleton instance
obsidian_service = ObsidianService()
