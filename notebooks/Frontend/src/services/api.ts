import { request } from '../lib/http'

export type Platform = 'blinkit' | 'zepto' | 'zomato'

export interface CreateJobRequest {
  items: string[]
  platforms: Platform[]
  location?: string
}

export interface CreateJobResponse {
  job_id: string
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
  screenshot_url?: string
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
}

