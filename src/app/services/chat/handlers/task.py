"""Task intent handlers - create, list, complete tasks."""
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse
from app.services.task_manager import task_manager, TaskStatus, TaskPriority, TaskContext


class TaskCreateHandler(IntentHandler):
    """Handle task_create intent - create new tasks."""
    
    actions = ['task_create']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Create a new task."""
        task_data = context.task_data
        
        if not task_data:
            return self._error_response(context, "No task data provided")
        
        try:
            title = task_data.get('title', '')
            priority_str = task_data.get('priority', 'medium').upper()
            context_str = task_data.get('context', 'any').upper()
            due_date_str = task_data.get('due_date')
            
            if not title:
                return self._error_response(context, "Please specify what task you want to create.")
            
            # Parse priority
            priority = getattr(TaskPriority, priority_str, TaskPriority.MEDIUM)
            
            # Parse context
            task_context = getattr(TaskContext, context_str, TaskContext.ANY)
            
            # Parse due date
            due_date = None
            if due_date_str:
                user_tz = settings.user_timezone
                now = datetime.now(user_tz)
                if due_date_str.lower() == 'today':
                    due_date = now.replace(hour=23, minute=59)
                elif due_date_str.lower() == 'tomorrow':
                    due_date = (now + timedelta(days=1)).replace(hour=23, minute=59)
            
            task = task_manager.create_task(
                title=title,
                priority=priority,
                context=task_context,
                due_date=due_date
            )
            
            priority_icon = {
                "URGENT": "!!", 
                "HIGH": "!", 
                "MEDIUM": "", 
                "LOW": ""
            }.get(priority.name, "")
            
            answer = f"Created task: {priority_icon} {title}"
            if due_date:
                answer += f" (due {due_date.strftime('%b %d')})"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Task create error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to create task: {str(e)}")


class TaskListHandler(IntentHandler):
    """Handle task_list intent - list tasks."""
    
    actions = ['task_list']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """List tasks based on tool type."""
        tool = context.tool
        
        try:
            if tool == "task_today":
                answer = self._get_today_tasks()
            else:
                answer = self._get_all_tasks()
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Task list error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to list tasks: {str(e)}")
    
    def _get_all_tasks(self) -> str:
        """Get all pending tasks."""
        tasks = task_manager.list_tasks(status=TaskStatus.TODO, limit=20)
        in_progress = task_manager.list_tasks(status=TaskStatus.IN_PROGRESS, limit=10)
        all_tasks = in_progress + tasks
        
        if all_tasks:
            result = "Your tasks:\n\n"
            for task in all_tasks:
                status_icon = "[>]" if task.status == TaskStatus.IN_PROGRESS else "[ ]"
                priority_icon = {
                    "URGENT": "!!",
                    "HIGH": "!",
                    "MEDIUM": "",
                    "LOW": ""
                }.get(task.priority.name, "")
                due_str = f" (due {task.due_date.strftime('%b %d')})" if task.due_date else ""
                result += f"{status_icon} {priority_icon} {task.title}{due_str}\n"
            return result
        return "You have no pending tasks."
    
    def _get_today_tasks(self) -> str:
        """Get today's tasks."""
        tasks = task_manager.get_tasks_for_today()
        
        if tasks:
            result = "Today's tasks:\n\n"
            for task in tasks:
                status_icon = "[>]" if task.status == TaskStatus.IN_PROGRESS else "[ ]"
                priority_icon = {
                    "URGENT": "!!",
                    "HIGH": "!",
                    "MEDIUM": "",
                    "LOW": ""
                }.get(task.priority.name, "")
                result += f"{status_icon} {priority_icon} {task.title}\n"
            return result
        return "You have no tasks scheduled for today."


class TaskCompleteHandler(IntentHandler):
    """Handle task_complete intent - mark tasks as done."""
    
    actions = ['task_complete']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Mark a task as complete."""
        task_data = context.task_data
        
        if not task_data:
            return self._error_response(context, "No task data provided")
        
        try:
            task_id_or_title = task_data.get('task_id', '')
            
            if not task_id_or_title:
                return self._error_response(context, "Please specify which task to complete.")
            
            # First try to find by exact ID
            task = task_manager.get_task(task_id_or_title)
            
            # If not found, search by title
            if not task:
                tasks = task_manager.list_tasks(status=TaskStatus.TODO, limit=100)
                tasks += task_manager.list_tasks(status=TaskStatus.IN_PROGRESS, limit=100)
                
                # Find task by partial title match
                search_lower = task_id_or_title.lower()
                for t in tasks:
                    if search_lower in t.title.lower():
                        task = t
                        break
            
            if task:
                task_manager.update_task_status(task.id, TaskStatus.DONE)
                answer = f"Completed: {task.title}"
            else:
                answer = f"Task not found: '{task_id_or_title}'"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Task complete error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to complete task: {str(e)}")


class TaskQueryHandler(IntentHandler):
    """Handle task_query intent - query specific task details."""
    
    actions = ['task_query']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Query details about a specific task."""
        task_data = context.task_data
        
        try:
            task_id_or_title = task_data.get('task_id', '') if task_data else ''
            
            if not task_id_or_title:
                # If no specific task, just list all tasks
                return TaskListHandler().handle(context)
            
            # Try to find task
            task = task_manager.get_task(task_id_or_title)
            
            if not task:
                tasks = task_manager.list_tasks(status=TaskStatus.TODO, limit=100)
                tasks += task_manager.list_tasks(status=TaskStatus.IN_PROGRESS, limit=100)
                
                search_lower = task_id_or_title.lower()
                for t in tasks:
                    if search_lower in t.title.lower():
                        task = t
                        break
            
            if task:
                answer = f"Task: {task.title}\n"
                answer += f"Status: {task.status.value}\n"
                answer += f"Priority: {task.priority.value}\n"
                answer += f"Context: {task.context.value}\n"
                if task.due_date:
                    answer += f"Due: {task.due_date.strftime('%b %d, %Y')}\n"
                if task.created_at:
                    answer += f"Created: {task.created_at.strftime('%b %d, %Y')}"
            else:
                answer = f"Task not found: '{task_id_or_title}'"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Task query error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to query task: {str(e)}")
