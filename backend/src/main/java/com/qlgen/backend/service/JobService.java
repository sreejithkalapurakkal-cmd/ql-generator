package com.qlgen.backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.qlgen.backend.dto.request.ICPProfileRequest;
import com.qlgen.backend.dto.response.JobResponse;
import com.qlgen.backend.dto.response.LeadResponse;
import com.qlgen.backend.entity.Job;
import com.qlgen.backend.entity.enums.JobStatus;
import com.qlgen.backend.exception.JobNotFoundException;
import com.qlgen.backend.mapper.JobMapper;
import com.qlgen.backend.mapper.LeadMapper;
import com.qlgen.backend.repository.JobRepository;
import com.qlgen.backend.repository.LeadRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class JobService {

    private final JobRepository jobRepository;
    private final LeadRepository leadRepository;
    private final JobMapper jobMapper;
    private final LeadMapper leadMapper;
    private final JobOrchestrator jobOrchestrator;
    private final ObjectMapper objectMapper;

    @Transactional
    public JobResponse createAndDispatch(ICPProfileRequest request) {
        try {
            String icpJson = objectMapper.writeValueAsString(request.getIcpProfile());
            String bantJson = objectMapper.writeValueAsString(request.getBantWeights());

            Job job = Job.builder()
                    .status(JobStatus.PENDING)
                    .icpProfileJson(icpJson)
                    .bantWeightsJson(bantJson)
                    .maxResults(request.getMaxResults())
                    .build();

            job = jobRepository.save(job);
            log.info("Job created: jobId={}", job.getId());

            jobOrchestrator.executeJob(job.getId(), request);

            return jobMapper.toResponse(job);
        } catch (Exception e) {
            throw new RuntimeException("Failed to create job", e);
        }
    }

    @Transactional(readOnly = true)
    public JobResponse getJob(UUID jobId) {
        Job job = jobRepository.findById(jobId)
                .orElseThrow(() -> new JobNotFoundException(jobId));
        return jobMapper.toResponse(job);
    }

    @Transactional(readOnly = true)
    public List<JobResponse> getAllJobs() {
        return jobRepository.findAllByOrderByCreatedAtDesc().stream()
                .map(jobMapper::toResponse)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<LeadResponse> getLeads(UUID jobId) {
        if (!jobRepository.existsById(jobId)) {
            throw new JobNotFoundException(jobId);
        }
        return leadRepository.findByJobIdOrderByRankAsc(jobId).stream()
                .map(leadMapper::toResponse)
                .collect(Collectors.toList());
    }

    @Transactional
    public void updateStatus(UUID jobId, JobStatus status) {
        Job job = jobRepository.findById(jobId)
                .orElseThrow(() -> new JobNotFoundException(jobId));
        job.setStatus(status);
        jobRepository.save(job);
    }

    @Transactional
    public void markFailed(UUID jobId, String errorMessage) {
        Job job = jobRepository.findById(jobId)
                .orElseThrow(() -> new JobNotFoundException(jobId));
        job.setStatus(JobStatus.FAILED);
        job.setErrorMessage(errorMessage);
        jobRepository.save(job);
        log.error("Job marked as failed: jobId={}, reason={}", jobId, errorMessage);
    }
}
