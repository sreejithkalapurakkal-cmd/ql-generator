# Doc 1 — Frontend Implementation Plan (React)

## qlGen: ICP-Driven Qualified Lead Generation Tool

---

## 1. Architecture Design

```
+-----------------------------------------------------------+
|                    React SPA (Vite)                        |
|                                                            |
|  +-------------+  +----------------+  +----------------+   |
|  | ICP Form    |  | Job Tracker    |  | Results View   |   |
|  | Module      |  | Module         |  | Module         |   |
|  +------+------+  +-------+--------+  +-------+--------+   |
|         |                 |                    |            |
|  +------+-----------------+--------------------+--------+  |
|  |          State Management (React Hooks)                |  |
|  +------+------------------------------------------------+  |
|         |                                                   |
|  +------+------------------------------------------------+  |
|  |              API Client Layer (Axios)                  |  |
|  +------+------------------------------------------------+  |
|         |                                                   |
+---------|---------------------------------------------------+
          | HTTP/REST + SSE
          v
  +-------+--------+
  | Spring Boot    |
  | Backend API    |
  +----------------+
```

### Technology Stack

| Layer            | Technology         | Version   |
|------------------|--------------------|-----------|
| Framework        | React              | 18.x      |
| Build Tool       | Vite               | 5.x       |
| Language         | TypeScript         | 5.x       |
| State Management | React useState/useReducer | Built-in |
| HTTP Client      | Axios              | 1.x       |
| UI Components    | Material UI (MUI)        | 6.x       |
| Styling          | CSS Modules              | Built-in  |
| Routing          | React Router       | 6.x       |
| Forms            | React Hook Form + Yup | Latest    |
| Real-time        | EventSource (SSE)  | Native    |
| Charts           | Recharts           | 2.x       |

---

## 2. Internal Components / Modules

### 2.1 Module Breakdown

```
src/
├── components/
│   ├── icp-form/
│   │   ├── ICPFormPage.tsx          # Main form container
│   │   ├── CompanyProfileSection.tsx # Industry, size, revenue inputs
│   │   ├── TechStackSection.tsx     # Technology preferences
│   │   ├── GeographySection.tsx     # Location targeting
│   │   ├── BANTWeightsSection.tsx   # Budget/Authority/Need/Timeline weights
│   │   └── FormSummaryCard.tsx      # Pre-submission review
│   ├── job-tracker/
│   │   ├── JobListPage.tsx          # List of all submitted jobs
│   │   ├── JobCard.tsx              # Individual job status card
│   │   ├── JobProgressBar.tsx       # Step-by-step progress indicator
│   │   └── JobStatusBadge.tsx       # Status pill (PENDING/RUNNING/DONE/FAILED)
│   ├── results/
│   │   ├── ResultsDashboard.tsx     # Main results container
│   │   ├── LeadTable.tsx            # Sortable/filterable lead table
│   │   ├── LeadDetailDrawer.tsx     # Slide-out lead detail panel
│   │   ├── BANTScoreCard.tsx        # Visual BANT score breakdown
│   │   ├── ScoreDistributionChart.tsx # Score distribution histogram
│   │   └── ExportButton.tsx         # CSV/JSON export
│   ├── layout/
│   │   ├── AppShell.tsx             # Top-level layout wrapper
│   │   ├── Sidebar.tsx              # Navigation sidebar
│   │   ├── Header.tsx               # App header with branding
│   │   └── ErrorBoundary.tsx        # Global error boundary
│   └── shared/
│       ├── LoadingSpinner.tsx
│       ├── EmptyState.tsx
│       └── ToastNotification.tsx
├── hooks/
│   ├── useJobSubmit.ts              # Mutation hook for ICP submission
│   ├── useJobStatus.ts             # SSE subscription for job updates
│   ├── useJobList.ts               # Fetch all jobs
│   └── useJobResults.ts            # Fetch scored leads for a job
├── services/
│   ├── api.ts                       # Axios instance + interceptors
│   ├── jobService.ts               # Job CRUD API calls
│   └── sseClient.ts                # SSE connection manager
├── context/
│   └── AppContext.tsx               # React Context + useReducer for shared state
├── types/
│   ├── icp.ts                       # ICP form types
│   ├── job.ts                       # Job & status types
│   └── lead.ts                      # Lead & BANT score types
├── lib/
│   ├── validators.ts                # Yup schemas
│   └── formatters.ts               # Display formatting utils
├── theme/
│   └── theme.ts                     # MUI custom theme configuration
├── App.tsx
├── main.tsx
└── index.module.css                 # Global reset / base styles (CSS Module)
```

