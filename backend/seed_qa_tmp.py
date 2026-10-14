from app.core.db import get_session_factory
from app.core.services import create_user

db = get_session_factory()
with db() as session:
    create_user(session, username="owner", password="qa-owner-123", full_name="QA Owner", role="dentiste", is_owner=True)
    session.commit()
    print("seeded")
