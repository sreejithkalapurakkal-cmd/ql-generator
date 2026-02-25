package com.qlgen.backend.service;

import com.qlgen.backend.dto.agent.AgentRequest;
import com.qlgen.backend.dto.agent.AgentResult;
import com.qlgen.backend.dto.request.ICPProfileRequest;
import com.qlgen.backend.entity.Job;
import com.qlgen.backend.entity.Lead;
import com.qlgen.backend.entity.enums.JobStatus;
import com.qlgen.backend.exception.JobNotFoundException;
import com.qlgen.backend.mapper.LeadMapper;
import com.qlgen.backend.repository.JobRepository;
import com.qlgen.backend.repository.LeadRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class JobOrchestrator {

    private final JobRepository jobRepository;
    private final LeadRepository leadRepository;
    private final AgentClient agentClient;
    private final SseService sseService;
    private final LeadMapper leadMapper;

    @Value("${app.job-timeout-minutes:10}")
    private int jobTimeoutMinutes;

    @Async("jobTaskExecutor")
    public void executeJob(UUID jobId, ICPProfileRequest request) {
        try {
            Job job = jobRepository.findById(jobId)
                    .orElseThrow(() -> new JobNotFoundException(jobId));
            job.setStatus(JobStatus.SEARCHING);
            jobRepository.save(job);

            String callbackUrl = "http://backend:8080/api/v1/internal/jobs/" + jobId + "/callback";

            Map<String, Object> icpMap = new LinkedHashMap<>();
            icpMap.put("industries", request.getIcpProfile().getIndustries());
            icpMap.put("companySizeRange", Map.of(
                    "min", request.getIcpProfile().getCompanySizeRange().getMin(),
                    "max", request.getIcpProfile().getCompanySizeRange().getMax()));
            icpMap.put("revenueRange", Map.of(
                    "min", request.getIcpProfile().getRevenueRange().getMin(),
                    "max", request.getIcpProfile().getRevenueRange().getMax()));
            icpMap.put("geographies", request.getIcpProfile().getGeographies());
            icpMap.put("techStack", request.getIcpProfile().getTechStack() != null
                    ? request.getIcpProfile().getTechStack() : List.of());
            icpMap.put("keywords", request.getIcpProfile().getKeywords() != null
                    ? request.getIcpProfile().getKeywords() : List.of());
            icpMap.put("additionalNotes", request.getIcpProfile().getAdditionalNotes() != null
                    ? request.getIcpProfile().getAdditionalNotes() : "");

            Map<String, Double> bantMap = Map.of(
                    "budget", request.getBantWeights().getBudget(),
                    "authority", request.getBantWeights().getAuthority(),
                    "need", request.getBantWeights().getNeed(),
                    "timeline", request.getBantWeights().getTimeline());

            AgentRequest agentRequest = AgentRequest.builder()
                    .jobId(jobId.toString())
                    .icpProfile(icpMap)
                    .bantWeights(bantMap)
                    .maxResults(request.getMaxResults())
                    .callbackUrl(callbackUrl)
                    .build();

            agentClient.dispatchJob(agentRequest);
            log.info("Agent dispatched for job {}", jobId);

        } catch (Exception e) {
            log.error("Failed to execute job {}", jobId, e);
            markJobFailed(jobId, "Failed to dispatch to agent: " + e.getMessage());
        }
    }

    @Transactional
    public void handleAgentResult(UUID jobId, AgentResult result) {
        log.info("Received agent result for job {}: status={}", jobId, result.getStatus());

        Job job = jobRepository.findById(jobId)
                .orElseThrow(() -> new JobNotFoundException(jobId));

        if ("COMPLETED".equals(result.getStatus()) && result.getLeads() != null) {
            List<Lead> leads = new ArrayList<>();
            for (int i = 0; i < result.getLeads().size(); i++) {
                leads.add(leadMapper.fromAgentLead(result.getLeads().get(i), job, i + 1));
            }
            leadRepository.saveAll(leads);

            job.setStatus(JobStatus.COMPLETED);
            jobRepository.save(job);

            sseService.publishComplete(jobId, leads.size());
            log.info("Job {} completed with {} leads", jobId, leads.size());

        } else if ("FAILED".equals(result.getStatus())) {
            job.setStatus(JobStatus.FAILED);
            job.setErrorMessage(result.getError());
            jobRepository.save(job);
            sseService.publishError(jobId, result.getError());

        } else {
            job.setStatus(JobStatus.COMPLETED);
            jobRepository.save(job);
            sseService.publishComplete(jobId, 0);
        }
    }

    @Scheduled(fixedRate = 60000)
    @Transactional
    public void checkStalledJobs() {
        List<Job> stalled = jobRepository.findByStatusInAndUpdatedAtBefore(
                List.of(JobStatus.SEARCHING, JobStatus.ENRICHING, JobStatus.SCORING),
                Instant.now().minus(jobTimeoutMinutes, ChronoUnit.MINUTES)
        );

        for (Job job : stalled) {
            log.warn("Job {} timed out after {} minutes", job.getId(), jobTimeoutMinutes);
            job.setStatus(JobStatus.FAILED);
            job.setErrorMessage("Job timed out after " + jobTimeoutMinutes + " minutes");
            jobRepository.save(job);
            sseService.publishError(job.getId(), "Job timed out");
        }
    }

    private void markJobFailed(UUID jobId, String reason) {
        try {
            Job job = jobRepository.findById(jobId).orElse(null);
            if (job != null) {
                job.setStatus(JobStatus.FAILED);
                job.setErrorMessage(reason);
                jobRepository.save(job);
                sseService.publishError(jobId, reason);
            }
        } catch (Exception e) {
            log.error("Failed to mark job {} as failed", jobId, e);
        }
    }
}
