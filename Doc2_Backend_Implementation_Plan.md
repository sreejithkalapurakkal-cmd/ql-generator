# Doc 2 — Backend Implementation Plan (Spring Boot)

## qlGen: ICP-Driven Qualified Lead Generation Tool

---

## 1. Architecture Design

```
                           ┌──────────────┐
                           │   Frontend   │
                           │   (React)    │
                           └──────┬───────┘
                                  │ REST + SSE
                                  v
┌─────────────────────────────────────────────────────────────────┐
│                     Spring Boot Backend                         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  REST API    │  │  Job         │  │  SSE Event           │  │
│  │  Controllers │──│  Orchestrator│──│  Publisher            │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────────┴───────────┐  │
│  │  Validation  │  │  Agent       │  │  Event               │  │
│  │  Layer       │  │  Client      │  │  Store               │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────────┘  │
│                           │                                     │
│  ┌────────────────────────┴─────────────────────────────────┐  │
│  │                  JPA Repository Layer                     │  │
│  │              (PostgreSQL dev + prod)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                  │ HTTP/REST
                                  v
                         ┌────────────────┐
                         │  Python Agent  │
                         │  (Strands)     │
                         └────────────────┘
```

### Technology Stack

| Layer              | Technology           | Version   |
|--------------------|----------------------|-----------|
| Framework          | Spring Boot          | 3.3.x     |
| Language           | Java                 | 21        |
| Build Tool         | Maven                | 3.9.x     |
| Database (Dev)     | PostgreSQL           | 16.x      |
| Database (Prod)    | PostgreSQL           | 16.x      |
| ORM                | Spring Data JPA      | 3.3.x     |
| Validation         | Jakarta Validation   | 3.0       |
| SSE                | Spring MVC SseEmitter| Built-in  |
| HTTP Client        | Spring WebClient     | 6.x       |
| API Docs           | SpringDoc OpenAPI    | 2.x       |
| Async Processing   | Spring @Async + ThreadPoolTaskExecutor | Built-in |
| JSON               | Jackson              | 2.17.x    |

---

## 2. Internal Components / Modules

### 2.1 Package Structure

```
src/main/java/com/qlgen/backend/
├── QlgenBackendApplication.java
├── config/
│   ├── AsyncConfig.java              # Thread pool for async job execution
│   ├── WebConfig.java                # CORS configuration
│   ├── WebClientConfig.java          # WebClient bean for agent communication
│   └── OpenApiConfig.java            # Swagger/OpenAPI setup
├── controller/
│   ├── JobController.java            # REST endpoints for job CRUD + SSE
│   └── HealthController.java         # Health check endpoint
├── dto/
│   ├── request/
│   │   ├── ICPProfileRequest.java    # ICP form submission DTO
│   │   └── BANTWeightsRequest.java   # BANT weight allocation DTO
│   ├── response/
│   │   ├── JobResponse.java          # Job status response
│   │   ├── LeadResponse.java         # Scored lead response
│   │   └── ErrorResponse.java        # Standardized error response
│   └── agent/
│       ├── AgentRequest.java         # Payload sent to Python agent
│       └── AgentResult.java          # Result received from Python agent
├── entity/
│   ├── Job.java                      # Job entity (JPA)
│   ├── Lead.java                     # Lead entity (JPA)
│   └── enums/
│       └── JobStatus.java            # PENDING, SEARCHING, ENRICHING, SCORING, COMPLETED, FAILED
├── repository/
│   ├── JobRepository.java            # JPA repository for jobs
│   └── LeadRepository.java           # JPA repository for leads
├── service/
│   ├── JobService.java               # Job lifecycle management
│   ├── JobOrchestrator.java          # Async job execution + agent dispatch
│   ├── AgentClient.java              # HTTP client to Python agent
│   └── SseService.java              # SSE emitter management + event publishing
├── exception/
│   ├── GlobalExceptionHandler.java   # @ControllerAdvice error handler
│   ├── JobNotFoundException.java
│   └── AgentCommunicationException.java
└── mapper/
    ├── JobMapper.java                # Entity <-> DTO mapping
    └── LeadMapper.java               # Entity <-> DTO mapping
```

