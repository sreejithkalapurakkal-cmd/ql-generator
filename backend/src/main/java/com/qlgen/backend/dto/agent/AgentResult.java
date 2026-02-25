package com.qlgen.backend.dto.agent;

import lombok.Data;

import java.util.List;

@Data
public class AgentResult {
    private String jobId;
    private String status;
    private List<AgentLead> leads;
    private String error;

    @Data
    public static class AgentLead {
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
        private BANTScore bantScore;
    }

    @Data
    public static class BANTScore {
        private Double budget;
        private Double authority;
        private Double need;
        private Double timeline;
        private Double total;
        private String reasoning;
    }
}
