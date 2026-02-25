import React, { useEffect, useState, useRef } from 'react';
import { Box, Typography, Button, LinearProgress, CircularProgress } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useParams, useNavigate } from 'react-router-dom';
import { getPipelineStatus } from '../api/pipelineApi';
import { PipelineRun } from '../types';

const stageOrder = ['company_discovery', 'contact_discovery', 'enrichment', 'scoring', 'completed'];

const stages = [
  { key: 'company_discovery',  title: 'Company Discovery',  emoji: '🔍' },
  { key: 'contact_discovery',  title: 'Contact Discovery',  emoji: '👥' },
  { key: 'enrichment',         title: 'Enrichment',         emoji: '🗄️' },
  { key: 'scoring',            title: 'BANT Scoring',       emoji: '📊' },
];

type StepState = 'pending' | 'active' | 'done';

interface TimelineStepProps {
  index: number;
  title: string;
  emoji: string;
  state: StepState;
  message: string;
}

const TimelineStep: React.FC<TimelineStepProps> = ({ index, title, emoji, state, message }) => (
  <Box
    sx={{
      display: 'flex', alignItems: 'center', gap: 1.75,
      position: 'relative', zIndex: 1, py: '5px',
      opacity: state === 'pending' ? 0.45 : 1,
      transition: 'opacity .25s',
    }}
  >
    {/* Node */}
    <Box
      sx={{
        width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700, position: 'relative', zIndex: 2,
        transition: 'all .3s cubic-bezier(.34,1.4,.64,1)',
        ...(state === 'pending' && {
          bgcolor: '#FAFAFA', border: '2px solid #EBEBEB', color: '#ADADAD',
        }),
        ...(state === 'active' && {
          bgcolor: '#5C2D8F', border: '2px solid #5C2D8F', color: '#fff',
          boxShadow: '0 0 0 5px rgba(92,45,143,.1),0 2px 8px rgba(92,45,143,.25)',
        }),
        ...(state === 'done' && {
          bgcolor: '#1E9B6B', border: '2px solid #1E9B6B', color: '#fff',
          boxShadow: '0 1px 6px rgba(30,155,107,.25)',
        }),
      }}
    >
      {state === 'done' ? <CheckIcon sx={{ fontSize: 14 }} /> : index + 1}
    </Box>

    {/* Content */}
    <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
      <Typography
        sx={{
          fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', width: 148, flexShrink: 0,
          color: state === 'active' ? '#5C2D8F' : state === 'done' ? '#3D3D3D' : '#ADADAD',
          transition: 'color .2s',
        }}
      >
        {title}
      </Typography>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          sx={{
            fontSize: 11.5, color: state === 'active' ? '#5C5C5C' : '#ADADAD',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            transition: 'color .2s',
          }}
        >
          {message}
        </Typography>
        {state === 'active' && (
          <LinearProgress
            sx={{
              mt: '3px', height: 3, borderRadius: 999,
              bgcolor: '#F5F5F5',
              '& .MuiLinearProgress-bar': { background: 'linear-gradient(90deg, #5C2D8F, #7B4DB5)', borderRadius: 999 },
            }}
          />
        )}
      </Box>

      {/* Right: spinner for active, done indicator for completed */}
      <Box sx={{ flexShrink: 0, width: 24, display: 'flex', justifyContent: 'center' }}>
        {state === 'active' && <CircularProgress size={12} sx={{ color: '#5C2D8F' }} />}
        {state === 'done' && <Typography sx={{ fontSize: 11, color: '#1E9B6B', fontWeight: 600 }}>✓</Typography>}
      </Box>
    </Box>
  </Box>
);

