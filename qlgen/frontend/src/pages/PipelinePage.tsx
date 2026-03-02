import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Card, Steps, Spin, Result, Button, Typography, Tag, Timeline, Badge } from 'antd';
import {
  SearchOutlined,
  TeamOutlined,
  DatabaseOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  ToolOutlined,
  BulbOutlined,
  RocketOutlined,
  ApiOutlined,
  GlobalOutlined,
  MailOutlined,
  PhoneOutlined,
  FileSearchOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { getPipelineStatus } from '../api/pipelineApi';
import { PipelineRun } from '../types';
import { API_BASE } from '../api/client';

const { Text, Paragraph } = Typography;

const stageOrder = ['company_discovery', 'contact_discovery', 'enrichment', 'scoring', 'completed'];

// Map tool names to icons for the activity log
const toolIcons: Record<string, React.ReactNode> = {
  apollo_company_search: <SearchOutlined />,
  apollo_people_search: <TeamOutlined />,
  exa_search: <GlobalOutlined />,
  tavily_search: <FileSearchOutlined />,
  duckduckgo_search: <GlobalOutlined />,
  hunter_domain_search: <MailOutlined />,
  hunter_email_finder: <MailOutlined />,
  lusha_person_search: <PhoneOutlined />,
  scrape_webpage: <ApiOutlined />,
};

// Map tool names to tag colors
const toolColors: Record<string, string> = {
  apollo_company_search: 'blue',
  apollo_people_search: 'blue',
  exa_search: 'purple',
  tavily_search: 'orange',
  duckduckgo_search: 'green',
  hunter_domain_search: 'cyan',
  hunter_email_finder: 'cyan',
  lusha_person_search: 'magenta',
  scrape_webpage: 'volcano',
};

const stageColors: Record<string, string> = {
  company_discovery: '#1890ff',
  contact_discovery: '#52c41a',
  enrichment: '#722ed1',
  scoring: '#fa8c16',
  completed: '#52c41a',
};

interface ActivityEntry {
  id: number;
  type: 'tool_start' | 'agent_reasoning' | 'stage_update';
  timestamp: Date;
  // tool_start fields
  toolName?: string;
  displayName?: string;
  context?: string;
  toolCallNumber?: number;
  // agent_reasoning fields
  text?: string;
  // stage_update fields
  stage?: string;
  progress?: number;
  message?: string;
}

const PipelinePage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [sseMessage, setSseMessage] = useState('Starting pipeline...');
  const [sseStage, setSseStage] = useState('pending');
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [toolCallCount, setToolCallCount] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const logContainerRef = useRef<HTMLDivElement | null>(null);
  const entryIdRef = useRef(0);
  const startTimeRef = useRef<Date>(new Date());

  const addEntry = useCallback((entry: Omit<ActivityEntry, 'id' | 'timestamp'>) => {
    const newEntry: ActivityEntry = {
      ...entry,
      id: ++entryIdRef.current,
      timestamp: new Date(),
    };
    setActivityLog((prev) => [...prev, newEntry]);
  }, []);

  // Auto-scroll log to bottom
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [activityLog]);

  useEffect(() => {
    if (!runId) return;
    startTimeRef.current = new Date();

    getPipelineStatus(runId).then((res) => setRun(res.data));

    const es = new EventSource(`${API_BASE}/pipeline/${runId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('stage_update', (event) => {
      const data = JSON.parse(event.data);
      setSseStage(data.stage);
      setSseMessage(data.message || 'Agent is working...');
      addEntry({
        type: 'stage_update',
        stage: data.stage,
        progress: data.progress,
        message: data.message,
      });
    });

    es.addEventListener('tool_start', (event) => {
      const data = JSON.parse(event.data);
      setToolCallCount(data.tool_call_number || 0);
      addEntry({
        type: 'tool_start',
        toolName: data.tool_name,
        displayName: data.display_name,
        context: data.context,
        toolCallNumber: data.tool_call_number,
        stage: data.stage,
      });
    });

    es.addEventListener('agent_reasoning', (event) => {
      const data = JSON.parse(event.data);
      addEntry({
        type: 'agent_reasoning',
        text: data.text,
        stage: data.stage,
      });
    });

    es.addEventListener('completed', (event) => {
      const data = JSON.parse(event.data);
      setSseStage('completed');
      setSseMessage(`Completed: ${data.companies_found} companies, ${data.contacts_found} contacts`);
      addEntry({
        type: 'stage_update',
        stage: 'completed',
        progress: 100,
        message: `Pipeline complete — found ${data.companies_found} companies and ${data.contacts_found} contacts`,
      });
      getPipelineStatus(runId).then((res) => setRun(res.data));
      es.close();
    });

    es.addEventListener('error', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        setSseMessage(`Error: ${data.message}`);
        addEntry({
          type: 'stage_update',
          stage: 'error',
          message: `Error: ${data.message}`,
        });
      } catch {
        // SSE connection error
      }
      es.close();
    });

    es.onerror = () => {
      es.close();
      const interval = setInterval(() => {
        getPipelineStatus(runId).then((res) => {
          setRun(res.data);
          if (res.data.status === 'completed' || res.data.status === 'failed') {
            clearInterval(interval);
          }
        });
      }, 5000);
    };

    return () => {
      es.close();
    };
  }, [runId, addEntry]);

  const stages = [
    { key: 'company_discovery', title: 'Company Discovery', icon: <SearchOutlined /> },
    { key: 'contact_discovery', title: 'Contact Discovery', icon: <TeamOutlined /> },
    { key: 'enrichment', title: 'Enrichment', icon: <DatabaseOutlined /> },
    { key: 'scoring', title: 'BANT Scoring', icon: <BarChartOutlined /> },
  ];

  const currentIndex = stageOrder.indexOf(sseStage);
  const isCompleted = run?.status === 'completed' || sseStage === 'completed';
  const isFailed = run?.status === 'failed';

  const getStepStatus = (index: number) => {
    if (isCompleted) return 'finish';
    if (isFailed) return index <= currentIndex ? 'error' : 'wait';
    if (index < currentIndex) return 'finish';
    if (index === currentIndex) return 'process';
    return 'wait';
  };

  const getElapsedTime = (entryTime: Date) => {
    const diffMs = entryTime.getTime() - startTimeRef.current.getTime();
    const secs = Math.floor(diffMs / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    const remainSecs = secs % 60;
    return `${mins}m ${remainSecs}s`;
  };

  const renderActivityEntry = (entry: ActivityEntry) => {
    switch (entry.type) {
      case 'tool_start':
        return (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <Tag
                color={toolColors[entry.toolName || ''] || 'default'}
                icon={toolIcons[entry.toolName || ''] || <ToolOutlined />}
              >
                {entry.displayName || entry.toolName}
              </Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
              </Text>
            </div>
            {entry.context && (
              <Paragraph
                type="secondary"
                style={{ margin: '4px 0 0 0', fontSize: 13 }}
                ellipsis={{ rows: 2 }}
              >
                {entry.context}
              </Paragraph>
            )}
          </div>
        );

      case 'agent_reasoning':
        return (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <BulbOutlined style={{ color: '#faad14' }} />
              <Text strong style={{ fontSize: 13 }}>Agent Reasoning</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
              </Text>
            </div>
            <Paragraph
              style={{
                margin: 0,
                fontSize: 13,
                background: '#fafafa',
                padding: '8px 12px',
                borderRadius: 6,
                borderLeft: '3px solid #faad14',
              }}
              ellipsis={{ rows: 4, expandable: true, symbol: 'more' }}
            >
              {entry.text}
            </Paragraph>
          </div>
        );

      case 'stage_update':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <RocketOutlined style={{ color: stageColors[entry.stage || ''] || '#1890ff' }} />
            <Text strong style={{ color: stageColors[entry.stage || ''] || '#1890ff' }}>
              {entry.message}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
            </Text>
          </div>
        );

      default:
        return null;
    }
  };

  const getTimelineDotColor = (entry: ActivityEntry) => {
    if (entry.type === 'stage_update') return stageColors[entry.stage || ''] || '#1890ff';
    if (entry.type === 'tool_start') return toolColors[entry.toolName || ''] || '#1890ff';
    return '#faad14';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Stage Progress Stepper */}
      <Card title="Pipeline Progress" bordered={false}>
        <Steps
          current={isCompleted ? 4 : currentIndex}
          items={stages.map((s, i) => ({
            title: s.title,
            icon: getStepStatus(i) === 'process' ? <LoadingOutlined /> : s.icon,
            status: getStepStatus(i) as any,
          }))}
        />

        {isCompleted && (
          <Result
            status="success"
            title="Pipeline Complete"
            subTitle={`Found ${run?.companies_found || 0} companies and ${run?.contacts_found || 0} contacts`}
            style={{ padding: '24px 0 0 0' }}
            extra={[
              <Button type="primary" key="leads" onClick={() => navigate(`/leads/${runId}`)}>
                View Leads
              </Button>,
              <Button key="dashboard" onClick={() => navigate('/dashboard')}>
                Dashboard
              </Button>,
            ]}
          />
        )}

        {isFailed && (
          <Result
            status="error"
            title="Pipeline Failed"
            subTitle={run?.error_log?.substring(0, 200) || 'An error occurred during pipeline execution'}
            style={{ padding: '24px 0 0 0' }}
            extra={<Button onClick={() => navigate('/dashboard')}>Dashboard</Button>}
          />
        )}

        {!isCompleted && !isFailed && (
          <div style={{ textAlign: 'center', marginTop: 24 }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
            <div style={{ marginTop: 8 }}>
              <Text type="secondary">{sseMessage}</Text>
            </div>
          </div>
        )}
      </Card>

      {/* Activity Log */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span>Agent Activity Log</span>
            {!isCompleted && !isFailed && (
              <Badge
                count={`${toolCallCount} tool calls`}
                style={{ backgroundColor: '#1890ff' }}
                showZero
              />
            )}
          </div>
        }
        bordered={false}
      >
        <div
          ref={logContainerRef}
          style={{
            maxHeight: 500,
            overflowY: 'auto',
            paddingRight: 8,
          }}
        >
          {activityLog.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
              <LoadingOutlined style={{ fontSize: 24, marginBottom: 12 }} />
              <div>Waiting for agent activity...</div>
            </div>
          ) : (
            <Timeline
              items={activityLog.map((entry) => ({
                key: entry.id,
                color: getTimelineDotColor(entry),
                children: renderActivityEntry(entry),
              }))}
            />
          )}
        </div>
      </Card>
    </div>
  );
};

export default PipelinePage;