### 2.2 Key Component Responsibilities

| Component              | Responsibility                                                |
|------------------------|---------------------------------------------------------------|
| `ICPFormPage`          | Orchestrates multi-section ICP form, validates, submits       |
| `BANTWeightsSection`   | Sliders for Budget/Authority/Need/Timeline weight allocation  |
| `JobListPage`          | Polls/streams job statuses, shows history of all searches     |
| `JobProgressBar`       | Visualizes agent pipeline stages (Search → Enrich → Score)    |
| `ResultsDashboard`     | Displays ranked leads with filtering, sorting, and export     |
| `LeadDetailDrawer`     | Shows full company profile, BANT breakdown, enrichment data   |
| `BANTScoreCard`        | Radar chart or bar visualization of individual BANT scores    |

---

## 3. Communication Flow

### 3.1 API Contract with Backend

All communication is via REST + SSE to the Spring Boot backend. The frontend never communicates directly with the AI agent.

#### Endpoints Consumed

| Method | Endpoint                    | Purpose                           |
|--------|-----------------------------|-----------------------------------|
| POST   | `/api/v1/jobs`              | Submit new ICP search job         |
| GET    | `/api/v1/jobs`              | List all jobs for the session     |
| GET    | `/api/v1/jobs/{jobId}`      | Get job detail + status           |
| GET    | `/api/v1/jobs/{jobId}/leads`| Get scored leads for a completed job |
| GET    | `/api/v1/jobs/{jobId}/stream` | SSE stream for real-time status |
| GET    | `/api/v1/health`            | Backend health check              |

#### Request/Response Schemas

**POST /api/v1/jobs — Request Body:**
```json
{
  "icpProfile": {
    "industries": ["SaaS", "FinTech"],
    "companySizeRange": { "min": 50, "max": 500 },
    "revenueRange": { "min": 1000000, "max": 50000000 },
    "geographies": ["US", "UK", "Germany"],
    "techStack": ["AWS", "Kubernetes", "Python"],
    "keywords": ["AI-powered", "Series B"],
    "additionalNotes": "Prefer companies with recent funding rounds"
  },
  "bantWeights": {
    "budget": 0.30,
    "authority": 0.25,
    "need": 0.25,
    "timeline": 0.20
  },
  "maxResults": 25
}
```

**SSE Event Stream (`/api/v1/jobs/{jobId}/stream`):**
```
event: status
data: {"stage": "SEARCHING", "message": "Generating search queries...", "progress": 15}

event: status
data: {"stage": "ENRICHING", "message": "Enriching company: Acme Corp", "progress": 45}

event: status
data: {"stage": "SCORING", "message": "Applying BANT scoring...", "progress": 80}

event: complete
data: {"stage": "COMPLETED", "totalLeads": 18, "progress": 100}

event: error
data: {"stage": "FAILED", "message": "Rate limit exceeded on enrichment API"}
```

### 3.2 Sequence Diagram — Job Submission Flow

