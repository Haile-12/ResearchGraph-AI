from __future__ import annotations
import threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from db.history_db import (
    add_message, 
    get_messages, 
    list_all_sessions, 
    save_session, 
    delete_session_db, 
    clear_messages,
    get_session as get_session_db,
    init_db
)
from models.gemini_client import generate_text
from utils.logger import get_logger

logger = get_logger(__name__)
init_db()
MAX_BUFFER_TURNS = 10

@dataclass
class ConversationTurn:
    """A single Human → AI exchange."""
    human: str
    ai: str

class MemoryEntry:
    """Manages context retrieval and persistence for one session."""

    def __init__(self, session_id: str):
        self.session_id = session_id

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        """Append a new User/Assistant turn to persistent storage."""
        add_message(self.session_id, "user", str(user_message))
        add_message(self.session_id, "assistant", str(assistant_message))
        
        # If this is the first turn, generate a title
        session = get_session_db(self.session_id)
        if not session or not session.get("title") or session.get("title") == "New Chat":
            title = generate_chat_title(user_message)
            save_session(self.session_id, title)
            logger.info("Generated title for session %s: %s", self.session_id, title)

    def get_history_string(self) -> str:
        """Format history for prompt injection (last N turns)."""
        messages = get_messages(self.session_id)
        if not messages:
            return ""
        
        turns = []
        for i in range(0, len(messages), 2):
            if i + 1 < len(messages):
                turns.append((messages[i]["content"], messages[i+1]["content"]))
        
        # Trim to buffer limit
        start_idx = max(0, len(turns) - MAX_BUFFER_TURNS)
        recent_turns = turns[start_idx:]
        
        lines = []
        for human, ai in recent_turns:
            lines.append(f"Human: {human}")
            lines.append(f"AI: {ai[:500]}")
        return "\n".join(lines)

    def get_messages_list(self) -> List[Dict[str, Any]]:
        """Return raw messages for the API (flat list)."""
        return get_messages(self.session_id)

    def clear(self) -> None:
        """Reset messages but keep session ID."""
        clear_messages(self.session_id)

    @property
    def turn_count(self) -> int:
        messages = get_messages(self.session_id)
        return len(messages) // 2

def generate_chat_title(first_question: str) -> str:
    """Use Gemini to generate a short, catchy title from the first question."""
    prompt = f"Generate a very short (max 4 words) descriptive title for a chat that starts with this question: '{first_question}'. Return ONLY the title text, no quotes, no period."
    try:
        title = generate_text(prompt, temperature=0.7, max_tokens=20)
        if title:
            return title.strip().replace('"', '')
        # Fallback if response is empty/None
        raise ValueError("Empty response")
    except Exception as e:
        logger.warning("Failed to generate title: %s", e)
        # Fallback to first few words
        words = first_question.split()[:4]
        return " ".join(words) + "..."

# Public API (Mostly wrappers around DB)
def get_or_create_memory(session_id: str) -> MemoryEntry:
    """Retrieve/initialise session memory."""
    session = get_session_db(session_id)
    if not session:
        save_session(session_id, "New Chat")
        logger.info("New persistent session created: %s", session_id)
    return MemoryEntry(session_id)

def get_conversation_history(session_id: str) -> str:
    return MemoryEntry(session_id).get_history_string()

def save_turn(session_id: str, human_message: str, ai_message: str) -> None:
    get_or_create_memory(session_id).add_turn(human_message, ai_message)

def clear_session(session_id: str) -> None:
    MemoryEntry(session_id).clear()

def delete_session(session_id: str) -> None:
    delete_session_db(session_id)

def list_sessions() -> list[dict]:
    """Return all stored sessions."""
    return list_all_sessions()
