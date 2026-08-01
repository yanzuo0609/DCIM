from pydantic import BaseModel, Field


class ImportResult(BaseModel):
    created: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
