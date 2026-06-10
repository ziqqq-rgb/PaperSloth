from fastapi import APIRouter, Depends
from core.database import execute_query, execute_write
from core.security import get_current_user

router = APIRouter()


def _ensure_chat_history_table():
    execute_write("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id         SERIAL PRIMARY KEY,
            user_id    TEXT        NOT NULL,
            role       VARCHAR(20) NOT NULL,   -- 'user' | 'assistant'
            content    TEXT        NOT NULL,
            intent     VARCHAR(50),
            created_at TIMESTAMP   DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_chat_history_user
            ON chat_history(user_id, created_at DESC);
    """)

_ensure_chat_history_table()


@router.post("/history")
def save_message(
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """Frontend calls this after every message (user + assistant turns)."""
    execute_write(
        """INSERT INTO chat_history (user_id, role, content, intent)
           VALUES (%s, %s, %s, %s)""",
        (current_user["id"], body["role"], body["content"], body.get("intent")),
    )
    return {"ok": True}


@router.get("/history")
def get_history(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """Fetch the last N messages for the current user."""
    rows = execute_query(
        """SELECT role, content, intent, created_at
           FROM   chat_history
           WHERE  user_id = %s
           ORDER  BY created_at DESC
           LIMIT  %s""",
        (current_user["id"], limit),
    )
    # Return in chronological order
    messages = [
        {"role": r[0], "content": r[1], "intent": r[2], "created_at": str(r[3])}
        for r in reversed(rows or [])
    ]
    return {"messages": messages}


@router.delete("/history")
def clear_history(current_user: dict = Depends(get_current_user)):
    """Let the user start fresh."""
    execute_write(
        "DELETE FROM chat_history WHERE user_id = %s",
        (current_user["id"],),
    )
    return {"ok": True}