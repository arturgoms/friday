"""Report intent handlers - morning/evening reports, vault health."""
from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse


class MorningReportHandler(IntentHandler):
    """Handle morning_report intent - generate morning briefing."""
    
    actions = ['morning_report']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Generate the morning report."""
        try:
            from app.services.morning_report import generate_morning_report
            from app.services.unified_calendar_service import UnifiedCalendarService
            from app.services.llm import LLMService
            from app.services.health_coach import get_health_coach
            
            health_coach = get_health_coach()
            calendar_service = UnifiedCalendarService()
            llm_svc = LLMService()
            
            answer = generate_morning_report(
                health_coach=health_coach,
                calendar_service=calendar_service,
                llm_service=llm_svc
            )
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                used_health=True,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Morning report error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to generate morning report: {str(e)}")


class EveningReportHandler(IntentHandler):
    """Handle evening_report intent - generate evening briefing."""
    
    actions = ['evening_report']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Generate the evening report."""
        try:
            from app.services.evening_report import generate_evening_report
            from app.services.unified_calendar_service import UnifiedCalendarService
            from app.services.llm import LLMService
            from app.services.health_coach import get_health_coach
            
            health_coach = get_health_coach()
            calendar_service = UnifiedCalendarService()
            llm_svc = LLMService()
            
            answer = generate_evening_report(
                health_coach=health_coach,
                calendar_service=calendar_service,
                llm_service=llm_svc
            )
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                used_health=True,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Evening report error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to generate evening report: {str(e)}")


class VaultHealthHandler(IntentHandler):
    """Handle vault_health intent - check Obsidian vault health."""
    
    actions = ['vault_health']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Run vault health check."""
        try:
            from app.services.obsidian_knowledge import obsidian_knowledge
            
            health_result = obsidian_knowledge.run_health_check()
            
            # Format the response
            score = health_result["health_score"]
            status = health_result["status"].replace("_", " ").title()
            
            answer_lines = [f"## Vault Health Check: {status} ({score}/100)\n"]
            
            summary = health_result["summary"]
            answer_lines.append("### Summary")
            answer_lines.append(f"- **Inbox backlog:** {summary['inbox_backlog']} notes")
            answer_lines.append(f"- **Stale notes:** {summary['stale_notes']} (30+ days)")
            answer_lines.append(f"- **Missing tags:** {summary['missing_tags']} notes")
            answer_lines.append(f"- **Misplaced notes:** {summary['misplaced_notes']}")
            answer_lines.append("")
            
            if health_result["recommendations"]:
                answer_lines.append("### Recommendations")
                for rec in health_result["recommendations"]:
                    answer_lines.append(f"- {rec}")
            
            answer = "\n".join(answer_lines)
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Vault health check error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to run vault health check: {str(e)}")


class BodyHealthCheckHandler(IntentHandler):
    """Handle body_health_check intent - comprehensive Garmin health assessment."""
    
    actions = ['body_health_check']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Run comprehensive body health check."""
        try:
            from app.services.health_coach import get_health_coach
            
            health_coach = get_health_coach()
            if not health_coach:
                return self._error_response(
                    context, 
                    "Health coach is not available. Check InfluxDB connection."
                )
            
            health_result = health_coach.run_health_check()
            
            # Format the response
            score = health_result["health_score"]
            status = health_result["status"].replace("_", " ").title()
            emoji = health_result["status_emoji"]
            
            answer_lines = [f"## Body Health Check: {status} {emoji} ({score}/100)\n"]
            
            # Key metrics
            details = health_result.get("details", {})
            if details:
                answer_lines.append("### Current Metrics")
                if "body_battery" in details:
                    answer_lines.append(f"- **Body Battery:** {details['body_battery']}/100")
                if "training_readiness" in details:
                    answer_lines.append(f"- **Training Readiness:** {details['training_readiness']}/100")
                if "hrv" in details:
                    hrv_avg = details.get('hrv_7day_avg', 'N/A')
                    answer_lines.append(f"- **HRV:** {details['hrv']}ms (7-day avg: {hrv_avg}ms)")
                if "recovery_time_hours" in details:
                    answer_lines.append(f"- **Recovery Time:** {details['recovery_time_hours']}h")
                if "last_sleep" in details:
                    sleep = details["last_sleep"]
                    answer_lines.append(
                        f"- **Last Sleep:** {sleep.get('total_sleep', 'N/A')} "
                        f"(score: {sleep.get('sleep_score', 'N/A')})"
                    )
                if "current_stress" in details or "avg_stress_today" in details:
                    current = details.get('current_stress', 'N/A')
                    avg_today = details.get('avg_stress_today', 'N/A')
                    avg_7day = details.get('avg_stress_7day', 'N/A')
                    if current != 'N/A':
                        answer_lines.append(
                            f"- **Stress:** {current}/100 "
                            f"(today avg: {avg_today}, 7-day avg: {avg_7day})"
                        )
                    else:
                        answer_lines.append(
                            f"- **Stress (today avg):** {avg_today}/100 "
                            f"(7-day avg: {avg_7day})"
                        )
                answer_lines.append("")
            
            # Issues
            if health_result.get("issues"):
                answer_lines.append("### Issues Found")
                for issue in health_result["issues"]:
                    answer_lines.append(f"- Warning: {issue}")
                answer_lines.append("")
            
            # Recommendations
            answer_lines.append("### Recommendations")
            for rec in health_result.get("recommendations", []):
                answer_lines.append(f"- {rec}")
            
            answer = "\n".join(answer_lines)
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                used_health=True,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Body health check error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to run body health check: {str(e)}")


class BudgetStatusHandler(IntentHandler):
    """Handle budget_status intent - show alert budget and skipped alerts."""
    
    actions = ['budget_status']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Get alert budget status."""
        try:
            from app.services.proactive_monitor import proactive_monitor
            
            stats = proactive_monitor.get_budget_stats()
            skipped = proactive_monitor.get_skipped_alerts()
            
            # Build response
            lines = [
                f"**Alert Budget Status** ({stats.get('date', 'today')})",
                f"",
                f"- Messages sent: {stats.get('messages_sent', 0)}/5",
                f"- Remaining budget: {stats.get('remaining', 0)}",
                f"- User responses: {stats.get('user_responses', 0)}",
                f"- Ignored: {stats.get('ignored', 0)}",
            ]
            
            if skipped:
                lines.append(f"")
                lines.append(f"**Skipped Alerts ({len(skipped)}):**")
                for i, alert in enumerate(skipped, 1):
                    lines.append(f"")
                    lines.append(
                        f"{i}. **{alert.get('title', 'Untitled')}** "
                        f"[{alert.get('priority', 'unknown')}]"
                    )
                    lines.append(f"   {alert.get('message', '')[:100]}")
                    lines.append(f"   _Skipped at: {alert.get('skipped_at', 'unknown')[:16]}_")
            else:
                lines.append(f"")
                lines.append(f"No alerts were skipped today.")
            
            answer = "\n".join(lines)
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Budget status error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to get budget status: {str(e)}")


class BudgetResetHandler(IntentHandler):
    """Handle budget_reset intent - reset the alert budget."""
    
    actions = ['budget_reset']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Reset the alert budget."""
        try:
            from app.services.proactive_monitor import proactive_monitor
            
            # Reset by creating a new day state
            proactive_monitor.budget._state = proactive_monitor.budget._new_day_state()
            proactive_monitor.budget._save_state()
            
            answer = (
                "Alert budget has been reset. "
                "You now have 5 message slots available for today."
            )
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Budget reset error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to reset budget: {str(e)}")
