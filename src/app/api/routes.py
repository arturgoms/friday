"""API routes."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import ChatRequest, ChatResponse, RememberRequest
from app.services.chat import chat_service
from app.services.obsidian import obsidian_service
from app.services.vector_store import vector_store
from app.services.llm import llm_service

router = APIRouter()


def verify_auth(x_api_key: Optional[str] = None):
    """Verify API key if configured."""
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@router.get("/health")
def health_check():
    """Health check endpoint."""
    llm_status = llm_service.health_check()
    stats = vector_store.get_stats()
    
    return {
        "status": "running",
        "llm_status": llm_status,
        "vault_path": str(settings.vault_path),
        "vault_exists": settings.vault_path.exists(),
        **stats,
    }


@router.post("/chat")
def chat(req: ChatRequest, x_api_key: Optional[str] = Header(None)):
    """Main chat endpoint."""
    verify_auth(x_api_key)
    
    try:
        result = chat_service.chat(
            message=req.message,
            session_id=req.session_id,
            use_rag=req.use_rag,
            use_web=req.use_web,
            use_memory=req.use_memory,
            save_memory=req.save_memory,
            stream=req.stream,
        )
        
        if req.stream:
            def generate():
                full_answer = ""
                stream = result["stream"]
                session_id = result["session_id"]
                message = result["message"]
                save_memory = result["save_memory"]
                
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_answer += content
                        yield content
                
                # Update history after streaming
                chat_service.update_history(session_id, message, full_answer)
                
                # Save memory if requested
                if save_memory:
                    mem_text = f"USER: {message}\nASSISTANT: {full_answer}"
                    vector_store.add_memory(mem_text, label="chat")
            
            return StreamingResponse(generate(), media_type="text/plain")
        
        else:
            return ChatResponse(**result)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remember")
def remember(req: RememberRequest, x_api_key: Optional[str] = Header(None)):
    """Create a memory note in Obsidian vault."""
    verify_auth(x_api_key)
    
    try:
        filepath = obsidian_service.create_memory_note(
            content=req.content,
            title=req.title,
            tags=req.tags,
        )
        
        # Index the file immediately
        chunks_indexed = obsidian_service.index_file(filepath)
        
        # Also add to memory collection
        vector_store.add_memory(req.content, label="explicit_memory")
        
        return {
            "status": "success",
            "filepath": str(filepath),
            "chunks_indexed": chunks_indexed,
        }
    
    except Exception as e:
        logger.error(f"Remember endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/reindex")
def reindex_obsidian(x_api_key: Optional[str] = Header(None), sync_nextcloud: bool = False):
    """Rebuild Obsidian index from scratch."""
    verify_auth(x_api_key)
    
    try:
        total = vector_store.rebuild_index()
        
        # Optionally trigger Nextcloud rescan
        if sync_nextcloud:
            logger.info("Triggering Nextcloud file rescan...")
            import subprocess
            result = subprocess.run(
                ["/home/artur/friday/sync_nextcloud.sh"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                logger.info("Nextcloud sync completed")
                return {
                    "status": "ok",
                    "chunks_indexed": total,
                    "nextcloud_synced": True
                }
            else:
                logger.error(f"Nextcloud sync failed: {result.stderr}")
                return {
                    "status": "ok",
                    "chunks_indexed": total,
                    "nextcloud_synced": False,
                    "sync_error": result.stderr
                }
        
        return {"status": "ok", "chunks_indexed": total}
    except Exception as e:
        logger.error(f"Reindex error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/sync-nextcloud")
def sync_nextcloud_files(x_api_key: Optional[str] = Header(None)):
    """Trigger Nextcloud file rescan."""
    verify_auth(x_api_key)
    
    try:
        logger.info("Triggering Nextcloud file rescan...")
        import subprocess
        result = subprocess.run(
            ["/home/artur/friday/sync_nextcloud.sh"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            logger.info("Nextcloud sync completed successfully")
            return {
                "status": "success",
                "message": "Nextcloud files rescanned",
                "output": result.stdout
            }
        else:
            logger.error(f"Nextcloud sync failed: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Nextcloud sync failed: {result.stderr}"
            )
    except subprocess.TimeoutExpired:
        logger.error("Nextcloud sync timed out")
        raise HTTPException(status_code=504, detail="Nextcloud sync timed out")
    except Exception as e:
        logger.error(f"Nextcloud sync error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/debug")
def debug_info(x_api_key: Optional[str] = Header(None)):
    """Get debug information."""
    verify_auth(x_api_key)
    
    files = list(settings.vault_path.rglob("*.md"))
    stats = vector_store.get_stats()
    
    # Check file watcher status
    try:
        from app.services.file_watcher import file_watcher
        watcher_running = file_watcher.observer is not None and file_watcher.observer.is_alive()
        pending_count = len(file_watcher.handler.pending_files)
    except:
        watcher_running = False
        pending_count = 0
    
    return {
        "vault_path": str(settings.vault_path),
        "vault_exists": settings.vault_path.exists(),
        "num_md_files": len(files),
        "sample_files": [str(p) for p in files[:10]],
        "file_watcher_running": watcher_running,
        "pending_files": pending_count,
        **stats,
    }


@router.get("/admin/memories")
def list_memories(x_api_key: Optional[str] = Header(None), limit: int = 100):
    """List all memories."""
    verify_auth(x_api_key)
    
    try:
        memories = vector_store.list_memories(limit=limit)
        return {
            "status": "ok",
            "count": len(memories),
            "memories": memories
        }
    except Exception as e:
        logger.error(f"List memories error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/memories/{memory_id}")
def delete_memory(memory_id: str, x_api_key: Optional[str] = Header(None)):
    """Delete a specific memory."""
    verify_auth(x_api_key)
    
    try:
        vector_store.delete_memory(memory_id)
        return {"status": "ok", "message": f"Memory {memory_id} deleted"}
    except Exception as e:
        logger.error(f"Delete memory error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/memories")
def clear_explicit_memories(x_api_key: Optional[str] = Header(None)):
    """Clear only explicit memories (not chat history)."""
    verify_auth(x_api_key)
    
    try:
        count = vector_store.clear_explicit_memories()
        return {"status": "ok", "message": f"Cleared {count} explicit memories"}
    except Exception as e:
        logger.error(f"Clear explicit memories error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/memories/all")
def clear_all_memories(x_api_key: Optional[str] = Header(None)):
    """Clear ALL memories including chat history (nuclear option)."""
    verify_auth(x_api_key)
    
    try:
        count = vector_store.clear_all_memories()
        return {"status": "ok", "message": f"Cleared {count} total memories"}
    except Exception as e:
        logger.error(f"Clear all memories error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
