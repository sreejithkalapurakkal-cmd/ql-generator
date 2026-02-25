package com.qlgen.backend.exception;

public class AgentCommunicationException extends RuntimeException {
    public AgentCommunicationException(String message) {
        super(message);
    }

    public AgentCommunicationException(String message, Throwable cause) {
        super(message, cause);
    }
}
