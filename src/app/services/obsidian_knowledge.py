"""
Obsidian Knowledge Service for Friday AI.

Embeds knowledge of the user's Obsidian note system, including:
- Folder structure and conventions
- Tagging system
- Templates
- How to properly create and update notes

This gives Friday "native" understanding of the vault structure.
"""
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from app.core.config import settings
from app.core.logging import logger


@dataclass
class FolderInfo:
    """Information about a folder in the vault."""
    path: str
    purpose: str
    usage: str
    subfolders: List[str]


@dataclass 
class TagInfo:
    """Information about a tag category."""
    prefix: str
    purpose: str
    examples: List[str]


class ObsidianKnowledge:
    """
    Understands and applies knowledge of the user's Obsidian note system.
    
    Loaded from the Operating Manual and templates.
    """
    
    def __init__(self):
        """Initialize Obsidian knowledge."""
        self.brain_path = settings.brain_path
        self.vault_path = settings.vault_path
        self._operating_manual: Optional[str] = None
        self._templates: Dict[str, str] = {}
        self._folder_structure: Dict[str, FolderInfo] = {}
        self._tag_system: Dict[str, TagInfo] = {}
        
        self._load_knowledge()
    
    def _load_knowledge(self):
        """Load knowledge from the vault."""
        self._load_operating_manual()
        self._load_templates()
        self._parse_folder_structure()
        self._parse_tag_system()
        
        logger.info(f"Obsidian knowledge loaded: {len(self._templates)} templates, {len(self._folder_structure)} folders")
    
    def _load_operating_manual(self):
        """Load the Obsidian Operating Manual."""
        manual_path = self.brain_path / "0. Overview" / "The Obsidian Operating Manual.md"
        
        if manual_path.exists():
            try:
                content = manual_path.read_text(encoding="utf-8")
                # Remove frontmatter
                if content.startswith("---"):
                    end_fm = content.find("---", 3)
                    if end_fm != -1:
                        content = content[end_fm + 3:].strip()
                self._operating_manual = content
                logger.info(f"Loaded Operating Manual: {len(content)} chars")
            except Exception as e:
                logger.error(f"Failed to load Operating Manual: {e}")
        else:
            logger.warning(f"Operating Manual not found: {manual_path}")
    
    def _load_templates(self):
        """Load all templates from the templates folder."""
        templates_path = self.brain_path / "3. Resources" / "3.2 Templates"
        
        if not templates_path.exists():
            logger.warning(f"Templates folder not found: {templates_path}")
            return
        
        for template_file in templates_path.glob("*.md"):
            try:
                content = template_file.read_text(encoding="utf-8")
                template_name = template_file.stem
                self._templates[template_name] = content
            except Exception as e:
                logger.error(f"Failed to load template {template_file}: {e}")
        
        logger.info(f"Loaded {len(self._templates)} templates")
    
    def _parse_folder_structure(self):
        """Parse the folder structure from the Operating Manual."""
        # Define the folder structure based on the manual
        self._folder_structure = {
            "0. Overview": FolderInfo(
                path="0. Overview",
                purpose="Main control center and entry point for the vault",
                usage="Contains dashboards, inbox, and maps of content",
                subfolders=["0.1 Inbox", "0.2 Dashboards", "0.3 Maps of Content (MOCs)"]
            ),
            "0.1 Inbox": FolderInfo(
                path="0. Overview/0.1 Inbox",
                purpose="Temporary storage for new notes and fleeting ideas",
                usage="All new notes start here before being processed and moved",
                subfolders=[]
            ),
            "1. Notes": FolderInfo(
                path="1. Notes",
                purpose="Permanent library for timeless, processed knowledge",
                usage="Store refined notes here once complete. Home for atomic notes, topic notes, and evergreen summaries.",
                subfolders=[]
            ),
            "2. Time": FolderInfo(
                path="2. Time",
                purpose="Active, time-sensitive notes (journals, meetings, goals)",
                usage="Contents surfaced through Dashboards, not browsed directly",
                subfolders=["2.1 Weekly", "2.2 Daily", "2.3 Meetings"]
            ),
            "3. Resources": FolderInfo(
                path="3. Resources",
                purpose="Non-note supplementary materials",
                usage="Templates, attachments, and other supporting files",
                subfolders=["3.1 Templates", "3.2 Attachments"]
            ),
            "4. Archive": FolderInfo(
                path="4. Archive",
                purpose="Cold storage for completed or inactive items",
                usage="Move completed projects and old time-based notes here",
                subfolders=["4.1 Projects", "4.2 Time"]
            ),
            "5. Friday": FolderInfo(
                path="5. Friday",
                purpose="Friday AI's dedicated space",
                usage="Memories, journals, reports, reminders. Managed by Friday, editable in Obsidian.",
                subfolders=["5.0 About", "5.1 Memories", "5.2 Journal", "5.3 Reports", "5.4 Reminders", "5.5 Conversations"]
            ),
        }
    
    def _parse_tag_system(self):
        """Parse the tagging system from the Operating Manual."""
        self._tag_system = {
            "time": TagInfo(
                prefix="#time/",
                purpose="Categorize notes in 2. Time folder by temporal type",
                examples=["#time/daily", "#time/weekly", "#time/meeting", "#time/goal"]
            ),
            "area": TagInfo(
                prefix="#area/",
                purpose="High-level tag to separate broad domains of life",
                examples=["#area/work", "#area/personal", "#area/learning", "#area/health", "#area/family", "#area/friday"]
            ),
            "person": TagInfo(
                prefix="#person/",
                purpose="Categorize notes by relationship or social context",
                examples=["#person/family", "#person/friend", "#person/colleague", "#person/client"]
            ),
            "project": TagInfo(
                prefix="#project/",
                purpose="Group notes related to a specific endeavor",
                examples=["#project/website-redesign", "#project/q3-launch"]
            ),
            "topic": TagInfo(
                prefix="#topic/",
                purpose="Subject matter classification (universal knowledge)",
                examples=["#topic/productivity", "#topic/psychology", "#topic/programming"]
            ),
            "extra": TagInfo(
                prefix="#extra/",
                purpose="Reference supplementary materials",
                examples=["#extra/template", "#extra/memory", "#extra/journal", "#extra/report"]
            ),
        }
    
    def get_operating_manual(self) -> str:
        """Get the full Operating Manual content."""
        return self._operating_manual or ""
    
    def get_operating_manual_summary(self) -> str:
        """Get a summary of the Operating Manual for context."""
        if not self._operating_manual:
            return ""
        
        return """## Obsidian Note System Summary

### Folder Structure
- **0. Overview**: Control center (Inbox, Dashboards, MOCs)
- **0.1 Inbox**: All new notes start here before processing
- **1. Notes**: Permanent library for processed knowledge
- **2. Time**: Time-sensitive notes (daily, weekly, meetings, goals)
- **3. Resources**: Templates and attachments
- **4. Archive**: Cold storage for completed items
- **5. Friday**: My dedicated space (memories, journals, reports)

### Core Philosophy
**Folders define the STATE of a note, tags define its CONTEXT.**

### Tag System
- `#time/...` - Temporal type (daily, weekly, meeting, goal)
- `#area/...` - Life domain (work, personal, health, friday)
- `#person/...` - Relationship context (family, colleague, client)
- `#project/...` - Specific endeavor
- `#topic/...` - Subject matter (universal knowledge)
- `#extra/...` - Supplementary materials (memory, journal, report)

### Area vs Topic
- **Area** is the "hat you're wearing" (your role/domain)
- **Topic** is the "book you're reading" (universal subject)

### Note Workflow
1. **Capture**: New notes go to Inbox
2. **Process**: Refine, tag, and move to permanent home
3. **View**: Navigate through Dashboards, not file explorer
4. **Archive**: Move completed items to Archive
"""
    
    def get_template(self, template_name: str) -> Optional[str]:
        """Get a specific template by name."""
        return self._templates.get(template_name)
    
    def get_friday_templates(self) -> Dict[str, str]:
        """Get all Friday-specific templates."""
        return {
            name: content
            for name, content in self._templates.items()
            if name.startswith("Friday")
        }
    
    def get_folder_for_note_type(self, note_type: str) -> str:
        """
        Determine the correct folder for a note type.
        
        Args:
            note_type: Type of note (daily, meeting, idea, memory, etc.)
        
        Returns:
            The folder path where this note should be created.
        """
        type_to_folder = {
            # Time-based notes
            "daily": "2. Time/2.2 Daily",
            "weekly": "2. Time/2.1 Weekly",
            "meeting": "2. Time/2.3 Meetings",
            "goal": "2. Time",
            
            # Friday notes
            "memory": "5. Friday/5.1 Memories",
            "journal": "5. Friday/5.2 Journal",
            "report": "5. Friday/5.3 Reports",
            "reminder": "5. Friday/5.4 Reminders",
            "idea": "0. Overview/0.1 Inbox",  # Ideas go to inbox first
            
            # General notes
            "note": "0. Overview/0.1 Inbox",  # New notes start in inbox
            "source": "1. Notes",
            "atomic": "1. Notes",
        }
        
        return type_to_folder.get(note_type.lower(), "0. Overview/0.1 Inbox")
    
    def get_tags_for_note_type(self, note_type: str) -> List[str]:
        """
        Get the appropriate tags for a note type.
        
        Args:
            note_type: Type of note
            
        Returns:
            List of tags to apply.
        """
        type_to_tags = {
            "daily": ["time/daily"],
            "weekly": ["time/weekly"],
            "meeting": ["time/meeting"],
            "goal": ["time/goal"],
            "memory": ["area/friday", "extra/memory"],
            "journal": ["area/friday", "extra/journal"],
            "report": ["area/friday", "extra/report"],
            "idea": ["area/friday", "extra/idea"],
            "source": ["source"],
            "atomic": ["atomic"],
        }
        
        return type_to_tags.get(note_type.lower(), [])
    
    def suggest_tags_for_content(self, content: str, title: str = "") -> List[str]:
        """
        Suggest appropriate tags based on content analysis.
        
        Args:
            content: The note content
            title: The note title
            
        Returns:
            List of suggested tags.
        """
        suggested = []
        combined = f"{title} {content}".lower()
        
        # Area detection
        if any(word in combined for word in ["work", "job", "meeting", "project", "deadline", "colleague"]):
            suggested.append("area/work")
        if any(word in combined for word in ["health", "sleep", "exercise", "run", "workout", "diet"]):
            suggested.append("area/health")
        if any(word in combined for word in ["learn", "study", "course", "book", "tutorial"]):
            suggested.append("area/learning")
        if any(word in combined for word in ["family", "wife", "camila", "mom", "dad", "brother", "sister"]):
            suggested.append("area/family")
        
        # Topic detection
        if any(word in combined for word in ["python", "code", "programming", "software", "api"]):
            suggested.append("topic/programming")
        if any(word in combined for word in ["psychology", "therapy", "mental", "emotion", "feeling"]):
            suggested.append("topic/psychology")
        if any(word in combined for word in ["productivity", "habit", "routine", "workflow"]):
            suggested.append("topic/productivity")
        
        return suggested
    
    def validate_note_location(self, filepath: str) -> Dict[str, Any]:
        """
        Validate if a note is in the correct location based on its content/tags.
        
        Args:
            filepath: Path to the note file
            
        Returns:
            Dict with 'valid', 'issues', 'suggestions'.
        """
        result = {
            "valid": True,
            "issues": [],
            "suggestions": [],
        }
        
        try:
            full_path = self.brain_path / filepath
            if not full_path.exists():
                result["valid"] = False
                result["issues"].append(f"File not found: {filepath}")
                return result
            
            content = full_path.read_text(encoding="utf-8")
            
            # Extract tags from frontmatter
            tags = []
            if content.startswith("---"):
                end_fm = content.find("---", 3)
                if end_fm != -1:
                    frontmatter = content[3:end_fm]
                    for line in frontmatter.split("\n"):
                        line = line.strip()
                        if line.startswith("- ") and "/" in line:
                            tags.append(line[2:].strip())
            
            # Check folder/tag consistency
            current_folder = str(Path(filepath).parent)
            
            # Friday notes should be in 5. Friday
            if any("area/friday" in t or "extra/memory" in t or "extra/journal" in t for t in tags):
                if not current_folder.startswith("5. Friday"):
                    result["valid"] = False
                    result["issues"].append(f"Friday-tagged note is not in 5. Friday folder")
                    result["suggestions"].append(f"Move to appropriate subfolder in 5. Friday/")
            
            # Time-based notes should be in 2. Time
            if any(t.startswith("time/") for t in tags):
                if not current_folder.startswith("2. Time"):
                    result["valid"] = False
                    result["issues"].append(f"Time-tagged note is not in 2. Time folder")
                    result["suggestions"].append(f"Move to 2. Time/ or appropriate subfolder")
            
            # Notes in Inbox should be processed
            if current_folder == "0. Overview/0.1 Inbox":
                # Check if note has been there for a while (would need file dates)
                result["suggestions"].append("This note is in Inbox - consider processing and moving it")
            
        except Exception as e:
            result["valid"] = False
            result["issues"].append(f"Error validating note: {e}")
        
        return result
    
    def get_context_for_llm(self) -> str:
        """
        Get Obsidian knowledge as context for LLM calls.
        
        Returns a concise summary that can be included in system prompts.
        """
        return self.get_operating_manual_summary()
    
    def find_stale_notes(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Find notes that haven't been updated in a while.
        
        Args:
            days: Number of days to consider a note "stale"
            
        Returns:
            List of stale notes with metadata.
        """
        stale_notes = []
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        # Check notes in 1. Notes and 2. Time
        for folder in ["1. Notes", "2. Time"]:
            folder_path = self.brain_path / folder
            if not folder_path.exists():
                continue
            
            for note_path in folder_path.rglob("*.md"):
                try:
                    stat = note_path.stat()
                    if stat.st_mtime < cutoff:
                        stale_notes.append({
                            "path": str(note_path.relative_to(self.brain_path)),
                            "title": note_path.stem,
                            "last_modified": datetime.fromtimestamp(stat.st_mtime),
                            "days_stale": int((datetime.now().timestamp() - stat.st_mtime) / (24 * 60 * 60)),
                        })
                except Exception as e:
                    logger.error(f"Error checking note {note_path}: {e}")
        
        return sorted(stale_notes, key=lambda x: x["days_stale"], reverse=True)
    
    def find_notes_missing_tags(self) -> List[Dict[str, Any]]:
        """
        Find notes that are missing appropriate tags.
        
        Returns:
            List of notes with suggested tags.
        """
        notes_missing_tags = []
        
        for folder in ["1. Notes", "2. Time"]:
            folder_path = self.brain_path / folder
            if not folder_path.exists():
                continue
            
            for note_path in folder_path.rglob("*.md"):
                try:
                    content = note_path.read_text(encoding="utf-8")
                    
                    # Extract existing tags
                    existing_tags = []
                    if content.startswith("---"):
                        end_fm = content.find("---", 3)
                        if end_fm != -1:
                            frontmatter = content[3:end_fm]
                            for line in frontmatter.split("\n"):
                                line = line.strip()
                                if line.startswith("- ") and "/" in line:
                                    existing_tags.append(line[2:].strip())
                    
                    # Suggest additional tags
                    suggested = self.suggest_tags_for_content(content, note_path.stem)
                    missing = [t for t in suggested if t not in existing_tags]
                    
                    if missing:
                        notes_missing_tags.append({
                            "path": str(note_path.relative_to(self.brain_path)),
                            "title": note_path.stem,
                            "existing_tags": existing_tags,
                            "suggested_tags": missing,
                        })
                        
                except Exception as e:
                    logger.error(f"Error checking note {note_path}: {e}")
        
        return notes_missing_tags
    
    def find_inbox_notes(self, older_than_days: int = 3) -> List[Dict[str, Any]]:
        """
        Find notes in the Inbox that have been there too long.
        
        Args:
            older_than_days: Notes older than this should be processed.
            
        Returns:
            List of inbox notes that need processing.
        """
        inbox_notes = []
        inbox_path = self.brain_path / "0. Overview" / "0.1 Inbox"
        
        if not inbox_path.exists():
            return inbox_notes
        
        cutoff = datetime.now().timestamp() - (older_than_days * 24 * 60 * 60)
        
        for note_path in inbox_path.glob("*.md"):
            try:
                stat = note_path.stat()
                days_old = int((datetime.now().timestamp() - stat.st_ctime) / (24 * 60 * 60))
                
                inbox_notes.append({
                    "path": str(note_path.relative_to(self.brain_path)),
                    "title": note_path.stem,
                    "created": datetime.fromtimestamp(stat.st_ctime),
                    "days_in_inbox": days_old,
                    "needs_processing": stat.st_ctime < cutoff,
                })
            except Exception as e:
                logger.error(f"Error checking inbox note {note_path}: {e}")
        
        return sorted(inbox_notes, key=lambda x: x["days_in_inbox"], reverse=True)
    
    def find_misplaced_notes(self) -> List[Dict[str, Any]]:
        """
        Find notes that are in the wrong folder based on their tags.
        
        Returns:
            List of misplaced notes with suggested locations.
        """
        misplaced = []
        
        # Check notes in common folders
        check_folders = ["1. Notes", "2. Time", "5. Friday"]
        
        for folder in check_folders:
            folder_path = self.brain_path / folder
            if not folder_path.exists():
                continue
            
            for note_path in folder_path.rglob("*.md"):
                try:
                    validation = self.validate_note_location(
                        str(note_path.relative_to(self.brain_path))
                    )
                    if not validation["valid"]:
                        misplaced.append({
                            "path": str(note_path.relative_to(self.brain_path)),
                            "title": note_path.stem,
                            "issues": validation["issues"],
                            "suggestions": validation["suggestions"],
                        })
                except Exception as e:
                    logger.error(f"Error validating note {note_path}: {e}")
        
        return misplaced
    
    def run_health_check(self) -> Dict[str, Any]:
        """
        Run a comprehensive health check on the Obsidian vault.
        
        Returns:
            Dict with health check results and suggestions.
        """
        logger.info("Running Obsidian vault health check...")
        
        # Gather all health data
        stale_notes = self.find_stale_notes(days=30)
        inbox_notes = self.find_inbox_notes(older_than_days=3)
        missing_tags = self.find_notes_missing_tags()
        misplaced = self.find_misplaced_notes()
        
        # Filter inbox to just those needing processing
        inbox_needing_processing = [n for n in inbox_notes if n["needs_processing"]]
        
        # Calculate overall health score (0-100)
        # Weight issues differently:
        # - Inbox backlog: -10 per note (these should be processed)
        # - Stale notes: -3 per note (max 10 considered)
        # - Misplaced notes: -5 per note (organization issue)
        # - Missing tags: -1 per note (minor, just suggestions)
        score_penalty = (
            len(inbox_needing_processing) * 10 +
            min(len(stale_notes), 10) * 3 +
            len(misplaced) * 5 +
            min(len(missing_tags), 20) * 1  # Cap at 20 points
        )
        health_score = max(0, 100 - score_penalty)
        
        # Determine health status
        if health_score >= 80:
            status = "healthy"
            status_emoji = "green"
        elif health_score >= 50:
            status = "needs_attention"
            status_emoji = "yellow"
        else:
            status = "needs_work"
            status_emoji = "red"
        
        result = {
            "health_score": health_score,
            "status": status,
            "status_emoji": status_emoji,
            "summary": {
                "stale_notes": len(stale_notes),
                "inbox_backlog": len(inbox_needing_processing),
                "missing_tags": len(missing_tags),
                "misplaced_notes": len(misplaced),
            },
            "details": {
                "stale_notes": stale_notes[:5],  # Top 5 most stale
                "inbox_backlog": inbox_needing_processing[:5],
                "missing_tags": missing_tags[:5],
                "misplaced_notes": misplaced[:5],
            },
            "recommendations": [],
        }
        
        # Generate recommendations
        if inbox_needing_processing:
            result["recommendations"].append(
                f"You have {len(inbox_needing_processing)} notes in your Inbox waiting to be processed. "
                f"The oldest is '{inbox_needing_processing[0]['title']}' ({inbox_needing_processing[0]['days_in_inbox']} days old)."
            )
        
        if stale_notes:
            oldest = stale_notes[0]
            result["recommendations"].append(
                f"You have {len(stale_notes)} notes that haven't been touched in 30+ days. "
                f"Consider reviewing '{oldest['title']}' ({oldest['days_stale']} days stale) - "
                f"is it still relevant or should it be archived?"
            )
        
        if missing_tags:
            result["recommendations"].append(
                f"{len(missing_tags)} notes could use better tagging. "
                f"For example, '{missing_tags[0]['title']}' could benefit from tags: {', '.join(missing_tags[0]['suggested_tags'])}."
            )
        
        if misplaced:
            result["recommendations"].append(
                f"{len(misplaced)} notes might be in the wrong folder. "
                f"Check '{misplaced[0]['title']}': {misplaced[0]['suggestions'][0] if misplaced[0]['suggestions'] else 'needs review'}."
            )
        
        if not result["recommendations"]:
            result["recommendations"].append("Your vault looks healthy! Keep up the good work.")
        
        logger.info(f"Health check complete: score={health_score}, status={status}")
        return result
    
    def get_health_summary_for_llm(self) -> str:
        """
        Get a concise health check summary for including in LLM context.
        
        Returns:
            A formatted string summary of vault health.
        """
        result = self.run_health_check()
        
        lines = [f"## Vault Health: {result['status'].replace('_', ' ').title()} ({result['health_score']}/100)"]
        
        if result["recommendations"]:
            lines.append("\n### Recommendations:")
            for rec in result["recommendations"][:3]:  # Top 3 recommendations
                lines.append(f"- {rec}")
        
        return "\n".join(lines)


# Singleton instance
obsidian_knowledge = ObsidianKnowledge()
