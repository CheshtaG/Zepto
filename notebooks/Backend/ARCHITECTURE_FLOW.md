# Project Architecture Flow (Frontend + Backend)

This flowchart shows the main runtime path for the price + availability comparison platform:

- User enters a list of items on the frontend
- Frontend creates a backend "job"
- Frontend polls job status and fetches results incrementally
- Frontend renders a comparison view
- Frontend supports agentic chat, which can trigger structured actions (e.g., re-run job)

```mermaid
flowchart TD
  %% =======================
  %% FRONTEND (React)
  %% =======================
  subgraph FE[Frontend (React + Vite)]
    A[Input UI<br/>Centered textbox + Enter button] --> B[Normalize items<br/>(split lines/commas, trim, lowercase unique)]
    B --> C[POST /api/jobs<br/>{ items, platforms, location? }]
    C --> D[Job progress UI (stepper + progress bar)]
    D --> E[Poll GET /api/jobs/:jobId/status<br/>every ~2-3s]
    E --> F{status?}
    F -->|capturing/extracting| G[Optionally re-fetch GET /api/jobs/:jobId/result<br/>for partial updates]
    F -->|done| H[Fetch final GET /api/jobs/:jobId/result]
    F -->|failed| I[Show error + allow retry]
    G --> J[Render results UI<br/>Item cards + platform match cards<br/>with screenshot/image thumbnails]
    H --> J
    J --> K[Chat UI (left panel on compare page)]
    K --> L[POST /api/chat<br/>{ job_id, messages[] }]
    L --> M[Handle agentic actions from response<br/>actions[]]
    M -->|RERUN_JOB| N[Create new job via POST /api/jobs<br/>navigate to /compare/:newJobId]
    M -->|UPDATE_ITEMS| O[Update UI items list (client-side UX)]
    M -->|FILTER_RESULTS| P[Apply client-side filtering/sorting]
  end

  %% =======================
  %% BACKEND (FastAPI)
  %% =======================
  subgraph BE[Backend (FastAPI)]
    Q[FastAPI App<br/>routers mounted + shared services in app.state] --> R[POST /api/jobs]
    R --> S[Create job placeholder in memory<br/>JobState: status=capturing, progress=0, empty matches]
    S --> T[asyncio.create_task(run_job(job_id))]
    T --> U[run_job(job_id)]
    U --> V[Scrape/enrich across platforms<br/>Zepto/Blinkit/Instamart (server-side)]
    V --> W[Update job.progress + write partial results<br/>as each platform finishes]
    W --> X{All items processed?}
    X -->|yes| Y[status=done, progress=100,<br/>final JobResultResponse]
    X -->|error| Z[status=failed<br/>error message]
    R --> AA[Return { job_id } immediately]

    E --> AB[GET /api/jobs/:jobId/status<br/>(in-memory state)]
    H --> AC[GET /api/jobs/:jobId/result<br/>(in-memory state)]
    L --> AD[POST /api/chat]
    AD --> AE[LLM clarification and/or action planning<br/>(current POC may stub actions)]
    AE --> AF[Return { assistant_message, actions[] }]

    %% Add-items path used for agent-driven “add more items”
    subgraph ADDPATH[Add items for existing job]
      AG[POST /api/jobs/:jobId/items<br/>{ items } ] --> AH[JobManager.add_items()<br/>append items + scrape only new ones]
      AH --> W2[Update partial results and progress]
    end
  end

  %% =======================
  %% Cross-links
  %% =======================
  C --- R
  AB --- E
  AC --- H
  F --- E
  L --- AD

  %% =======================
  %% Styling Notes
  %% =======================
  %% - Screenshots are produced server-side via Playwright scrapers
  %% - Frontend uses backend-provided image URLs for thumbnails/previews
```

## Endpoint Contract (what the frontend expects)

- `POST /api/jobs`
  - Request: `{ items: string[], platforms: string[], location?: string | {name, city, pincode, lat, lng} }`
  - Response: `{ job_id: string }`

- `GET /api/jobs/:jobId/status`
  - Response: `{ status: "capturing" | "extracting" | "done" | "failed", progress: number, message?: string }`

- `GET /api/jobs/:jobId/result`
  - Response: `{ items: [{ query: string, matches: [{ platform, price, in_stock, image_url/screenshot_url }] }], summary?: ... }`

- `POST /api/chat`
  - Request: `{ job_id, messages: [{ role, content }] }`
  - Response: `{ assistant_message, actions?: [...] }`

## Incremental Rendering Strategy

- Backend returns a job immediately with placeholder rows.
- Frontend keeps polling status and re-fetches results while the job is running (so the table/cards fill in gradually).

