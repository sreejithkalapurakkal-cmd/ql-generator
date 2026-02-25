import React, { useEffect, useState, useRef } from 'react';
import { Card, Steps, Spin, Result, Button, Alert, Typography } from 'antd';
import {
  SearchOutlined,
  TeamOutlined,
  DatabaseOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { getPipelineStatus } from '../api/pipelineApi';
import { PipelineRun } from '../types';

const { Text } = Typography;

const stageOrder = ['company_discovery', 'contact_discovery', 'enrichment', 'scoring', 'completed'];

const PipelinePage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [sseMessage, setSseMessage] = useState('Starting pipeline...');
  const [sseStage, setSseStage] = useState('pending');
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) return;

    // Fetch initial status
    getPipelineStatus(runId).then((res) => setRun(res.data));

    // Set up SSE
    const es = new EventSource(`/api/v1/pipeline/${runId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('stage_update', (event) => {
      const data = JSON.parse(event.data);
      setSseStage(data.stage);
      setSseMessage(data.message || 'Agent is working...');
    });

    es.addEventListener('completed', (event) => {
      const data = JSON.parse(event.data);
      setSseStage('completed');
      setSseMessage(`Completed: ${data.companies_found} companies, ${data.contacts_found} contacts`);
      // Refresh run data
      getPipelineStatus(runId).then((res) => setRun(res.data));
      es.close();
    });

    es.addEventListener('error', (event) => {
      // Try to parse error data
      try {
        const data = JSON.parse((event as MessageEvent).data);
        setSseMessage(`Error: ${data.message}`);
      } catch {
        // SSE connection error, poll instead
      }
      es.close();
    });

    es.onerror = () => {
      // Fallback to polling
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
  }, [runId]);

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

  return (
    <Card title="Pipeline Progress">
      <Steps
        current={isCompleted ? 4 : currentIndex}
        items={stages.map((s, i) => ({
          title: s.title,
          icon: getStepStatus(i) === 'process' ? <LoadingOutlined /> : s.icon,
          status: getStepStatus(i) as any,
        }))}
      />

      <div style={{ marginTop: 48, textAlign: 'center' }}>
        {isCompleted ? (
          <Result
            status="success"
            title="Pipeline Complete"
            subTitle={`Found ${run?.companies_found || 0} companies and ${run?.contacts_found || 0} contacts`}
            extra={[
              <Button type="primary" key="leads" onClick={() => navigate(`/leads/${runId}`)}>
                View Leads
              </Button>,
              <Button key="dashboard" onClick={() => navigate('/dashboard')}>
                Dashboard
              </Button>,
            ]}
          />
        ) : isFailed ? (
          <Result
            status="error"
            title="Pipeline Failed"
            subTitle={run?.error_log?.substring(0, 200) || 'An error occurred during pipeline execution'}
            extra={<Button onClick={() => navigate('/dashboard')}>Dashboard</Button>}
          />
        ) : (
          <div>
            <Spin size="large" tip={sseMessage}>
              <div style={{ padding: 50 }} />
            </Spin>
            <div style={{ marginTop: 16 }}>
              <Text type="secondary">{sseMessage}</Text>
            </div>
            <Alert
              message="The agent is processing your ICP through all 4 stages. This may take several minutes depending on the number of companies requested."
              type="info"
              showIcon
              style={{ marginTop: 24, maxWidth: 600, margin: '24px auto' }}
            />
          </div>
        )}
      </div>
    </Card>
  );
};

export default PipelinePage;
