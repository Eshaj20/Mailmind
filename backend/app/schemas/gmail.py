from datetime import datetime

from pydantic import BaseModel, Field


class GmailOAuthUrl(BaseModel):
    authorization_url: str


class GmailOAuthCallback(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)


class GmailAccountRead(BaseModel):
    id: int
    google_email: str
    history_id: str | None
    sync_status: str
    last_synced_at: datetime | None

    model_config = {"from_attributes": True}


class EmailRead(BaseModel):
    id: int
    gmail_message_id: str
    sender: str | None
    recipients: str | None
    subject: str | None
    snippet: str | None
    labels: list[str] | None
    is_read: bool
    received_at: datetime | None

    model_config = {"from_attributes": True}


class GmailSyncResult(BaseModel):
    account: GmailAccountRead
    synced_count: int
    created_count: int
    updated_count: int
