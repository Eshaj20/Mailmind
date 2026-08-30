from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# The GmailOAuthUrl, GmailOAuthCallback, GmailAccountRead, EmailRead, ClassificationBatchRead, ClassificationSummaryRead, ThreadRead, GmailSyncResult, and SyncJobRead classes are Pydantic models that define the structure of data used for various operations related to Gmail integration in the application. 
 
# These models represent the data for OAuth authorization, Gmail account information, email details, classification summaries, email threads, synchronization results, and synchronization job status. They facilitate data validation and serialization for API responses and requests.


class AIUsageSummaryRead(BaseModel):
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    by_feature: dict[str, int]
    by_model: dict[str, int]
    since_days: int

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
    category: str | None
    priority: str | None
    needs_reply: bool | None
    classification_confidence: float | None
    classification_model_version: str | None
    classified_at: datetime | None

    model_config = {"from_attributes": True}


class EmailPageRead(BaseModel):
    items: list[EmailRead]
    total: int
    limit: int
    offset: int
    has_more: bool

class EmailSearchResultRead(BaseModel):
    email: EmailRead
    keyword_rank: int | None
    vector_rank: int | None
    keyword_score: float
    vector_score: float
    rrf_score: float
    match_reason: str


class EmailSearchResponse(BaseModel):
    query: str
    results: list[EmailSearchResultRead]


class SenderBreakdownRead(BaseModel):
    sender: str
    count: int


class CleanupSuggestionRead(BaseModel):
    suggestion_type: str
    title: str
    description: str
    email_count: int
    estimated_time_saved_minutes: int
    confidence: float
    candidate_emails: list[EmailRead]
    sender_breakdown: list[SenderBreakdownRead]
    oldest_days_pending: int | None


class InboxHealthRead(BaseModel):
    score: int
    total_emails: int
    unread_count: int
    high_priority_unread_count: int
    pending_reply_count: int
    aged_follow_up_count: int
    oldest_follow_up_days: int | None
    follow_up_age_days: int
    cleanup_candidate_count: int
    formula: str
    suggestions: list[CleanupSuggestionRead]



class CleanupPreviewItemRead(BaseModel):
    email: EmailRead
    reason: str
    suggested_action: str
    confidence: float


class CleanupPreviewRead(BaseModel):
    total_candidates: int
    estimated_time_saved_minutes: int
    items: list[CleanupPreviewItemRead]


class SenderInsightRead(BaseModel):
    sender: str
    total_emails: int
    unread_count: int
    cleanup_candidate_count: int
    pending_reply_count: int
    last_seen_at: datetime | None
    suggested_action: str
    confidence: float
    candidate_emails: list[EmailRead]


class CleanupActionRequest(BaseModel):
    email_ids: list[int] = Field(min_length=1, max_length=100)
    action: Literal["archive", "mark_read"]


class CleanupActionResultRead(BaseModel):
    action: str
    requested_count: int
    applied_count: int
    skipped_count: int
    emails: list[EmailRead]


class EmailFeedbackCreate(BaseModel):
    email_id: int
    feedback_type: str = Field(default="correction", min_length=1, max_length=32)
    corrected_category: str | None = Field(default=None, max_length=32)
    corrected_priority: str | None = Field(default=None, max_length=16)
    corrected_needs_reply: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class EmailFeedbackRead(BaseModel):
    id: int
    email_id: int
    feedback_type: str
    original_category: str | None
    corrected_category: str | None
    original_priority: str | None
    corrected_priority: str | None
    original_needs_reply: bool | None
    corrected_needs_reply: bool | None
    original_confidence: float | None
    model_version: str | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationReportRead(BaseModel):
    report_markdown: str

class ClassificationBatchRead(BaseModel):
    classified_count: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    needs_reply_count: int
    stage_counts: dict[str, int]


class ClassificationSummaryRead(BaseModel):
    total_classified: int
    total_unclassified: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    needs_reply_count: int


class ThreadRead(BaseModel):
    id: int
    gmail_thread_id: str
    subject: str | None
    snippet: str | None
    last_message_at: datetime | None
    summary: str | None
    summary_model_version: str | None
    summarized_at: datetime | None

    model_config = {"from_attributes": True}


class GmailSyncResult(BaseModel):
    account: GmailAccountRead
    synced_count: int
    created_count: int
    updated_count: int



class SyncHealthRead(BaseModel):
    total_jobs: int
    queued_jobs: int
    running_jobs: int
    retrying_jobs: int
    succeeded_jobs: int
    failed_jobs: int
    latest_status: str | None
    last_sync_at: datetime | None
    avg_synced_count: float
    error_counts: dict[str, int]

class SyncJobRead(BaseModel):
    id: int
    user_id: int
    gmail_account_id: int
    job_type: str
    status: str
    attempt_count: int
    max_attempts: int
    max_results: int
    synced_count: int
    created_count: int
    updated_count: int
    celery_task_id: str | None
    error_type: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}










