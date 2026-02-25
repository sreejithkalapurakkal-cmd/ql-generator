package com.qlgen.backend.mapper;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.qlgen.backend.dto.agent.AgentResult;
import com.qlgen.backend.dto.response.LeadResponse;
import com.qlgen.backend.entity.Job;
import com.qlgen.backend.entity.Lead;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class LeadMapper {

    private final ObjectMapper objectMapper;

    public LeadResponse toResponse(Lead lead) {
        List<String> techStack = parseTechStack(lead.getTechStackJson());

        return LeadResponse.builder()
                .id(lead.getId())
                .companyName(lead.getCompanyName())
                .domain(lead.getDomain())
                .industry(lead.getIndustry())
                .employeeCount(lead.getEmployeeCount())
                .estimatedRevenue(lead.getEstimatedRevenue())
                .location(lead.getLocation())
                .description(lead.getDescription())
                .techStack(techStack)
                .fundingStage(lead.getFundingStage())
                .linkedinUrl(lead.getLinkedinUrl())
                .bantScore(LeadResponse.BANTScoreResponse.builder()
                        .budget(lead.getBudgetScore())
                        .authority(lead.getAuthorityScore())
                        .need(lead.getNeedScore())
                        .timeline(lead.getTimelineScore())
                        .total(lead.getTotalScore())
                        .reasoning(lead.getBantReasoning())
                        .build())
                .rank(lead.getRank())
                .build();
    }

    public Lead fromAgentLead(AgentResult.AgentLead agentLead, Job job, int rank) {
        String techStackJson = null;
        if (agentLead.getTechStack() != null) {
            try {
                techStackJson = objectMapper.writeValueAsString(agentLead.getTechStack());
            } catch (Exception e) {
                log.warn("Failed to serialize tech stack", e);
            }
        }

        return Lead.builder()
                .job(job)
                .companyName(agentLead.getCompanyName())
                .domain(agentLead.getDomain())
                .industry(agentLead.getIndustry())
                .employeeCount(agentLead.getEmployeeCount())
                .estimatedRevenue(agentLead.getEstimatedRevenue())
                .location(agentLead.getLocation())
                .description(agentLead.getDescription())
                .techStackJson(techStackJson)
                .fundingStage(agentLead.getFundingStage())
                .linkedinUrl(agentLead.getLinkedinUrl())
                .budgetScore(agentLead.getBantScore() != null ? agentLead.getBantScore().getBudget() : null)
                .authorityScore(agentLead.getBantScore() != null ? agentLead.getBantScore().getAuthority() : null)
                .needScore(agentLead.getBantScore() != null ? agentLead.getBantScore().getNeed() : null)
                .timelineScore(agentLead.getBantScore() != null ? agentLead.getBantScore().getTimeline() : null)
                .totalScore(agentLead.getBantScore() != null ? agentLead.getBantScore().getTotal() : null)
                .bantReasoning(agentLead.getBantScore() != null ? agentLead.getBantScore().getReasoning() : null)
                .rank(rank)
                .build();
    }

    private List<String> parseTechStack(String json) {
        if (json == null || json.isBlank()) return Collections.emptyList();
        try {
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception e) {
            log.warn("Failed to parse tech stack JSON", e);
            return Collections.emptyList();
        }
    }
}
