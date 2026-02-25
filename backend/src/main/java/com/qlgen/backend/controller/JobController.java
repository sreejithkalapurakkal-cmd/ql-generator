package com.qlgen.backend.controller;

import com.qlgen.backend.dto.request.ICPProfileRequest;
import com.qlgen.backend.dto.response.JobResponse;
import com.qlgen.backend.dto.response.LeadResponse;
import com.qlgen.backend.service.JobService;
import com.qlgen.backend.service.SseService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/jobs")
@RequiredArgsConstructor
public class JobController {

    private final JobService jobService;
    private final SseService sseService;

    @PostMapping
    public ResponseEntity<JobResponse> createJob(@Valid @RequestBody ICPProfileRequest request) {
        JobResponse job = jobService.createAndDispatch(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(job);
    }

    @GetMapping
    public ResponseEntity<List<JobResponse>> getAllJobs() {
        return ResponseEntity.ok(jobService.getAllJobs());
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
