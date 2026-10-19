import secrets

from app.core.db import get_session_factory
from app.core.services import create_user

pwd = "QA-" + secrets.token_urlsafe(9)
db = get_session_factory()
with db() as session:
    create_user(session, username="owner", password=pwd, full_name="QA Owner", role="dentiste", is_owner=True)
    session.commit()
    print("seeded")
    print(f"QA LOGIN (single print): owner / {pwd}")
