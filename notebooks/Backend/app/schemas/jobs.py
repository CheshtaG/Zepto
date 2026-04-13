from typing import List, Optional, Literal, Dict, Any, Union
from pydantic import BaseModel


class LocationPayload(BaseModel):
  name: Optional[str] = None
  city: Optional[str] = None
  pincode: Optional[str] = None
  lat: Optional[float] = None
  lng: Optional[float] = None
  source: Optional[Literal["geolocation", "ip", "manual"]] = None


class CreateJobRequest(BaseModel):
  items: List[str]
  platforms: List[str]
  metadata: Optional[Dict[str, Any]] = None


class AddItemsRequest(BaseModel):
  items: List[str]


class ClarifyItemsRequest(BaseModel):
  items: List[str]


class ClarificationQuestion(BaseModel):
  item: str
  prompt: str
  options: List[str]


class ClarifyItemsResponse(BaseModel):
  resolved_items: List[str]
  questions: List[ClarificationQuestion]


class JobStatusResponse(BaseModel):
  status: Literal["capturing", "extracting", "done", "failed"]
  progress: int
  message: Optional[str] = None


class JobItemMatch(BaseModel):
  platform: str
  price: Optional[float]
  in_stock: bool
  # CDN URL of the product thumbnail from the platform listing (preferred for UI).
  image_url: Optional[str] = None
  # Legacy alias; same as image_url when populated from scrapers.
  screenshot_url: Optional[str] = None
  image_source: Optional[str] = None
  image_confidence: Optional[float] = None
  image_match_reason: Optional[str] = None
  image_debug: Optional[Dict[str, Any]] = None
  quantity_label: Optional[str] = None
  quantity_base_value: Optional[float] = None
  quantity_base_unit: Optional[str] = None
  price_per_base_unit: Optional[float] = None
  quantity_comparable: Optional[bool] = None
  quantity_comparison_note: Optional[str] = None
  # Title text from that platform's search result card (what the site shows).
  listing_title: Optional[str] = None


class JobResultItem(BaseModel):
  query: str
  matches: List[JobItemMatch]
  canonical_title: Optional[str] = None
  canonical_subtitle: Optional[str] = None
  match_confidence: Optional[float] = None
  high_confidence: Optional[bool] = None
  comparison_mode: Optional[Literal["exact", "generic_comparable", "weak_partial"]] = None


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
  resolved_location: Optional[Union[LocationPayload, str]] = None
  metadata: Optional[Dict[str, Any]] = None
  status: Literal["capturing", "extracting", "done", "failed"] = "capturing"
  progress: int = 0
  result: Optional[JobResultResponse] = None
  error: Optional[str] = None