```
User        Frontend         Backend          AI Agent
 |              |                |                |
 |--Fill Form-->|                |                |
 |              |--POST /jobs--->|                |
 |              |<--201 {jobId}--|                |
 |              |                |--Dispatch----->|
 |              |--SSE connect-->|                |
 |              |<--status event-|<--progress-----|
 |              |<--status event-|<--progress-----|
 |              |<--complete-----|<--results------|
 |              |                |                |
 |              |--GET /leads--->|                |
 |              |<--lead list----|                |
 |<-View Results|                |                |
```

---

## 4. Deployment Architecture

### 4.1 Containerization

**Dockerfile:**
```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**nginx.conf:**
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8080/api/;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;            # Required for SSE
        proxy_cache off;
    }

    location / {
        try_files $uri $uri/ /index.html;  # SPA fallback
    }
}
```

### 4.2 Docker Compose Integration

```yaml
frontend:
  build: ./frontend
  ports:
    - "3000:80"
  depends_on:
    - backend
  environment:
    - VITE_API_BASE_URL=/api/v1
```

### 4.3 Local Development

```bash
npm create vite@latest qlgen-frontend -- --template react-ts
cd qlgen-frontend
npm install
npm run dev   # Starts on http://localhost:5173
```

Vite proxy for local dev (`vite.config.ts`):
```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});
```

---

## 5. Security Considerations

| Concern                  | Mitigation                                                    |
|--------------------------|---------------------------------------------------------------|
| XSS                      | React auto-escapes JSX; no `dangerouslySetInnerHTML` usage   |
| CSRF                     | API uses stateless auth; no cookies for session               |
| Input Validation         | Yup schemas validate all form inputs client-side              |
| API Key Exposure         | No API keys in frontend; all external calls routed via backend|
| Content Security Policy  | CSP headers set via nginx                                     |
| Dependency Vulnerabilities | `npm audit` in CI pipeline                                 |
| Environment Variables    | Only `VITE_API_BASE_URL` exposed; no secrets in frontend      |

### Input Validation Schema (Yup)

```typescript
import * as yup from 'yup';

export const icpProfileSchema = yup.object({
  industries: yup
    .array()
    .of(yup.string().min(1).required())
    .min(1, "At least one industry required")
    .required(),
  companySizeRange: yup.object({
    min: yup.number().integer().min(1).required(),
    max: yup.number().integer().min(1).required(),
  }).test("min-max", "Max must be >= min", (v) => (v?.max ?? 0) >= (v?.min ?? 0)),
  revenueRange: yup.object({
    min: yup.number().min(0).required(),
    max: yup.number().min(0).required(),
  }).test("min-max", "Max must be >= min", (v) => (v?.max ?? 0) >= (v?.min ?? 0)),
  geographies: yup.array().of(yup.string().required()).min(1).required(),
  techStack: yup.array().of(yup.string().required()).optional(),
  keywords: yup.array().of(yup.string().required()).optional(),
  additionalNotes: yup.string().max(1000).optional(),
});

export const bantWeightsSchema = yup.object({
  budget: yup.number().min(0).max(1).required(),
  authority: yup.number().min(0).max(1).required(),
  need: yup.number().min(0).max(1).required(),
  timeline: yup.number().min(0).max(1).required(),
}).test(
  "sum-to-one",
  "BANT weights must sum to 1.0",
  (v) => Math.abs((v?.budget ?? 0) + (v?.authority ?? 0) + (v?.need ?? 0) + (v?.timeline ?? 0) - 1.0) < 0.01
);
```

---

## 6. Error Handling Strategy

### 6.1 Layers of Error Handling

| Layer              | Strategy                                                      |
|--------------------|---------------------------------------------------------------|
| Global             | `ErrorBoundary` catches React render errors, shows fallback UI|
| API Layer          | Axios interceptors handle 4xx/5xx, show toast notifications   |
| SSE Connection     | Auto-reconnect with exponential backoff (max 5 retries)       |
| Form Validation    | Inline field errors via React Hook Form + Yup                 |
| Empty States       | Dedicated empty state components for no-data scenarios        |

### 6.2 Axios Error Interceptor

