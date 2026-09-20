"""Import actors for the Dramatiq worker process."""

from .jobs import process_document_job

__all__ = ["process_document_job"]
