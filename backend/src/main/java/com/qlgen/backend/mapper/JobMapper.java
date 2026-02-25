package com.qlgen.backend.mapper;

import com.qlgen.backend.dto.response.JobResponse;
import com.qlgen.backend.entity.Job;
import org.springframework.stereotype.Component;

@Component
public class JobMapper {

    public JobResponse toResponse(Job job) {
        return toResponse(job, 0);
    }

    public JobResponse toResponse(Job job, int jobNumber) {
        return JobResponse.builder()
                .id(job.getId())
                .jobNumber(jobNumber)
                .status(job.getStatus())
                .maxResults(job.getMaxResults())
                .errorMessage(job.getErrorMessage())
                .leadCount(job.getLeads() != null ? job.getLeads().size() : 0)
                .createdAt(job.getCreatedAt())
                .updatedAt(job.getUpdatedAt())
                .build();
    }
}