```typescript
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    if (status === 429) {
      toast.error("Rate limited. Please wait before retrying.");
    } else if (status >= 500) {
      toast.error("Server error. Please try again later.");
    } else if (status === 404) {
      toast.error("Resource not found.");
    } else if (!error.response) {
      toast.error("Network error. Check your connection.");
    }
    return Promise.reject(error);
  }
);
```

### 6.3 SSE Reconnection Logic

```typescript
function connectSSE(jobId: string, onEvent: (e: StatusEvent) => void) {
  let retries = 0;
  const maxRetries = 5;

  function connect() {
    const es = new EventSource(`/api/v1/jobs/${jobId}/stream`);

    es.addEventListener('status', (e) => {
      retries = 0; // Reset on success
      onEvent(JSON.parse(e.data));
    });

    es.addEventListener('complete', (e) => {
      onEvent(JSON.parse(e.data));
      es.close();
    });

    es.onerror = () => {
      es.close();
      if (retries < maxRetries) {
        const delay = Math.min(1000 * 2 ** retries, 30000);
        retries++;
        setTimeout(connect, delay);
      }
    };
  }

  connect();
}
```

---

## 7. Data Flow Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│                        FRONTEND DATA FLOW                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. USER INPUT                                                   │
│     User fills ICP form (industries, size, geo, BANT weights)    │
│              │                                                   │
│              v                                                   │
│  2. CLIENT VALIDATION                                            │
│     Yup schema validates all fields + BANT weight sum = 1.0      │
│              │                                                   │
│              v                                                   │
│  3. API SUBMISSION                                               │
│     POST /api/v1/jobs → receives jobId                           │
│              │                                                   │
│              v                                                   │
│  4. SSE SUBSCRIPTION                                             │
│     EventSource connects to /api/v1/jobs/{jobId}/stream          │
│     Updates component state → re-renders JobProgressBar          │
│              │                                                   │
│              v                                                   │
│  5. REAL-TIME STATUS UPDATES                                     │
│     stage: SEARCHING → ENRICHING → SCORING → COMPLETED           │
│     Each event updates progress percentage + status message       │
│              │                                                   │
│              v                                                   │
│  6. RESULTS FETCH                                                │
│     On COMPLETED: GET /api/v1/jobs/{jobId}/leads                 │
│     Leads stored in component state, rendered in LeadTable        │
│              │                                                   │
│              v                                                   │
│  7. DISPLAY & INTERACTION                                        │
│     User sorts/filters leads, views BANT breakdowns,             │
│     exports to CSV/JSON                                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### State Shape (React Context + useReducer)

```typescript
// State interface
interface AppState {
  jobs: Job[];
  activeJobId: string | null;
  jobProgress: Record<string, JobProgress>;
  leads: Record<string, Lead[]>;  // keyed by jobId
}

// Action types
type AppAction =
  | { type: 'SET_JOBS'; payload: Job[] }
  | { type: 'ADD_JOB'; payload: Job }
  | { type: 'SET_ACTIVE_JOB'; payload: string | null }
  | { type: 'UPDATE_PROGRESS'; payload: { jobId: string; progress: JobProgress } }
  | { type: 'SET_LEADS'; payload: { jobId: string; leads: Lead[] } };

// Reducer
function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_JOBS':
      return { ...state, jobs: action.payload };
    case 'ADD_JOB':
      return { ...state, jobs: [...state.jobs, action.payload] };
    case 'SET_ACTIVE_JOB':
      return { ...state, activeJobId: action.payload };
    case 'UPDATE_PROGRESS':
      return {
        ...state,
        jobProgress: { ...state.jobProgress, [action.payload.jobId]: action.payload.progress },
      };
    case 'SET_LEADS':
      return {
        ...state,
        leads: { ...state.leads, [action.payload.jobId]: action.payload.leads },
      };
    default:
      return state;
  }
}

// Context
const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
} | null>(null);

// Provider wraps <App />
function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

// Hook for consuming components
function useAppState() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppState must be used within AppProvider');
  return ctx;
}
```

