package com.qlgen.backend.dto.agent;

import lombok.Data;

@Data
public class ProgressUpdate {
    private String jobId;
    private String stage;
    private String message;
    private int progress;
}
