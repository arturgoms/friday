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
        """Load all markdown files from vault and Friday's About folder."""
        docs = []
        
        # Load from main vault (1. Notes)
        vault_files = list(settings.vault_path.rglob("*.md"))
        for f in vault_files:
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = f.read_text(errors="ignore")
            docs.append({"path": str(f), "text": text})
        
        # Also load Friday's About folder (5.0 About) for "Who are you?" queries
        if settings.about_path.exists():
            about_files = list(settings.about_path.rglob("*.md"))
            for f in about_files:
                try:
                    text = f.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    text = f.read_text(errors="ignore")
                docs.append({"path": str(f), "text": text})
            logger.info(f"Loaded {len(about_files)} documents from About folder")
        
        logger.info(f"Loaded {len(docs)} total documents for indexing")
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
    
    def create_note(
        self,
        title: str,
        content: str,
        folder: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Path:
        """
        Create a new note in the vault.
        
        Args:
            title: Note title (will be used as filename)
            content: Note content (markdown)
            folder: Optional subfolder within vault
            tags: Optional list of tags for frontmatter
            
        Returns:
            Path to the created file
        """
        filename = self.sanitize_filename(title) + ".md"
        
        if folder:
            target_dir = settings.vault_path / folder
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = settings.vault_path
        
        filepath = target_dir / filename
        
        # Handle duplicate filenames
        counter = 1
        while filepath.exists():
            filename = f"{self.sanitize_filename(title)}_{counter}.md"
            filepath = target_dir / filename
            counter += 1
        
        # Build frontmatter
        frontmatter_lines = ["---"]
        frontmatter_lines.append(f"created: {datetime.now().isoformat()}")
        frontmatter_lines.append(f"title: {title}")
        if tags:
            tags_str = ", ".join(tags)
            frontmatter_lines.append(f"tags: [{tags_str}]")
        frontmatter_lines.append("---")
        frontmatter_lines.append("")
        frontmatter_lines.append(f"# {title}")
        frontmatter_lines.append("")
        
        full_content = "\n".join(frontmatter_lines) + content
        
        try:
            filepath.write_text(full_content, encoding="utf-8")
            logger.info(f"Created note: {filepath}")
            
            # Index the new note
            self.index_file(filepath)
            
            return filepath
        except Exception as e:
            logger.error(f"Failed to create note: {e}")
            raise
    
    def update_note(
        self,
        title: str,
        new_content: str,
        append: bool = False,
    ) -> Optional[Path]:
        """
        Update an existing note by title.
        
        Args:
            title: Note title to search for
            new_content: New content to write or append
            append: If True, append to existing content; if False, replace
            
        Returns:
            Path to the updated file, or None if not found
        """
        # Search for matching file
        search_name = self.sanitize_filename(title)
        matches = []
        
        for f in settings.vault_path.rglob("*.md"):
            fname = f.stem.lower()
            if search_name.lower() in fname or title.lower() in fname:
                matches.append(f)
        
        if not matches:
            logger.warning(f"Note not found: {title}")
            return None
        
        # Use the best match (exact match preferred)
        filepath = matches[0]
        for m in matches:
            if m.stem.lower() == search_name.lower() or m.stem.lower() == title.lower():
                filepath = m
                break
        
        try:
            existing_content = filepath.read_text(encoding="utf-8")
            
            # SAFETY: Create backup before any modification
            backup_path = filepath.with_suffix('.md.bak')
            backup_path.write_text(existing_content, encoding="utf-8")
            logger.info(f"Created backup: {backup_path}")
            
            # SAFETY: Always append, never replace (to prevent accidental data loss)
            # The 'append' parameter is kept for API compatibility but ignored
            if not append:
                logger.warning(f"Replace mode requested but forcing append for safety")
            
            updated_content = existing_content.rstrip() + "\n\n" + new_content
            
            filepath.write_text(updated_content, encoding="utf-8")
            logger.info(f"Updated note: {filepath}")
            
            # Re-index the updated note
            self.index_file(filepath)
            
            return filepath
        except Exception as e:
            logger.error(f"Failed to update note: {e}")
            raise
    
    def search_notes(self, query: str, limit: int = 5) -> List[dict]:
        """
        Search notes by filename/title.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching notes with path and preview
        """
        results = []
        query_lower = query.lower()
        
        for f in settings.vault_path.rglob("*.md"):
            fname = f.stem.lower()
            if query_lower in fname:
                try:
                    content = f.read_text(encoding="utf-8")
                    # Get first 200 chars of content (skip frontmatter)
                    preview = content
                    if "---" in content:
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            preview = parts[2]
                    preview = preview.strip()[:200]
                    
                    results.append({
                        "path": str(f),
                        "title": f.stem,
                        "preview": preview
                    })
                except Exception as e:
                    logger.error(f"Error reading {f}: {e}")
        
        return results[:limit]
    
    def get_note(self, title: str) -> Optional[dict]:
        """
        Get a note by title.
        
        Args:
            title: Note title to search for
            
        Returns:
            Dict with path, title, and content, or None if not found
        """
        search_name = self.sanitize_filename(title)
        
        for f in settings.vault_path.rglob("*.md"):
            fname = f.stem.lower()
            if search_name.lower() in fname or title.lower() in fname:
                try:
                    content = f.read_text(encoding="utf-8")
                    return {
                        "path": str(f),
                        "title": f.stem,
                        "content": content
                    }
                except Exception as e:
                    logger.error(f"Error reading {f}: {e}")
                    return None
        
        return None
    
    def list_notes(self, folder: Optional[str] = None, limit: int = 20) -> List[dict]:
        """
        List notes in the vault.
        
        Args:
            folder: Optional subfolder to list
            limit: Maximum number of results
            
        Returns:
            List of notes with path and title
        """
        if folder:
            search_path = settings.vault_path / folder
        else:
            search_path = settings.vault_path
        
        results = []
        for f in search_path.rglob("*.md"):
            results.append({
                "path": str(f),
                "title": f.stem
            })
        
        # Sort by modification time (newest first)
        results.sort(key=lambda x: Path(x["path"]).stat().st_mtime, reverse=True)
        
        return results[:limit]


# Singleton instance
obsidian_service = ObsidianService()
