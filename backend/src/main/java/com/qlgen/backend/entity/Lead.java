package com.qlgen.backend.entity;

import jakarta.persistence.*;
import lombok.*;

import java.util.UUID;

@Entity
@Table(name = "leads")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Lead {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "job_id", nullable = false)
    private Job job;

    @Column(nullable = false)
    private String companyName;

    private String domain;

    private String industry;

    private Integer employeeCount;

    private Long estimatedRevenue;

    private String location;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(columnDefinition = "TEXT")
    private String techStackJson;

    private String fundingStage;

    private String linkedinUrl;

    private Double budgetScore;
    private Double authorityScore;
    private Double needScore;
    private Double timelineScore;
    private Double totalScore;

    @Column(columnDefinition = "TEXT")
    private String bantReasoning;

    private Integer rank;
}
