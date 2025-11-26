"""File watcher for automatic reindexing."""
import time
from pathlib import Path
from typing import Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from app.core.config import settings
from app.core.logging import logger


class MarkdownFileHandler(FileSystemEventHandler):
    """Handler for markdown file changes."""
    
    def __init__(self):
        """Initialize handler."""
        self.pending_files: Set[Path] = set()
        self.last_process_time = time.time()
        self.debounce_seconds = 5  # Wait 5 seconds after last change
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if path.suffix == '.md':
            self.pending_files.add(path)
            logger.info(f"Detected change: {path}")
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if path.suffix == '.md':
            self.pending_files.add(path)
            logger.info(f"Detected new file: {path}")
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if path.suffix == '.md':
            # Remove from vector store
            from app.services.vector_store import vector_store
            try:
                vector_store.remove_file(str(path))
                logger.info(f"Removed from index: {path}")
            except Exception as e:
                logger.error(f"Failed to remove from index: {e}")
    
    def get_pending_files(self) -> Set[Path]:
        """Get and clear pending files if debounce period passed."""
        now = time.time()
        if self.pending_files and (now - self.last_process_time) >= self.debounce_seconds:
            files = self.pending_files.copy()
            self.pending_files.clear()
            self.last_process_time = now
            return files
        return set()


class FileWatcher:
    """Service for watching file changes."""
    
    def __init__(self):
        """Initialize file watcher."""
        self.observer = None
        self.handler = MarkdownFileHandler()
    
    def start(self):
        """Start watching the vault."""
        if self.observer is not None:
            logger.warning("File watcher already running")
            return
        
        self.observer = Observer()
        self.observer.schedule(
            self.handler,
            str(settings.vault_path),
            recursive=True
        )
        self.observer.start()
        logger.info(f"File watcher started on {settings.vault_path}")
    
    def stop(self):
        """Stop watching."""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("File watcher stopped")
    
    def process_pending_files(self):
        """Process any pending file changes."""
        pending = self.handler.get_pending_files()
        if not pending:
            return 0
        
        from app.services.obsidian import obsidian_service
        
        indexed_count = 0
        for filepath in pending:
            try:
                if filepath.exists():
                    chunks = obsidian_service.index_file(filepath)
                    indexed_count += chunks
                    logger.info(f"Reindexed {filepath}: {chunks} chunks")
            except Exception as e:
                logger.error(f"Failed to index {filepath}: {e}")
        
        if indexed_count > 0:
            logger.info(f"Processed {len(pending)} files, indexed {indexed_count} chunks")
        
        return indexed_count


# Singleton instance
file_watcher = FileWatcher()
