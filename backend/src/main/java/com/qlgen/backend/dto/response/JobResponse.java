package com.qlgen.backend.dto.response;

import com.qlgen.backend.entity.enums.JobStatus;
import lombok.Builder;
import lombok.Data;

import java.time.Instant;
import java.util.UUID;

@Data
@Builder
public class JobResponse {
    private UUID id;
    private int jobNumber;
    private JobStatus status;
    private int maxResults;
    private String errorMessage;
    private int leadCount;
    private Instant createdAt;
    private Instant updatedAt;
}
