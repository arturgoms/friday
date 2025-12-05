"""Obsidian vault service."""
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
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
        
        # Lazy-load obsidian_knowledge to avoid circular imports
        self._knowledge = None
        
        logger.info(f"Obsidian service initialized: {settings.vault_path}")
    
    @property
    def knowledge(self):
        """Lazy load ObsidianKnowledge."""
        if self._knowledge is None:
            from app.services.obsidian_knowledge import obsidian_knowledge
            self._knowledge = obsidian_knowledge
        return self._knowledge
    
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
        base_path: Optional[Path] = None,
    ) -> Path:
        """
        Create a new note in the vault.
        
        Args:
            title: Note title (will be used as filename)
            content: Note content (markdown)
            folder: Optional subfolder within vault (relative to base_path)
            tags: Optional list of tags for frontmatter
            base_path: Base path for the note. Defaults to brain_path.
            
        Returns:
            Path to the created file
        """
        filename = self.sanitize_filename(title) + ".md"
        
        # Use brain_path as default base (covers all folders: 0-5)
        base = base_path or settings.brain_path
        
        if folder:
            target_dir = base / folder
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = base
        
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
    
    def create_note_smart(
        self,
        title: str,
        content: str,
        note_type: Optional[str] = None,
        additional_tags: Optional[List[str]] = None,
        use_template: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a note using Obsidian knowledge to auto-select folder and tags.
        
        This is the preferred method for creating notes as it follows the
        user's Obsidian conventions automatically.
        
        Args:
            title: Note title
            content: Note content (markdown)
            note_type: Type of note (daily, meeting, memory, journal, idea, note, etc.)
                       If None, defaults to 'note' which goes to Inbox
            additional_tags: Extra tags to add beyond auto-detected ones
            use_template: If True, use appropriate template if available
            
        Returns:
            Dict with:
                - path: Path to created file
                - folder: Folder used
                - tags: Tags applied
                - template_used: Name of template used (if any)
        """
        note_type = note_type or "note"
        
        # Get folder and tags from obsidian knowledge
        folder = self.knowledge.get_folder_for_note_type(note_type)
        tags = self.knowledge.get_tags_for_note_type(note_type)
        
        # Add content-based tag suggestions
        suggested_tags = self.knowledge.suggest_tags_for_content(content, title)
        for tag in suggested_tags:
            if tag not in tags:
                tags.append(tag)
        
        # Add any additional tags
        if additional_tags:
            for tag in additional_tags:
                if tag not in tags:
                    tags.append(tag)
        
        # Check for template
        template_used = None
        template_content = None
        if use_template:
            # Map note types to template names
            template_map = {
                "daily": "Friday Journal",
                "journal": "Friday Journal",
                "memory": "Friday Memory",
                "report": "Friday Report",
                "reminder": "Friday Reminder",
                "idea": "Friday Idea",
                "meeting": "Meeting",  # User's meeting template
            }
            template_name = template_map.get(note_type)
            if template_name:
                template_content = self.knowledge.get_template(template_name)
                if template_content:
                    template_used = template_name
        
        # Build the note content
        if template_content:
            # Process template - replace placeholders
            processed_template = self._process_template(template_content, {
                "title": title,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.now().strftime("%H:%M"),
                "content": content,
            })
            final_content = processed_template
        else:
            final_content = content
        
        # Create the note using the standard method
        filepath = self.create_note(
            title=title,
            content=final_content,
            folder=folder,
            tags=tags,
        )
        
        return {
            "path": filepath,
            "folder": folder,
            "tags": tags,
            "template_used": template_used,
        }
    
    def _process_template(self, template: str, variables: Dict[str, str]) -> str:
        """
        Process a template by replacing placeholders.
        
        Handles common template patterns:
        - {{date}}, {{time}}, {{title}}
        - Templater syntax: <% tp.date.now() %>
        """
        result = template
        
        # Remove frontmatter from template (we build our own)
        if result.startswith("---"):
            end_fm = result.find("---", 3)
            if end_fm != -1:
                result = result[end_fm + 3:].strip()
        
        # Replace simple placeholders
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)
            result = result.replace(f"{{{{ {key} }}}}", value)
        
        # Handle Templater date syntax (common patterns)
        result = re.sub(
            r'<%\s*tp\.date\.now\(\s*["\']?YYYY-MM-DD["\']?\s*\)\s*%>',
            variables.get("date", datetime.now().strftime("%Y-%m-%d")),
            result
        )
        result = re.sub(
            r'<%\s*tp\.date\.now\(\s*\)\s*%>',
            variables.get("date", datetime.now().strftime("%Y-%m-%d")),
            result
        )
        result = re.sub(
            r'<%\s*tp\.file\.title\s*%>',
            variables.get("title", ""),
            result
        )
        
        # If content variable provided and template has a content section, insert it
        content = variables.get("content", "")
        if content:
            # Look for common content markers
            if "## Content" in result:
                result = result.replace("## Content\n", f"## Content\n{content}\n")
            elif "## Notes" in result:
                result = result.replace("## Notes\n", f"## Notes\n{content}\n")
            elif not any(marker in result for marker in ["## ", "### "]):
                # If no sections, append content
                result = result + "\n" + content
        
        return result
    
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