### 2.2 Module Responsibilities

| Module              | Responsibility                                                |
|---------------------|---------------------------------------------------------------|
| `JobController`     | Accepts ICP submissions, returns job status, streams SSE events |
| `JobService`        | CRUD operations on jobs, status transitions, validation        |
| `JobOrchestrator`   | Async job runner — dispatches to agent, processes results, updates DB |
| `AgentClient`       | WebClient-based HTTP client to communicate with Python agent   |
| `SseService`        | Manages active SSE emitter connections, publishes status events|
| `GlobalExceptionHandler` | Converts exceptions to standardized JSON error responses  |

---

## 3. Communication Flow

### 3.1 Frontend ↔ Backend (REST + SSE)

#### API Endpoints

| Method | Path                          | Description                     | Auth |
|--------|-------------------------------|---------------------------------|------|
| POST   | `/api/v1/jobs`                | Submit new ICP job              | None |
| GET    | `/api/v1/jobs`                | List all jobs                   | None |
| GET    | `/api/v1/jobs/{jobId}`        | Get single job with status      | None |
| GET    | `/api/v1/jobs/{jobId}/leads`  | Get scored leads for a job      | None |
| GET    | `/api/v1/jobs/{jobId}/stream` | SSE real-time status stream     | None |
| GET    | `/api/v1/health`              | Health check                    | None |

#### Controller Implementation

```java
@RestController
@RequestMapping("/api/v1/jobs")
public class JobController {

    @PostMapping
    public ResponseEntity<JobResponse> createJob(@Valid @RequestBody ICPProfileRequest request) {
        JobResponse job = jobService.createAndDispatch(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(job);
    }

    @GetMapping("/{jobId}")
    public ResponseEntity<JobResponse> getJob(@PathVariable UUID jobId) {
        return ResponseEntity.ok(jobService.getJob(jobId));
    }

    @GetMapping("/{jobId}/leads")
    public ResponseEntity<List<LeadResponse>> getLeads(@PathVariable UUID jobId) {
        return ResponseEntity.ok(jobService.getLeads(jobId));
    }

    @GetMapping("/{jobId}/stream")
    public SseEmitter streamJobStatus(@PathVariable UUID jobId) {
        return sseService.createEmitter(jobId);
    }
}
```

### 3.2 Backend → Agent (HTTP/REST)

The backend calls the Python agent via REST to dispatch ICP processing jobs.

#### Agent API Contract

**POST `http://agent:8000/api/v1/process`**

Request:
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "icpProfile": {
    "industries": ["SaaS", "FinTech"],
    "companySizeRange": { "min": 50, "max": 500 },
    "revenueRange": { "min": 1000000, "max": 50000000 },
    "geographies": ["US", "UK"],
    "techStack": ["AWS", "Kubernetes"],
    "keywords": ["AI-powered", "Series B"],
    "additionalNotes": "Prefer recently funded companies"
  },
  "bantWeights": {
    "budget": 0.30,
    "authority": 0.25,
    "need": 0.25,
    "timeline": 0.20
  },
  "maxResults": 25,
  "callbackUrl": "http://backend:8080/api/v1/internal/jobs/550e.../callback"
}
```

**Callback from Agent → Backend:**

**POST `http://backend:8080/api/v1/internal/jobs/{jobId}/callback`**

```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "leads": [
    {
      "companyName": "Acme Corp",
      "domain": "acmecorp.com",
      "industry": "SaaS",
      "employeeCount": 250,
      "estimatedRevenue": 15000000,
      "location": "San Francisco, US",
      "description": "Cloud-based project management platform",
      "techStack": ["AWS", "Python", "React"],
      "fundingStage": "Series B",
      "bantScore": {
        "budget": 8.5,
        "authority": 7.0,
        "need": 9.0,
        "timeline": 6.5,
        "total": 7.85,
        "reasoning": "Strong budget indicators from recent $20M Series B..."
      }
    }
  ]
}
```

### 3.3 Internal Status Update (Agent → Backend → Frontend)

The agent sends progress updates to the backend callback endpoint. The backend publishes these as SSE events to connected frontends.

