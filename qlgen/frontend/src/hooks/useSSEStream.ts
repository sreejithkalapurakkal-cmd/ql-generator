/**
 * Generic SSE stream hook for all async agent operations.
 *
 * Manages: connection lifecycle, event parsing, progress tracking,
 * activity log accumulation, auto-cleanup on unmount, and terminal
 * event detection.
 *
 * Usage:
 *   const stream = useSSEStream({
 *     terminalEvents: ['brief_ready', 'brief_failed'],
 *     onEvent: (type, data) => { ... },
 *   });
 *
 *   // Start streaming
 *   stream.connect(url);
 *
 *   // Read state
 *   stream.isRunning, stream.progress, stream.activityLog
 */
import { useState, useRef, useCallback, useEffect } from 'react';

export interface SSEActivityEntry {
  id: number;
  type: string;
  text: string;
  ts: number;
}

export interface UseSSEStreamOptions {
  /** Event types that signal the stream is complete (close connection) */
  terminalEvents: string[];
  /** Called for every SSE event received */
  onEvent?: (eventType: string, data: Record<string, unknown>, rawEvent: MessageEvent) => void;
  /** Called when a terminal event is received */
  onComplete?: (eventType: string, data: Record<string, unknown>) => void;
  /** Called on connection error after retry timeout */
  onError?: (error: Event) => void;
  /** Timeout (ms) to consider connection dead after native error (default 5000) */
  errorTimeout?: number;
}

export interface UseSSEStreamReturn {
  /** Whether the SSE stream is currently active */
  isRunning: boolean;
  /** Current progress percentage (0-100) */
  progress: number;
  /** Current status label */
  statusLabel: string;
  /** Accumulated activity log entries */
  activityLog: SSEActivityEntry[];
  /** Connect to an SSE stream URL */
  connect: (url: string) => void;
  /** Disconnect and reset state */
  disconnect: () => void;
  /** Add a manual log entry */
  addLog: (type: string, text: string) => void;
  /** Set progress externally */
  setProgress: (pct: number) => void;
  /** Set status label externally */
  setStatusLabel: (label: string) => void;
}

export function useSSEStream(options: UseSSEStreamOptions): UseSSEStreamReturn {
  const {
    terminalEvents,
    onEvent,
    onComplete,
    onError,
    errorTimeout = 5000,
  } = options;

  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusLabel, setStatusLabel] = useState('');
  const [activityLog, setActivityLog] = useState<SSEActivityEntry[]>([]);

  const esRef = useRef<EventSource | null>(null);
  const logIdRef = useRef(0);
  const terminalSetRef = useRef(new Set(terminalEvents));

  // Keep terminal events set in sync
  useEffect(() => {
    terminalSetRef.current = new Set(terminalEvents);
  }, [terminalEvents]);

  // Store latest callbacks in refs to avoid stale closures
  const onEventRef = useRef(onEvent);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);
  useEffect(() => { onEventRef.current = onEvent; }, [onEvent]);
  useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  const addLog = useCallback((type: string, text: string) => {
    const entry: SSEActivityEntry = {
      id: ++logIdRef.current,
      type,
      text,
      ts: Date.now(),
    };
    setActivityLog(prev => [...prev, entry]);
  }, []);

  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const disconnect = useCallback(() => {
    if (errorTimerRef.current) {
      clearTimeout(errorTimerRef.current);
      errorTimerRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setIsRunning(false);
  }, []);

  const connect = useCallback((url: string) => {
    // Close any existing connection
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    // Reset state
    setIsRunning(true);
    setProgress(0);
    setStatusLabel('Starting...');
    setActivityLog([]);
    logIdRef.current = 0;

    const es = new EventSource(url);
    esRef.current = es;

    // Generic message handler for all SSE events
    es.onmessage = (event: MessageEvent) => {
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(event.data);
      } catch {
        data = { raw: event.data };
      }

      const eventType = (data.type as string) || 'message';

      // Auto-extract common fields
      if (typeof data.percent === 'number') {
        setProgress(data.percent as number);
      }
      if (typeof data.label === 'string') {
        setStatusLabel(data.label as string);
      }

      // Delegate to caller
      onEventRef.current?.(eventType, data, event);

      // Check terminal
      if (terminalSetRef.current.has(eventType)) {
        onCompleteRef.current?.(eventType, data);
        es.close();
        esRef.current = null;
        setIsRunning(false);
      }
    };

    // Named event handler — SSE events sent with "event: <type>" use addEventListener
    // Listen for all events via the generic handler above AND named events
    const namedHandler = (e: Event) => {
      const me = e as MessageEvent;
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(me.data);
      } catch {
        data = { raw: me.data };
      }

      const eventType = e.type;

      if (typeof data.percent === 'number') {
        setProgress(data.percent as number);
      }
      if (typeof data.label === 'string') {
        setStatusLabel(data.label as string);
      }

      onEventRef.current?.(eventType, data, me);

      if (terminalSetRef.current.has(eventType)) {
        onCompleteRef.current?.(eventType, data);
        es.close();
        esRef.current = null;
        setIsRunning(false);
      }
    };

    // Register named event listeners for all terminal events + common event types
    const allEventTypes = new Set([
      ...terminalEvents,
      'progress', 'stage_started', 'stage_complete',
      'agent_thought', 'tool_start', 'tool_result',
      'section_started', 'section_complete',
      'error', 'timeout',
    ]);
    for (const evtType of allEventTypes) {
      es.addEventListener(evtType, namedHandler);
    }

    // Native connection error handler
    es.onerror = (err: Event) => {
      // If connection was intentionally closed, ignore
      if (es.readyState === EventSource.CLOSED && esRef.current !== es) return;

      // Wait before declaring dead — track timer so disconnect() can cancel it
      errorTimerRef.current = setTimeout(() => {
        errorTimerRef.current = null;
        if (es.readyState === EventSource.CLOSED && esRef.current === es) {
          esRef.current = null;
          setIsRunning(false);
          onErrorRef.current?.(err);
        }
      }, errorTimeout);
    };
  }, [terminalEvents, errorTimeout, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (errorTimerRef.current) {
        clearTimeout(errorTimerRef.current);
        errorTimerRef.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, []);

  return {
    isRunning,
    progress,
    statusLabel,
    activityLog,
    connect,
    disconnect,
    addLog,
    setProgress,
    setStatusLabel,
  };
}