---

## 8. Scalability Considerations

| Concern                  | Approach                                                      |
|--------------------------|---------------------------------------------------------------|
| Large Result Sets        | Paginated lead table (25 items/page), virtual scrolling if >100 |
| Multiple Concurrent Jobs | State keyed by jobId via useReducer; each SSE connection independent |
| Bundle Size              | Vite code splitting per route; lazy-load Results module        |
| API Call Efficiency      | Debounce form auto-save; no polling (SSE replaces it)         |
| Offline Resilience       | Service worker caching of static assets (future enhancement)  |
| CDN Delivery             | Static build artifacts served from CDN in production          |

### Route-Based Code Splitting

```typescript
const ICPFormPage = lazy(() => import('./components/icp-form/ICPFormPage'));
const JobListPage = lazy(() => import('./components/job-tracker/JobListPage'));
const ResultsDashboard = lazy(() => import('./components/results/ResultsDashboard'));
```

---

## 9. Observability

### 9.1 Structured Logging

```typescript
const logger = {
  info: (event: string, data?: Record<string, unknown>) =>
    console.log(JSON.stringify({ level: 'info', event, ...data, ts: Date.now() })),
  error: (event: string, error: unknown, data?: Record<string, unknown>) =>
    console.error(JSON.stringify({ level: 'error', event, error: String(error), ...data, ts: Date.now() })),
};

// Usage
logger.info('job_submitted', { jobId, industries: icp.industries });
logger.error('sse_connection_failed', err, { jobId, retryCount: retries });
```

### 9.2 Health & Diagnostics

| Check              | Implementation                                                |
|--------------------|---------------------------------------------------------------|
| Backend Reachable  | Periodic `GET /api/v1/health` — show banner if down           |
| SSE Connected      | Connection state tracked in store — show reconnecting indicator|
| Build Info         | Version + commit SHA injected via `VITE_APP_VERSION` env var  |

### 9.3 User-Facing Error Tracking

- Toast notifications for API errors (non-blocking)
- Inline form validation errors (per-field)
- Full-page error boundary for unrecoverable failures
- Job failure state displayed with error message from backend

---

## 10. Production Readiness Checklist

| #  | Item                                         | Status |
|----|----------------------------------------------|--------|
| 1  | All form inputs validated with Yup schemas   | [ ]    |
| 2  | SSE reconnection with exponential backoff    | [ ]    |
| 3  | Error boundary wrapping entire app            | [ ]    |
| 4  | Responsive layout (desktop + tablet minimum) | [ ]    |
| 5  | Loading states for all async operations      | [ ]    |
| 6  | Empty states for zero-data scenarios         | [ ]    |
| 7  | CORS properly configured via nginx proxy     | [ ]    |
| 8  | No API keys or secrets in frontend bundle    | [ ]    |
| 9  | Production build tested (`npm run build`)    | [ ]    |
| 10 | Docker image builds and runs successfully    | [ ]    |
| 11 | Nginx serves SPA with history API fallback   | [ ]    |
| 12 | SSE proxy pass configured (no buffering)     | [ ]    |
| 13 | CSP headers configured in nginx              | [ ]    |
| 14 | `npm audit` shows no high/critical vulns     | [ ]    |
| 15 | Export (CSV/JSON) tested with large datasets  | [ ]    |

---

## Appendix: Quick Start Commands

```bash
# Initialize project
npm create vite@latest qlgen-frontend -- --template react-ts
cd qlgen-frontend

# Install dependencies
npm install axios react-router-dom react-hook-form yup @hookform/resolvers recharts @mui/material @mui/icons-material @emotion/react @emotion/styled

# Run development server
npm run dev

# Build for production
npm run build

# Docker build
docker build -t qlgen-frontend .
```
