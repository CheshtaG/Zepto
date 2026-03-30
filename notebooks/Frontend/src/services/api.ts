import { request } from '../lib/http'

// `zomato` is kept as a legacy alias used by the UI to mean Instamart.
export type Platform = 'blinkit' | 'zepto' | 'zomato' | 'instamart'

export interface LocationPayload {
  name?: string
  city?: string
  pincode?: string
  lat?: number
  lng?: number
  source?: 'geolocation' | 'ip' | 'manual'
}

export interface CreateJobRequest {
  items: string[]
  platforms: Platform[]
  location?: string | LocationPayload
}

export interface CreateJobResponse {
  job_id: string
}

export interface ClarificationQuestion {
  item: string
  prompt: string
  options: string[]
}

export interface ClarifyItemsResponse {
  resolved_items: string[]
  questions: ClarificationQuestion[]
}

export type JobStatusPhase = 'creating' | 'capturing' | 'extracting' | 'comparing' | 'done' | 'failed'

export interface JobStatusResponse {
  status: 'capturing' | 'extracting' | 'done' | 'failed'
  progress: number
  message?: string
  artifacts?: {
    screenshots?: { platform: Platform; item: string; url: string }[]
  }
}

export interface JobItemMatch {
  platform: Platform
  price: number | null
  in_stock: boolean
  /** Title shown on that platform's listing card. */
  listing_title?: string | null
  /** Product thumbnail URL from the platform (preferred). */
  image_url?: string
  /** @deprecated Same as image_url when set by backend */
  screenshot_url?: string
  quantity_label?: string | null
  quantity_base_value?: number | null
  quantity_base_unit?: string | null
  price_per_base_unit?: number | null
  quantity_comparable?: boolean | null
  quantity_comparison_note?: string | null
}

export interface JobResultItem {
  query: string
  matches: JobItemMatch[]
}

export interface JobResultSummary {
  cheapest_platform?: Platform
  notes?: string[]
}

export interface JobResultResponse {
  items: JobResultItem[]
  summary?: JobResultSummary
}

export interface DetectLocationResponse {
  location: LocationPayload | null
}

export type ChatRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  role: ChatRole
  content: string
}

export type AgentActionType = 'RERUN_JOB' | 'UPDATE_ITEMS' | 'FILTER_RESULTS'

export interface AgentAction {
  type: AgentActionType
  payload?: any
}

export interface ChatResponse {
  assistant_message: string
  actions?: AgentAction[]
}

export const api = {
  async createJob(payload: CreateJobRequest): Promise<CreateJobResponse> {
    return request<CreateJobResponse>({
      path: '/jobs',
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async addJobItems(jobId: string, items: string[]): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>({
      path: `/jobs/${encodeURIComponent(jobId)}/items`,
      method: 'POST',
      body: JSON.stringify({ items }),
    })
  },

  async clarifyItems(items: string[]): Promise<ClarifyItemsResponse> {
    return request<ClarifyItemsResponse>({
      path: '/items/clarify',
      method: 'POST',
      body: JSON.stringify({ items }),
    })
  },

  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    return request<JobStatusResponse>({
      path: `/jobs/${encodeURIComponent(jobId)}/status`,
      method: 'GET',
    })
  },

  async getJobResult(jobId: string): Promise<JobResultResponse> {
    return request<JobResultResponse>({
      path: `/jobs/${encodeURIComponent(jobId)}/result`,
      method: 'GET',
    })
  },

  async sendChat(jobId: string, messages: ChatMessage[]): Promise<ChatResponse> {
    return request<ChatResponse>({
      path: '/chat',
      method: 'POST',
      body: JSON.stringify({ job_id: jobId, messages }),
    })
  },

  async detectLocation(): Promise<DetectLocationResponse> {
    return request<DetectLocationResponse>({
      path: '/location/auto',
      method: 'GET',
    })
  },
}

