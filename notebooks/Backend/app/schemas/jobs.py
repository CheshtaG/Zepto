from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel


class CreateJobRequest(BaseModel):
  items: List[str]
  platforms: List[str]
  location: Optional[str] = None


class JobStatusResponse(BaseModel):
  status: Literal["capturing", "extracting", "done", "failed"]
  progress: int
  message: Optional[str] = None


class JobItemMatch(BaseModel):
  platform: str
  price: Optional[float]
  in_stock: bool
  screenshot_url: Optional[str] = None


class JobResultItem(BaseModel):
  query: str
  matches: List[JobItemMatch]


class JobResultResponse(BaseModel):
  items: List[JobResultItem]
  summary: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
  role: str
  content: str


class ChatRequest(BaseModel):
  job_id: str
  messages: List[ChatMessage]


class ChatResponse(BaseModel):
  assistant_message: str
  actions: Optional[List[Dict[str, Any]]] = None


class JobState(BaseModel):
  id: str
  items: List[str]
  platforms: List[str]
  location: Optional[str] = None
  status: Literal["capturing", "extracting", "done", "failed"] = "capturing"
  progress: int = 0
  result: Optional[JobResultResponse] = None
  error: Optional[str] = None

