package com.qlgen.backend.controller;

import com.qlgen.backend.dto.agent.AgentResult;
import com.qlgen.backend.dto.agent.ProgressUpdate;
import com.qlgen.backend.entity.enums.JobStatus;
import com.qlgen.backend.service.JobOrchestrator;
import com.qlgen.backend.service.JobService;
import com.qlgen.backend.service.SseService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/internal/jobs")
@RequiredArgsConstructor
public class InternalJobController {

    private final JobOrchestrator jobOrchestrator;
    private final SseService sseService;
    private final JobService jobService;

    @PostMapping("/{jobId}/callback")
    public ResponseEntity<Void> agentCallback(
            @PathVariable UUID jobId,
            @RequestBody AgentResult result) {
        log.info("Received agent callback for job {}", jobId);
        jobOrchestrator.handleAgentResult(jobId, result);
        return ResponseEntity.ok().build();
    }

    @PostMapping("/{jobId}/progress")
    public ResponseEntity<Void> agentProgress(
            @PathVariable UUID jobId,
            @RequestBody ProgressUpdate update) {
        log.debug("Progress update for job {}: {} ({}%)", jobId, update.getStage(), update.getProgress());

        try {
            JobStatus status = JobStatus.valueOf(update.getStage());
            jobService.updateStatus(jobId, status);
        } catch (IllegalArgumentException e) {
            log.debug("Non-status stage received: {}", update.getStage());
        }

        sseService.publishProgress(jobId, update);
        return ResponseEntity.ok().build();
    }
}