**POST `http://backend:8080/api/v1/internal/jobs/{jobId}/progress`**

```json
{
  "jobId": "550e8400-...",
  "stage": "ENRICHING",
  "message": "Enriching company data: 12/25 complete",
  "progress": 48
}
```

### 3.4 Sequence Diagram

```
Frontend          Backend              Agent
   │                 │                    │
   │──POST /jobs────>│                    │
   │<──201 {jobId}───│                    │
   │                 │──POST /process────>│
   │──GET /stream───>│                    │
   │                 │<──POST /progress───│  (SEARCHING)
   │<──SSE event─────│                    │
   │                 │<──POST /progress───│  (ENRICHING)
   │<──SSE event─────│                    │
   │                 │<──POST /progress───│  (SCORING)
   │<──SSE event─────│                    │
   │                 │<──POST /callback───│  (COMPLETED + leads)
   │<──SSE complete──│                    │
   │                 │                    │
   │──GET /leads────>│                    │
   │<──lead list─────│                    │
```

---

## 4. Deployment Architecture

### 4.1 Dockerfile

```dockerfile
# Build stage
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn package -DskipTests -B

# Runtime stage
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /app/target/qlgen-backend-*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

### 4.2 Docker Compose Service

```yaml
backend:
  build: ./backend
  ports:
    - "8080:8080"
  environment:
    - SPRING_PROFILES_ACTIVE=dev
    - AGENT_BASE_URL=http://agent:8000
    - SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/qlgen
    - SPRING_DATASOURCE_USERNAME=qlgen
    - SPRING_DATASOURCE_PASSWORD=${DB_PASSWORD}
  depends_on:
    - agent
    - postgres
```

### 4.3 Database Service (Docker Compose)

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: qlgen
    POSTGRES_USER: qlgen
    POSTGRES_PASSWORD: ${DB_PASSWORD:-qlgen_dev}
  volumes:
    - pgdata:/var/lib/postgresql/data
  ports:
    - "5432:5432"

volumes:
  pgdata:
```

### 4.4 Production Profile

```yaml
# application-prod.yml
spring:
  datasource:
    url: jdbc:postgresql://${DB_HOST}:5432/qlgen
    username: ${DB_USER}
    password: ${DB_PASSWORD}
  jpa:
    hibernate:
      ddl-auto: validate
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
```

---

## 5. Security Considerations

| Concern                  | Mitigation                                                    |
|--------------------------|---------------------------------------------------------------|
| Input Validation         | Jakarta Bean Validation on all request DTOs                   |
| SQL Injection            | JPA parameterized queries only (no raw SQL)                   |
| Internal Endpoints       | `/api/v1/internal/**` restricted to container network only    |
| CORS                     | Explicit origin whitelist via `WebConfig`                     |
| Secrets Management       | Environment variables for DB creds, agent URL                 |
| API Keys                 | All third-party API keys stored only in agent service         |
| Rate Limiting            | Max concurrent jobs per session (configurable, default: 5)    |
| Payload Size             | `spring.servlet.multipart.max-request-size=1MB`              |

### CORS Configuration

```java
@Configuration
public class WebConfig implements WebMvcConfigurer {
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins("http://localhost:3000", "http://localhost:5173")
                .allowedMethods("GET", "POST")
                .allowedHeaders("*");
    }
}
```

### Internal Endpoint Security

```java
@RestController
@RequestMapping("/api/v1/internal/jobs")
public class InternalJobController {
    // These endpoints are only accessible within the Docker network.
    // In production, use Spring Security + API key header for internal comms.

    @PostMapping("/{jobId}/callback")
    public ResponseEntity<Void> agentCallback(
            @PathVariable UUID jobId,
            @RequestBody AgentResult result) {
        jobOrchestrator.handleAgentResult(jobId, result);
        return ResponseEntity.ok().build();
    }

    @PostMapping("/{jobId}/progress")
    public ResponseEntity<Void> agentProgress(
            @PathVariable UUID jobId,
            @RequestBody ProgressUpdate update) {
        sseService.publishProgress(jobId, update);
        return ResponseEntity.ok().build();
    }
}
```

