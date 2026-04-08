import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  Platform,
  JobResultResponse,
  JobStatusResponse,
  ChatMessage,
  AgentAction,
  LocationPayload,
} from '../services/api'

export interface JobHistoryEntry {
  jobId: string
  createdAt: string
  items: string[]
  platforms: Platform[]
  location?: string
}

export interface ToastState {
  message: string
  kind: 'error' | 'info'
}

interface PollingState {
  isPolling: boolean
  status?: JobStatusResponse
}

interface CompareViewState {
  sortByCheapest: boolean
  showOnlyInStock: boolean
}

interface AppState {
  lastPlatforms: Platform[]
  lastLocation?: string
  lastLocationPayload?: LocationPayload
  jobHistory: JobHistoryEntry[]
  chatsByJobId: Record<string, ChatMessage[]>
  resultsByJobId: Record<string, JobResultResponse | undefined>
  pollingByJobId: Record<string, PollingState>
  compareViewByJobId: Record<string, CompareViewState>
  toast?: ToastState

  setLastPlatforms: (platforms: Platform[]) => void
  setLastLocation: (loc: string) => void
  setLastLocationPayload: (payload?: LocationPayload) => void

  addJobHistory: (entry: JobHistoryEntry) => void

  setChatMessages: (jobId: string, messages: ChatMessage[]) => void
  appendChatMessage: (jobId: string, message: ChatMessage) => void

  setResult: (jobId: string, result: JobResultResponse | undefined) => void

  setPollingState: (jobId: string, state: Partial<PollingState>) => void

  setCompareViewState: (jobId: string, state: Partial<CompareViewState>) => void

  setToast: (toast?: ToastState) => void

  applyAgentActions: (jobId: string, actions: AgentAction[]) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      lastPlatforms: ['blinkit', 'zepto', 'zomato'],
      lastLocation: 'Pune',
      lastLocationPayload: undefined,
      jobHistory: [],
      chatsByJobId: {},
      resultsByJobId: {},
      pollingByJobId: {},
      compareViewByJobId: {},
      toast: undefined,

      setLastPlatforms(platforms) {
        set({ lastPlatforms: platforms })
      },

      setLastLocation(loc) {
        set({ lastLocation: loc })
      },

      setLastLocationPayload(payload) {
        set({ lastLocationPayload: payload })
      },

      addJobHistory(entry) {
        set((state) => {
          const existing = state.jobHistory.filter((e) => e.jobId !== entry.jobId)
          const updated = [entry, ...existing].slice(0, 5)
          return { jobHistory: updated }
        })
      },

      setChatMessages(jobId, messages) {
        set((state) => ({
          chatsByJobId: { ...state.chatsByJobId, [jobId]: messages },
        }))
      },

      appendChatMessage(jobId, message) {
        set((state) => {
          const existing = state.chatsByJobId[jobId] ?? []
          return {
            chatsByJobId: { ...state.chatsByJobId, [jobId]: [...existing, message] },
          }
        })
      },

      setResult(jobId, result) {
        set((state) => ({
          resultsByJobId: { ...state.resultsByJobId, [jobId]: result },
        }))
      },

      setPollingState(jobId, partial) {
        set((state) => ({
          pollingByJobId: {
            ...state.pollingByJobId,
            [jobId]: {
              isPolling: false,
              ...state.pollingByJobId[jobId],
              ...partial,
            },
          },
        }))
      },

      setCompareViewState(jobId, partial) {
        set((state) => ({
          compareViewByJobId: {
            ...state.compareViewByJobId,
            [jobId]: {
              sortByCheapest: false,
              showOnlyInStock: false,
              ...state.compareViewByJobId[jobId],
              ...partial,
            },
          },
        }))
      },

      setToast(toast) {
        set({ toast })
      },

      applyAgentActions(jobId, actions) {
        if (!actions?.length) return
        for (const action of actions) {
          if (action.type === 'FILTER_RESULTS') {
            const payload = action.payload ?? {}
            const showOnlyInStock = Boolean(payload.showOnlyInStock)
            const sortByCheapest = Boolean(payload.sortByCheapest)
            get().setCompareViewState(jobId, { showOnlyInStock, sortByCheapest })
          }
          // UPDATE_ITEMS and RERUN_JOB are handled at page level because they
          // need to trigger new API calls and update input UI.
        }
      },
    }),
    {
      name: 'zepto-compare-app',
      partialize: (state) => ({
        lastPlatforms: state.lastPlatforms,
        lastLocation: state.lastLocation,
        lastLocationPayload: state.lastLocationPayload,
        jobHistory: state.jobHistory,
        chatsByJobId: state.chatsByJobId,
        resultsByJobId: state.resultsByJobId,
        compareViewByJobId: state.compareViewByJobId,
      }),
    },
  ),
)

