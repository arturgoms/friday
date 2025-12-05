"""API routes."""
import json
import time
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import (
    ChatRequest, ChatResponse, RememberRequest,
    TaskCreate, TaskUpdate, TaskResponse
)
from app.services.chat import chat_service
from app.services.obsidian import obsidian_service
from app.services.vector_store import vector_store
from app.services.llm import llm_service
from app.services.task_manager import task_manager

router = APIRouter()


# ===== OpenAI-Compatible API for OpenWebUI =====

class OpenAIMessage(BaseModel):
    role: str
    content: str

class OpenAIChatRequest(BaseModel):
    model: str = "friday"
    messages: List[OpenAIMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

@router.get("/v1/models")
def list_models():
    """OpenAI-compatible models list endpoint."""
    return {
        "object": "list",
        "data": [
            {
                "id": "friday",
                "object": "model",
                "created": 1700000000,
                "owned_by": "local",
                "permission": [],
                "root": "friday",
                "parent": None,
            }
        ]
    }

@router.post("/v1/chat/completions")
async def openai_chat_completions(request: OpenAIChatRequest):
    """
    OpenAI-compatible chat completions endpoint.
    This allows OpenWebUI to use Friday as a model.
    """
    try:
        # Extract the last user message
        user_message = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_message = msg.content
                break
        
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")
        
        # Detect and skip OpenWebUI internal prompts (tags, suggestions, etc.)
        openwebui_internal_patterns = [
            "Generate 1-3 broad tags",
            "Suggest 3-5 relevant follow-up",
            "categorizing the main themes",
            "### Task:",
            "high-level domains",
        ]
        
        is_internal_prompt = any(pattern.lower() in user_message.lower() for pattern in openwebui_internal_patterns)
        
        if is_internal_prompt:
            # Return empty/minimal response for internal prompts
            # Don't process these through Friday's full pipeline
            logger.debug(f"Skipping OpenWebUI internal prompt: {user_message[:50]}...")
            
            response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
            created = int(time.time())
            
            if request.stream:
                def skip_stream():
                    yield f"data: {json.dumps({'id': response_id, 'object': 'chat.completion.chunk', 'created': created, 'model': 'friday', 'choices': [{'index': 0, 'delta': {'content': ''}, 'finish_reason': 'stop'}]})}\n\n"
                    yield "data: [DONE]\n\n"
                return StreamingResponse(skip_stream(), media_type="text/event-stream")
            else:
                return {
                    "id": response_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": "friday",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                }
        
        # Generate a session ID from the conversation
        # Use a hash of the first message to maintain session across requests
        session_id = f"openwebui_{hash(request.messages[0].content) if request.messages else 'default'}"
        
        # Format as OpenAI response
        response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())
        
        if request.stream:
            # Streaming response
            def generate_stream():
                chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
                
                try:
                    # Call Friday's chat service with streaming
                    result = chat_service.chat(
                        message=user_message,
                        session_id=session_id,
                        stream=True
                    )
                    
                    # Check if we got a stream or a direct result
                    if isinstance(result, dict) and "stream" in result:
                        # True LLM streaming
                        stream = result["stream"]
                        for chunk in stream:
                            if chunk.choices[0].delta.content:
                                content = chunk.choices[0].delta.content
                                chunk_data = {
                                    "id": chunk_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": "friday",
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": content},
                                        "finish_reason": None
                                    }]
                                }
                                yield f"data: {json.dumps(chunk_data)}\n\n"
                    else:
                        # Direct result (tool response) - simulate streaming
                        answer = result.get("answer", "I couldn't generate a response.") if isinstance(result, dict) else str(result)
                        
                        # Stream character by character for smooth effect
                        buffer = ""
                        for char in answer:
                            buffer += char
                            # Send every few characters or on newlines for smoother streaming
                            if len(buffer) >= 3 or char in '\n.!?,:;':
                                chunk_data = {
                                    "id": chunk_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": "friday",
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": buffer},
                                        "finish_reason": None
                                    }]
                                }
                                yield f"data: {json.dumps(chunk_data)}\n\n"
                                buffer = ""
                        
                        # Send remaining buffer
                        if buffer:
                            chunk_data = {
                                "id": chunk_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": "friday",
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": buffer},
                                    "finish_reason": None
                                }]
                            }
                            yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                except Exception as e:
                    logger.error(f"Streaming error: {e}", exc_info=True)
                    error_chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": "friday",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": f"Error: {str(e)}"},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
                
                # Send final chunk
                final_chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": "friday",
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            # Non-streaming response
            result = chat_service.chat(
                message=user_message,
                session_id=session_id,
                stream=False
            )
            
            answer = result.get("answer", "I couldn't generate a response.")
            
            return {
                "id": response_id,
                "object": "chat.completion",
                "created": created,
                "model": "friday",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": answer
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": len(user_message.split()),
                    "completion_tokens": len(answer.split()),
                    "total_tokens": len(user_message.split()) + len(answer.split())
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OpenAI chat completions error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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


@router.post("/admin/reload-personality")
def reload_personality(x_api_key: Optional[str] = Header(None)):
    """Reload Friday's personality from the About file."""
    verify_auth(x_api_key)
    
    try:
        personality = chat_service.reload_personality()
        return {
            "status": "ok",
            "message": "Personality reloaded",
            "personality_length": len(personality),
            "preview": personality[:200] + "..." if len(personality) > 200 else personality
        }
    except Exception as e:
        logger.error(f"Reload personality error: {e}", exc_info=True)
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


@router.get("/admin/alerts/skipped")
def get_skipped_alerts(x_api_key: Optional[str] = Header(None)):
    """Get alerts that were skipped today due to budget exhaustion."""
    verify_auth(x_api_key)
    
    try:
        from app.services.proactive_monitor import proactive_monitor
        
        skipped = proactive_monitor.get_skipped_alerts()
        stats = proactive_monitor.get_budget_stats()
        
        return {
            "status": "ok",
            "date": stats.get("date"),
            "budget_stats": stats,
            "skipped_count": len(skipped),
            "skipped_alerts": skipped
        }
    except Exception as e:
        logger.error(f"Get skipped alerts error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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


# ===== TASK MANAGEMENT ENDPOINTS =====

@router.post("/tasks", response_model=TaskResponse)
def create_task(task: TaskCreate, x_api_key: Optional[str] = Header(None)):
    """Create a new task."""
    verify_auth(x_api_key)
    
    try:
        task_id = task_manager.create_task(
            title=task.title,
            description=task.description,
            due_date_str=task.due_date,
            priority=task.priority,
            context=task.context,
            energy_level=task.energy_level,
            project=task.project,
            people=task.people
        )
        
        task_data = task_manager.get_task(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found after creation")
        
        return TaskResponse(**task_data)
    
    except Exception as e:
        logger.error(f"Create task error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks", response_model=List[TaskResponse])
def list_tasks(
    x_api_key: Optional[str] = Header(None),
    status: Optional[str] = Query(None, description="Filter by status: pending, in_progress, completed, cancelled"),
    context: Optional[str] = Query(None, description="Filter by context: home, work, gym, etc."),
    priority: Optional[str] = Query(None, description="Filter by priority: Low, Medium, High, Urgent"),
    due_soon: bool = Query(False, description="Only show tasks due within 7 days")
):
    """List all tasks with optional filters."""
    verify_auth(x_api_key)
    
    try:
        tasks = task_manager.list_tasks(
            status=status,
            context=context,
            priority=priority,
            due_soon=due_soon
        )
        return [TaskResponse(**t) for t in tasks]
    
    except Exception as e:
        logger.error(f"List tasks error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/today", response_model=List[TaskResponse])
def get_today_tasks(x_api_key: Optional[str] = Header(None)):
    """Get tasks due today."""
    verify_auth(x_api_key)
    
    try:
        tasks = task_manager.get_today_tasks()
        return [TaskResponse(**t) for t in tasks]
    
    except Exception as e:
        logger.error(f"Get today tasks error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, x_api_key: Optional[str] = Header(None)):
    """Get a specific task by ID."""
    verify_auth(x_api_key)
    
    try:
        task_data = task_manager.get_task(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskResponse(**task_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get task error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task: TaskUpdate, x_api_key: Optional[str] = Header(None)):
    """Update a task."""
    verify_auth(x_api_key)
    
    try:
        # Build update dict with only provided fields
        updates = {}
        if task.title is not None:
            updates["title"] = task.title
        if task.description is not None:
            updates["description"] = task.description
        if task.status is not None:
            updates["status"] = task.status
        if task.due_date is not None:
            updates["due_date"] = task.due_date
        if task.priority is not None:
            updates["priority"] = task.priority
        if task.context is not None:
            updates["context"] = task.context
        if task.energy_level is not None:
            updates["energy_level"] = task.energy_level
        if task.project is not None:
            updates["project"] = task.project
        if task.people is not None:
            updates["people"] = task.people
        
        task_manager.update_task(task_id, **updates)
        
        task_data = task_manager.get_task(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskResponse(**task_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update task error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, x_api_key: Optional[str] = Header(None)):
    """Delete a task."""
    verify_auth(x_api_key)
    
    try:
        # Verify task exists
        task_data = task_manager.get_task(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Mark as cancelled instead of deleting
        task_manager.update_task(task_id, status="cancelled")
        
        return {"status": "ok", "message": f"Task {task_id} cancelled"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete task error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