---

## 6. Error Handling Strategy

### 6.1 Global Exception Handler

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(JobNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(JobNotFoundException ex) {
        return ResponseEntity.status(404)
            .body(new ErrorResponse("JOB_NOT_FOUND", ex.getMessage()));
    }

    @ExceptionHandler(AgentCommunicationException.class)
    public ResponseEntity<ErrorResponse> handleAgentError(AgentCommunicationException ex) {
        return ResponseEntity.status(502)
            .body(new ErrorResponse("AGENT_UNREACHABLE", "AI agent is not responding"));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        String details = ex.getBindingResult().getFieldErrors().stream()
            .map(e -> e.getField() + ": " + e.getDefaultMessage())
            .collect(Collectors.joining(", "));
        return ResponseEntity.status(400)
            .body(new ErrorResponse("VALIDATION_ERROR", details));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneral(Exception ex) {
        log.error("Unexpected error", ex);
        return ResponseEntity.status(500)
            .body(new ErrorResponse("INTERNAL_ERROR", "An unexpected error occurred"));
    }
}
```

### 6.2 Agent Communication Retry

```java
@Service
public class AgentClient {
    private final WebClient webClient;

    public void dispatchJob(AgentRequest request) {
        webClient.post()
            .uri("/api/v1/process")
            .bodyValue(request)
            .retrieve()
            .toBodilessEntity()
            .retryWhen(Retry.backoff(3, Duration.ofSeconds(2))
                .maxBackoff(Duration.ofSeconds(10))
                .filter(ex -> ex instanceof WebClientResponseException.ServiceUnavailable
                           || ex instanceof ConnectException))
            .doOnError(ex -> {
                log.error("Agent dispatch failed for job {}", request.getJobId(), ex);
                jobService.markFailed(request.getJobId(), "Agent unreachable after retries");
            })
            .subscribe();
    }
}
```

### 6.3 Job Timeout Handling

```java
@Scheduled(fixedRate = 60000) // Every minute
public void checkStalledJobs() {
    List<Job> stalled = jobRepository.findByStatusInAndUpdatedAtBefore(
        List.of(JobStatus.SEARCHING, JobStatus.ENRICHING, JobStatus.SCORING),
        Instant.now().minus(10, ChronoUnit.MINUTES)
    );
    stalled.forEach(job -> {
        job.setStatus(JobStatus.FAILED);
        job.setErrorMessage("Job timed out after 10 minutes");
        jobRepository.save(job);
        sseService.publishError(job.getId(), "Job timed out");
    });
}
```

---

## 7. Data Flow Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│                       BACKEND DATA FLOW                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. RECEIVE ICP SUBMISSION                                       │
│     POST /api/v1/jobs → Validate DTO → Create Job entity         │
│     Status: PENDING                                              │
│              │                                                   │
│              v                                                   │
│  2. PERSIST JOB                                                  │
│     Save Job to DB with status PENDING                           │
│     Return 201 with jobId to frontend                            │
│              │                                                   │
│              v                                                   │
│  3. ASYNC DISPATCH TO AGENT                                      │
│     @Async → Build AgentRequest → POST to agent /process         │
│     Include callbackUrl for results delivery                     │
│     Status: SEARCHING                                            │
│              │                                                   │
│              v                                                   │
│  4. STREAM PROGRESS EVENTS                                       │
│     Agent POSTs progress to /internal/jobs/{id}/progress         │
│     Backend publishes to SseEmitter for connected frontend       │
│     Status transitions: SEARCHING → ENRICHING → SCORING          │
│              │                                                   │
│              v                                                   │
│  5. RECEIVE AGENT RESULTS                                        │
│     Agent POSTs final results to /internal/jobs/{id}/callback    │
│     Parse leads, compute any server-side aggregations            │
│              │                                                   │
│              v                                                   │
│  6. PERSIST LEADS                                                │
│     Save Lead entities to DB, linked to Job                      │
│     Status: COMPLETED                                            │
│              │                                                   │
│              v                                                   │
│  7. SERVE RESULTS                                                │
│     GET /api/v1/jobs/{id}/leads → Return ranked lead list        │
│     SSE complete event sent to frontend                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 7.1 Entity Model

```java
@Entity
@Table(name = "jobs")
public class Job {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(columnDefinition = "TEXT")
    private String icpProfileJson;      // Stored as JSON string

    @Column(columnDefinition = "TEXT")
    private String bantWeightsJson;

    @Enumerated(EnumType.STRING)
    private JobStatus status;

    private int maxResults;
    private String errorMessage;
    private Instant createdAt;
    private Instant updatedAt;

    @OneToMany(mappedBy = "job", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<Lead> leads;
}

@Entity
@Table(name = "leads")
public class Lead {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "job_id")
    private Job job;

    private String companyName;
    private String domain;
    private String industry;
    private Integer employeeCount;
    private Long estimatedRevenue;
    private String location;

    @Column(columnDefinition = "TEXT")
    private String description;

    private String techStackJson;       // JSON array
    private String fundingStage;

    // BANT Scores
    private Double budgetScore;
    private Double authorityScore;
    private Double needScore;
    private Double timelineScore;
    private Double totalScore;

    @Column(columnDefinition = "TEXT")
    private String bantReasoning;

    private Integer rank;
}
```

---

## 8. Scalability Considerations

| Concern                  | Approach                                                      |
|--------------------------|---------------------------------------------------------------|
| Async Job Processing     | `@Async` with configurable `ThreadPoolTaskExecutor`           |
| SSE Connection Management| Emitters stored in `ConcurrentHashMap`, cleaned on timeout/complete |
| Database Scaling         | PostgreSQL with connection pooling (HikariCP) for dev and prod |
| Concurrent Jobs          | Thread pool limits concurrent agent dispatches (default: 10)  |
| Stateless Backend        | No server-side session; horizontally scalable behind load balancer |
| Result Pagination        | Spring Data `Pageable` on lead queries for large result sets  |

### Async Configuration

```java
@Configuration
@EnableAsync
public class AsyncConfig {
    @Bean
    public TaskExecutor jobTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(10);
        executor.setQueueCapacity(25);
        executor.setThreadNamePrefix("job-exec-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();
        return executor;
    }
}
```

### SSE Emitter Management

```java
@Service
public class SseService {
    private final ConcurrentHashMap<UUID, List<SseEmitter>> emitters = new ConcurrentHashMap<>();

    public SseEmitter createEmitter(UUID jobId) {
        SseEmitter emitter = new SseEmitter(600_000L); // 10 min timeout
        emitters.computeIfAbsent(jobId, k -> new CopyOnWriteArrayList<>()).add(emitter);

        emitter.onCompletion(() -> removeEmitter(jobId, emitter));
        emitter.onTimeout(() -> removeEmitter(jobId, emitter));
        emitter.onError(e -> removeEmitter(jobId, emitter));

        return emitter;
    }

    public void publishProgress(UUID jobId, ProgressUpdate update) {
        List<SseEmitter> jobEmitters = emitters.getOrDefault(jobId, List.of());
        jobEmitters.forEach(emitter -> {
            try {
                emitter.send(SseEmitter.event()
                    .name("status")
                    .data(update));
            } catch (IOException e) {
                removeEmitter(jobId, emitter);
            }
        });
    }

    public void publishComplete(UUID jobId, int totalLeads) {
        // Send complete event and close all emitters for this job
    }

    private void removeEmitter(UUID jobId, SseEmitter emitter) {
        List<SseEmitter> list = emitters.get(jobId);
        if (list != null) list.remove(emitter);
    }
}
```

---

## 9. Observability

### 9.1 Structured Logging (Logback + SLF4J)

```xml
<!-- logback-spring.xml -->
<configuration>
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder"/>
    </appender>
    <root level="INFO">
        <appender-ref ref="CONSOLE"/>
    </root>
</configuration>
```

Usage in services:
```java
log.info("Job created: jobId={}, industries={}", job.getId(), icp.getIndustries());
log.info("Agent dispatched: jobId={}, agentUrl={}", jobId, agentBaseUrl);
log.warn("SSE emitter timeout: jobId={}", jobId);
log.error("Agent callback failed: jobId={}, error={}", jobId, ex.getMessage());
```

### 9.2 Health Check Endpoint

```java
@RestController
@RequestMapping("/api/v1")
public class HealthController {

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(Map.of(
            "status", "UP",
            "service", "qlgen-backend",
            "timestamp", Instant.now(),
            "version", buildVersion
        ));
    }
}
```

### 9.3 Spring Boot Actuator

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health, info, metrics
  endpoint:
    health:
      show-details: when_authorized
```