const PipelinePage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [sseMessage, setSseMessage] = useState('Setting up your pipeline');
  const [sseStage, setSseStage] = useState('pending');
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) return;

    getPipelineStatus(runId).then((res) => setRun(res.data));

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
      setSseMessage(`Found ${data.companies_found} companies, ${data.contacts_found} contacts`);
      getPipelineStatus(runId).then((res) => setRun(res.data));
      es.close();
    });

    es.addEventListener('error', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        setSseMessage(`Error: ${data.message}`);
      } catch { /* ignore */ }
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

    return () => { es.close(); };
  }, [runId]);

  const currentIndex = stageOrder.indexOf(sseStage);
  const isCompleted = run?.status === 'completed' || sseStage === 'completed';
  const isFailed = run?.status === 'failed';

  const getStepState = (index: number): StepState => {
    if (isCompleted) return 'done';
    if (index < currentIndex) return 'done';
    if (index === currentIndex) return 'active';
    return 'pending';
  };

  const globalProgress = isCompleted
    ? 100
    : currentIndex < 0 ? 0 : Math.round(((currentIndex) / stages.length) * 100);

  // ── Completed or Failed ────────────────────────────────────────────────────
  if (isCompleted || isFailed) {
    return (
      <Box
        sx={{
          minHeight: 'calc(100vh - 56px)',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          py: 8,
        }}
      >
        <Box
          sx={{
            width: 64, height: 64, borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            mb: 3,
            bgcolor: isCompleted ? '#E6F7F1' : '#FDECEA',
          }}
        >
          {isCompleted
            ? <CheckIcon sx={{ fontSize: 32, color: '#1E9B6B' }} />
            : <ErrorOutlineIcon sx={{ fontSize: 32, color: '#D93025' }} />
          }
        </Box>
        <Typography sx={{ fontSize: 20, fontWeight: 700, color: '#141414', letterSpacing: '-0.4px', mb: 1 }}>
          {isCompleted ? 'Pipeline Complete' : 'Pipeline Failed'}
        </Typography>
        <Typography sx={{ fontSize: 14, color: '#858585', mb: 3, textAlign: 'center', maxWidth: 420 }}>
          {isCompleted
            ? `Found ${run?.companies_found || 0} companies and ${run?.contacts_found || 0} contacts`
            : run?.error_log?.substring(0, 200) || 'An error occurred during pipeline execution'
          }
        </Typography>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          {isCompleted && (
            <Button
              variant="contained"
              onClick={() => navigate(`/leads/${runId}`)}
              sx={{ bgcolor: '#5C2D8F', '&:hover': { bgcolor: '#4a2272' } }}
            >
              View Results →
            </Button>
          )}
          <Button
            variant="outlined"
            onClick={() => navigate('/dashboard')}
            sx={{ borderColor: '#D6D6D6', color: '#3D3D3D', '&:hover': { borderColor: '#ADADAD', bgcolor: '#FAFAFA' } }}
          >
            Dashboard
          </Button>
        </Box>
      </Box>
    );
  }

  // ── Running ────────────────────────────────────────────────────────────────
  return (
    <Box
      sx={{
        minHeight: 'calc(100vh - 56px)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box sx={{ textAlign: 'center', mb: 2.5, flexShrink: 0 }}>
        <Typography sx={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#F4693B', mb: '5px' }}>
          qlGen · AI Pipeline
        </Typography>
        <Typography sx={{ fontSize: 20, fontWeight: 700, color: '#141414', letterSpacing: '-0.4px', mb: '3px' }}>
          Generating Leads…
        </Typography>
        <Typography sx={{ fontSize: 12, color: '#ADADAD', minHeight: 16 }}>
          {sseMessage}
        </Typography>
      </Box>

      {/* Global progress bar */}
      <Box sx={{ width: 400, maxWidth: '90vw', mb: 2.5, flexShrink: 0 }}>
        <LinearProgress
          variant="determinate"
          value={globalProgress}
          sx={{
            height: 3, borderRadius: 999,
            bgcolor: '#F5F5F5',
            '& .MuiLinearProgress-bar': {
              background: 'linear-gradient(90deg, #5C2D8F, #7B4DB5)',
              borderRadius: 999,
              transition: 'width .8s cubic-bezier(.4,0,.2,1)',
            },
          }}
        />
      </Box>

      {/* Timeline */}
      <Box
        sx={{
          position: 'relative',
          width: 480, maxWidth: '92vw',
          flexShrink: 0,
        }}
      >
        {/* Vertical connector */}
        <Box
          sx={{
            position: 'absolute', left: 14, top: 16, bottom: 16,
            width: 2, bgcolor: '#F5F5F5', borderRadius: 999, zIndex: 0,
          }}
        />

        {stages.map((stage, i) => (
          <TimelineStep
            key={stage.key}
            index={i}
            title={stage.title}
            emoji={stage.emoji}
            state={getStepState(i)}
            message={i === currentIndex ? sseMessage : i < currentIndex ? 'Completed' : 'Waiting...'}
          />
        ))}
      </Box>

      {/* Info note */}
      <Box
        sx={{
          mt: 3, p: '12px 20px',
          bgcolor: '#F4EFFE', border: '1px solid #EDE0FA', borderRadius: '8px',
          maxWidth: 420, width: '100%',
        }}
      >
        <Typography sx={{ fontSize: 12, color: '#5C2D8F', textAlign: 'center', lineHeight: 1.6 }}>
          The agent is processing your ICP through all 4 stages. This may take several minutes.
        </Typography>
      </Box>
    </Box>
  );
};

export default PipelinePage;
