"""Background task scheduler."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.core.logging import logger


class TaskScheduler:
    """Service for scheduling background tasks."""
    
    def __init__(self):
        """Initialize scheduler."""
        self.scheduler = BackgroundScheduler()
    
    def start(self):
        """Start the scheduler."""
        from app.services.file_watcher import file_watcher
        
        # Process pending file changes every 10 seconds
        self.scheduler.add_job(
            file_watcher.process_pending_files,
            trigger=IntervalTrigger(seconds=10),
            id='process_files',
            name='Process pending file changes',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Task scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Task scheduler stopped")


# Singleton instance
task_scheduler = TaskScheduler()