### 9.4 Key Metrics to Track

| Metric                        | Type      | Description                          |
|-------------------------------|-----------|--------------------------------------|
| `jobs.created.count`          | Counter   | Total jobs submitted                 |
| `jobs.completed.count`        | Counter   | Successfully completed jobs          |
| `jobs.failed.count`           | Counter   | Failed jobs                          |
| `agent.dispatch.duration`     | Timer     | Time to dispatch to agent            |
| `agent.callback.duration`     | Timer     | Time from dispatch to result         |
| `sse.active.connections`      | Gauge     | Currently active SSE connections     |

---

## 10. Production Readiness Checklist

| #  | Item                                             | Status |
|----|--------------------------------------------------|--------|
| 1  | All DTOs validated with Jakarta Bean Validation  | [ ]    |
| 2  | Global exception handler returns consistent JSON | [ ]    |
| 3  | Agent communication has retry with backoff       | [ ]    |
| 4  | Stalled job timeout scheduled task running        | [ ]    |
| 5  | SSE emitters properly cleaned up on disconnect    | [ ]    |
| 6  | CORS configured for frontend origins              | [ ]    |
| 7  | Internal endpoints not exposed publicly           | [ ]    |
| 8  | PostgreSQL connection validated for dev and prod   | [ ]    |
| 9  | Database migrations ready (Flyway/Liquibase)      | [ ]    |
| 10 | Health endpoint returns service status             | [ ]    |
| 11 | Structured JSON logging configured                 | [ ]    |
| 12 | Docker image builds and starts successfully        | [ ]    |
| 13 | Application starts within 30 seconds               | [ ]    |
| 14 | Thread pool configured for async job processing    | [ ]    |
| 15 | No secrets hardcoded — all externalized via env    | [ ]    |

