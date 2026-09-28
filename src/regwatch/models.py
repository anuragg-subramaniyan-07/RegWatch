from datetime import datetime

from pydantic import BaseModel, HttpUrl


class Reference(BaseModel):
    notification_id: int
    title: str
    link: HttpUrl
    pub_date: datetime
