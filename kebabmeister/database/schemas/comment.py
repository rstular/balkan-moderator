import datetime
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from kebabmeister.database.schemas import Base


class SeenComment(Base):
    __tablename__ = "seen_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    seen_date: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    reddit_id: Mapped[str] = mapped_column(unique=True)