---

## Appendix A: Maven Dependencies (pom.xml key entries)

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-webflux</artifactId>
        <!-- WebClient for agent communication -->
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-actuator</artifactId>
    </dependency>
    <dependency>
        <groupId>org.postgresql</groupId>
        <artifactId>postgresql</artifactId>
        <scope>runtime</scope>
    </dependency>
    <dependency>
        <groupId>org.projectlombok</groupId>
        <artifactId>lombok</artifactId>
        <optional>true</optional>
    </dependency>
    <dependency>
        <groupId>org.springdoc</groupId>
        <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
        <version>2.5.0</version>
    </dependency>
</dependencies>
```

## Appendix B: Quick Start

```bash
# Generate project
# Use https://start.spring.io with:
#   - Spring Boot 3.3.x, Java 21, Maven
#   - Dependencies: Web, JPA, Validation, PostgreSQL, Actuator, Lombok

# Build
cd backend
mvn clean package -DskipTests

# Run locally
mvn spring-boot:run -Dspring-boot.run.profiles=dev

# Docker
docker build -t qlgen-backend .
docker run -p 8080:8080 \
  -e AGENT_BASE_URL=http://agent:8000 \
  -e SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5432/qlgen \
  -e SPRING_DATASOURCE_USERNAME=qlgen \
  -e SPRING_DATASOURCE_PASSWORD=qlgen_dev \
  qlgen-backend
```

## Appendix C: application.yml

```yaml
server:
  port: 8080

spring:
  application:
    name: qlgen-backend
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:5432/qlgen
    username: ${DB_USER:qlgen}
    password: ${DB_PASSWORD:qlgen_dev}
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update    # Dev: auto-create/update tables
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect

agent:
  base-url: ${AGENT_BASE_URL:http://localhost:8000}
  timeout-seconds: 300

app:
  max-concurrent-jobs: 10
  job-timeout-minutes: 10
```
