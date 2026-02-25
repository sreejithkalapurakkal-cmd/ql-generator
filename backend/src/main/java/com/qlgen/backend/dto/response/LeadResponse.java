package com.qlgen.backend.dto.response;

import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.UUID;

@Data
@Builder
public class LeadResponse {
    private UUID id;
    private String companyName;
    private String domain;
    private String industry;
    private Integer employeeCount;
    private Long estimatedRevenue;
    private String location;
    private String description;
    private List<String> techStack;
    private String fundingStage;
    private String linkedinUrl;
    private BANTScoreResponse bantScore;
    private Integer rank;

    @Data
    @Builder
    public static class BANTScoreResponse {
        private Double budget;
        private Double authority;
        private Double need;
        private Double timeline;
        private Double total;
        private String reasoning;
    }
}
