package com.qlgen.backend.repository;

import com.qlgen.backend.entity.Job;
import com.qlgen.backend.entity.enums.JobStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface JobRepository extends JpaRepository<Job, UUID> {

    List<Job> findAllByOrderByCreatedAtDesc();

    List<Job> findByStatusInAndUpdatedAtBefore(List<JobStatus> statuses, Instant cutoff);
}
