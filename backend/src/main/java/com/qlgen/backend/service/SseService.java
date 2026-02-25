package com.qlgen.backend.service;

import com.qlgen.backend.dto.agent.ProgressUpdate;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

@Slf4j
@Service
public class SseService {

    private final ConcurrentHashMap<UUID, List<SseEmitter>> emitters = new ConcurrentHashMap<>();

    public SseEmitter createEmitter(UUID jobId) {
        SseEmitter emitter = new SseEmitter(600_000L); // 10 min timeout
        emitters.computeIfAbsent(jobId, k -> new CopyOnWriteArrayList<>()).add(emitter);

        emitter.onCompletion(() -> removeEmitter(jobId, emitter));
        emitter.onTimeout(() -> removeEmitter(jobId, emitter));
        emitter.onError(e -> removeEmitter(jobId, emitter));

        return emitter;
    }

    public void publishProgress(UUID jobId, ProgressUpdate update) {
        List<SseEmitter> jobEmitters = emitters.getOrDefault(jobId, List.of());
        for (SseEmitter emitter : jobEmitters) {
            try {
                emitter.send(SseEmitter.event()
                        .name("status")
                        .data(Map.of(
                                "stage", update.getStage(),
                                "message", update.getMessage(),
                                "progress", update.getProgress()
                        )));
            } catch (IOException e) {
                log.debug("Failed to send SSE event for job {}", jobId);
                removeEmitter(jobId, emitter);
            }
        }
    }

    public void publishComplete(UUID jobId, int totalLeads) {
        List<SseEmitter> jobEmitters = emitters.getOrDefault(jobId, List.of());
        for (SseEmitter emitter : jobEmitters) {
            try {
                emitter.send(SseEmitter.event()
                        .name("complete")
                        .data(Map.of(
                                "stage", "COMPLETED",
                                "totalLeads", totalLeads,
                                "progress", 100
                        )));
                emitter.complete();
            } catch (IOException e) {
                log.debug("Failed to send SSE complete for job {}", jobId);
            }
        }
        emitters.remove(jobId);
    }

    public void publishError(UUID jobId, String message) {
        List<SseEmitter> jobEmitters = emitters.getOrDefault(jobId, List.of());
        for (SseEmitter emitter : jobEmitters) {
            try {
                emitter.send(SseEmitter.event()
                        .name("error")
                        .data(Map.of(
                                "stage", "FAILED",
                                "message", message
                        )));
                emitter.complete();
            } catch (IOException e) {
                log.debug("Failed to send SSE error for job {}", jobId);
            }
        }
        emitters.remove(jobId);
    }

    private void removeEmitter(UUID jobId, SseEmitter emitter) {
        List<SseEmitter> list = emitters.get(jobId);
        if (list != null) {
            list.remove(emitter);
        }
    }
}
