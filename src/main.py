"""Friday AI Assistant - Main entry point."""
from fastapi import FastAPI
from app.api.routes import router
from app.core.logging import logger
from app.core.config import settings

# Initialize FastAPI app
app = FastAPI(
    title="Friday: AI Assistant",
    description="Personal homelab AI with RAG, memory, and web search",
    version="1.0.0"
)

# Include routes
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("=" * 60)
    logger.info("Friday AI Assistant starting up")
    logger.info(f"Vault path: {settings.vault_path}")
    logger.info(f"LLM endpoint: {settings.llm_base_url}")
    logger.info(f"LLM model: {settings.llm_model_name}")
    
    # Start file watcher
    try:
        from app.services.file_watcher import file_watcher
        from app.services.scheduler import task_scheduler
        from app.services.coaching_scheduler import coaching_scheduler
        from app.services.reminders import reminder_service
        
        file_watcher.start()
        task_scheduler.start()
        coaching_scheduler.start()
        reminder_service.start_background_task()
        
        logger.info("File watcher, scheduler, coaching, and reminders started")
    except Exception as e:
        logger.error(f"Failed to start services: {e}")
    
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Friday AI Assistant shutting down")
    
    # Stop services
    try:
        from app.services.file_watcher import file_watcher
        from app.services.scheduler import task_scheduler
        from app.services.coaching_scheduler import coaching_scheduler
        from app.services.reminders import reminder_service
        
        task_scheduler.stop()
        coaching_scheduler.stop()
        reminder_service.stop_background_task()
        file_watcher.stop()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


if __name__ == "__main__":
    import uvicorn
    import os
    # Only enable reload in development
    reload = os.getenv("FRIDAY_DEV_MODE", "false").lower() == "true"
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=reload,
        log_level="info"
    )
