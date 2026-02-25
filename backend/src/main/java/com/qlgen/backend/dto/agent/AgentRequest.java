package com.qlgen.backend.dto.agent;

import lombok.Builder;
import lombok.Data;

import java.util.Map;

@Data
@Builder
public class AgentRequest {
    private String jobId;
    private Map<String, Object> icpProfile;
    private Map<String, Double> bantWeights;
    private int maxResults;
    private String callbackUrl;
}
