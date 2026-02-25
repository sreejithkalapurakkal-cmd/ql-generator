package com.qlgen.backend.service;

import com.qlgen.backend.dto.agent.AgentRequest;
import com.qlgen.backend.exception.AgentCommunicationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.util.retry.Retry;

import java.net.ConnectException;
import java.time.Duration;

@Slf4j
@Service
public class AgentClient {

    private final WebClient webClient;

    public AgentClient(@Qualifier("agentWebClient") WebClient webClient) {
        this.webClient = webClient;
    }

    public void dispatchJob(AgentRequest request) {
        log.info("Dispatching job {} to agent", request.getJobId());

        webClient.post()
                .uri("/api/v1/process")
                .bodyValue(request)
                .retrieve()
                .toBodilessEntity()
                .retryWhen(Retry.backoff(3, Duration.ofSeconds(2))
                        .maxBackoff(Duration.ofSeconds(10))
                        .filter(ex -> ex instanceof WebClientResponseException.ServiceUnavailable
                                || ex instanceof ConnectException))
                .doOnSuccess(response -> log.info("Agent accepted job {}", request.getJobId()))
                .doOnError(ex -> log.error("Agent dispatch failed for job {}", request.getJobId(), ex))
                .subscribe(
                        response -> {},
                        ex -> {
                            throw new AgentCommunicationException(
                                    "Failed to dispatch job " + request.getJobId(), ex);
                        }
                );
    }
}
