import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { message, Spin } from 'antd';
import {
  ArrowLeftOutlined, FileTextOutlined, ReloadOutlined,
  DownOutlined, CheckCircleOutlined, LoadingOutlined,
} from '@ant-design/icons';
import CitedBody from '../components/ui/CitedBody';
import SectionSkeleton from '../components/ui/SectionSkeleton';
import SourceCitationChip from '../components/ui/SourceCitationChip';
import {
  getLatestBrief, getBriefVersions, getBriefVersion,
  generateStructuredBrief, startBriefGeneration, getBriefGenerationStreamUrl,
} from '../api/briefApi';
import { getListMembers } from '../api/trackingApi';
import { useSSEStream } from '../hooks/useSSEStream';
import type { BriefRevision, BriefSection } from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

const SECTION_ICONS: Record<string, string> = {
  'overview': '🏢',
  'org': '👥',
  'signals': '⚡',
  'competitive': '🎯',
  'tech': '⚙️',
  'budget': '💰',
  'why-now': '⏱️',
  'angle': '💬',
};

// ─── Streaming Hook ─────────────────────────────────────────────────────────

type GenPhase = 'idle' | 'scanning' | 'streaming' | 'done';

function useGenFlow(sectionCount: number, shouldGenerate: boolean) {
  const [phase, setPhase] = useState<GenPhase>(shouldGenerate ? 'scanning' : 'done');
  const [visibleCount, setVisible] = useState(shouldGenerate ? 0 : sectionCount);

  useEffect(() => {
    if (!shouldGenerate) {
      setPhase('done');
      setVisible(sectionCount);
      return;
    }
    setPhase('scanning');
    setVisible(0);

    let intervalId: ReturnType<typeof setInterval> | null = null;

    const scanTimer = setTimeout(() => {
      setPhase('streaming');
      let count = 0;
      intervalId = setInterval(() => {
        count++;
        setVisible(count);
        if (count >= sectionCount) {
          clearInterval(intervalId!);
          intervalId = null;
          setPhase('done');
        }
      }, 350);
    }, 1500);

    return () => {
      clearTimeout(scanTimer);
      if (intervalId) clearInterval(intervalId);
    };
  }, [shouldGenerate, sectionCount]);

  return { phase, visibleCount };
}

// ─── Revision Dropdown ──────────────────────────────────────────────────────

function RevisionDropdown({
  revisions,
  current,
  onSelect,
}: {
  revisions: BriefRevision[];
  current: BriefRevision;
  onSelect: (r: BriefRevision) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const formatDate = (iso: string | null) => {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 h-8 px-3 text-xs font-medium bg-white border border-gray-200 rounded-lg text-gray-700 hover:border-gray-300 hover:bg-gray-50 transition-colors"
      >
        <span className="font-mono text-purple-700">v{current.version}</span>
        <span className="text-gray-400">·</span>
        <span>{formatDate(current.created_at)}</span>
        <DownOutlined className="text-[10px] text-gray-400" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full mt-1 w-72 bg-white border border-gray-200 rounded-lg shadow-lg z-50 overflow-hidden">
            {revisions.map(r => (
              <button
                key={r.version}
                onClick={() => { onSelect(r); setOpen(false); }}
                className={`w-full flex items-start gap-3 px-3 py-2.5 text-left hover:bg-gray-50 transition-colors ${
                  r.version === current.version ? 'bg-purple-50' : ''
                }`}
              >
                <span className={`font-mono text-xs px-1.5 py-0.5 rounded mt-0.5 shrink-0 ${
                  r.version === current.version ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'
                }`}>
                  v{r.version}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-800 leading-tight">
                    {r.trigger_signal_headline || `Version ${r.version}`}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                    {formatDate(r.created_at)}
                    <span>·</span>
                    <span>{r.word_count?.toLocaleString() || 0} words</span>
                    {r.generated_by === 'auto' && (
                      <span className="ml-1 text-purple-600">✦ Auto</span>
                    )}
                  </p>
                </div>
                {r.version === current.version && (
                  <CheckCircleOutlined className="text-purple-500 shrink-0 mt-0.5" />
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

const ResearchBriefPage: React.FC = () => {
  const params = useParams<{ id: string; listId: string; membershipId: string }>();
  // Support both /accounts/:id/brief and /tracking/:listId/company/:membershipId/brief
  const companyKbId = params.id;
  const listId = params.listId;
  const membershipId = params.membershipId;
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [companyName, setCompanyName] = useState('');
  const [currentRevision, setCurrentRevision] = useState<BriefRevision | null>(null);
  const [allRevisions, setAllRevisions] = useState<BriefRevision[]>([]);
  const [isNewGeneration, setIsNewGeneration] = useState(false);

  // SSE streaming state
  const [agentThought, setAgentThought] = useState('');
  const [streamingSections, setStreamingSections] = useState<string[]>([]);

  const briefStream = useSSEStream({
    terminalEvents: ['brief_ready', 'brief_failed'],
    onEvent: (eventType, data) => {
      if (eventType === 'agent_thought') {
        setAgentThought(data.message as string || '');
      }
      if (eventType === 'section_complete') {
        setStreamingSections(prev => [...prev, data.heading as string || '']);
      }
    },
    onComplete: async (eventType) => {
      if (eventType === 'brief_ready') {
        // Refresh brief data
        await fetchBrief();
        setIsNewGeneration(true);
        setGenerating(false);
        setAgentThought('');
        setStreamingSections([]);
        message.success('Research brief generated');
      } else if (eventType === 'brief_failed') {
        setGenerating(false);
        setAgentThought('');
        setStreamingSections([]);
        message.error('Failed to generate brief');
      }
    },
    onError: () => {
      setGenerating(false);
      setAgentThought('');
      setStreamingSections([]);
    },
  });

  // Citation state
  const [citationHighlight, setCitationHighlight] = useState<{ sectionId: string; sourceIdx: number } | null>(null);
  const sourceChipRefs = useRef<Record<string, HTMLSpanElement | null>>({});
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // TOC active section
  const [activeSection, setActiveSection] = useState('');
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const sections: BriefSection[] = currentRevision?.sections || [];

  const { phase, visibleCount } = useGenFlow(
    sections.length,
    isNewGeneration && sections.length > 0,
  );

  const [resolvedKbId, setResolvedKbId] = useState<string | null>(companyKbId || null);

  // ── Resolve company KB ID from tracking route ──

  useEffect(() => {
    if (companyKbId) {
      setResolvedKbId(companyKbId);
      return;
    }
    if (!listId || !membershipId) return;
    // Fetch member to get company_kb_id and name
    getListMembers(listId, { limit: 200, offset: 0 })
      .then(res => {
        const found = (res.data.members || []).find(
          (m: { membership_id: string }) => m.membership_id === membershipId,
        );
        if (found) {
          setResolvedKbId(found.company_kb_id);
          setCompanyName(found.company_name || '');
        }
      })
      .catch(() => {});
  }, [companyKbId, listId, membershipId]);

  // ── Fetch data ──

  const fetchBrief = useCallback(async () => {
    if (!resolvedKbId) return;
    setLoading(true);
    try {
      const [latestRes, versionsRes] = await Promise.all([
        getLatestBrief(resolvedKbId),
        getBriefVersions(resolvedKbId),
      ]);
      const brief = latestRes.data.brief;
      if (brief) {
        setCurrentRevision(brief);
      }
      setAllRevisions(versionsRes.data.revisions || []);
    } catch {
      // No brief yet — that's fine
    } finally {
      setLoading(false);
    }
  }, [resolvedKbId]);

  useEffect(() => { fetchBrief(); }, [fetchBrief]);

  // ── Intersection observer for TOC ──

  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(e => {
          if (e.isIntersecting) setActiveSection(e.target.id);
        });
      },
      { rootMargin: '-20% 0px -70% 0px' },
    );
    Object.values(sectionRefs.current).forEach(el => {
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [currentRevision, visibleCount]);

  // ── Handlers ──

  const handleGenerate = async () => {
    if (!resolvedKbId || generating) return;
    setGenerating(true);
    setIsNewGeneration(true);
    setAgentThought('');
    setStreamingSections([]);
    try {
      const res = await startBriefGeneration(resolvedKbId!);
      const streamUrl = getBriefGenerationStreamUrl(resolvedKbId!, res.data.run_id);
      briefStream.connect(streamUrl);
    } catch {
      message.error('Failed to start brief generation');
      setGenerating(false);
    }
  };

  const handleSelectRevision = async (r: BriefRevision) => {
    if (!resolvedKbId) return;
    setIsNewGeneration(false);
    try {
      const res = await getBriefVersion(resolvedKbId!, r.version);
      if (res.data.brief) {
        setCurrentRevision(res.data.brief);
      }
    } catch {
      message.error('Failed to load revision');
    }
  };

  const handleCite = useCallback((sectionId: string, sourceIdx: number) => {
    if (highlightTimer.current) clearTimeout(highlightTimer.current);
    setCitationHighlight({ sectionId, sourceIdx });
    sourceChipRefs.current[`${sectionId}-${sourceIdx}`]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    highlightTimer.current = setTimeout(() => setCitationHighlight(null), 1600);
  }, []);

  const scrollToSection = (domId: string) => {
    sectionRefs.current[domId]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // ── Computed values ──

  const showProgress = phase === 'scanning' || phase === 'streaming' || generating;
  const progress = phase === 'scanning' ? 15
    : sections.length > 0 ? Math.round((visibleCount / sections.length) * 100) : 0;

  const formatDate = (iso: string | null) => {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  // ── Loading state ──

  if (loading) {
    return (
      <div className="max-w-[1200px] mx-auto py-24 text-center">
        <Spin size="large" />
        <p className="text-gray-400 mt-4 text-sm">Loading brief...</p>
      </div>
    );
  }

  // ── No brief yet ──

  if (!currentRevision) {
    return (
      <div className="max-w-[1200px] mx-auto">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-4 transition-colors"
        >
          <ArrowLeftOutlined className="text-xs" />
          Back
        </button>

        <div className="bg-white border border-gray-200 rounded-lg">
          <div className="flex flex-col items-center py-14 px-8 gap-5">
            <div className="w-14 h-14 rounded-2xl bg-purple-50 border border-purple-100 flex items-center justify-center">
              <FileTextOutlined className="text-xl text-purple-500" />
            </div>
            <div className="text-center max-w-sm">
              <p className="text-sm font-semibold text-gray-800 mb-1.5">No research brief yet</p>
              <p className="text-xs text-gray-400 leading-relaxed">
                Generate a brief to get a structured view of this account — signals, org structure,
                competitive context, and a recommended outreach angle.
              </p>
            </div>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
            >
              {generating ? <LoadingOutlined /> : '✦'}
              {generating ? 'Generating...' : 'Generate brief'}
            </button>
            <p className="text-[11px] text-gray-300">
              Briefs are also auto-generated when high-confidence signals fire.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Brief view ──

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* Back breadcrumb */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-4 transition-colors"
      >
        <ArrowLeftOutlined className="text-xs" />
        Back
      </button>

      {/* Document header */}
      <div className="bg-white border border-gray-200 rounded-lg px-5 py-4 mb-5">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-purple-100 flex items-center justify-center shrink-0">
              <FileTextOutlined className="text-purple-600" />
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-900">
                {companyName || 'Company'} — Research Brief
              </h1>
              <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-400">
                <FileTextOutlined className="text-[10px]" />
                <span>{currentRevision.word_count?.toLocaleString() || 0} words</span>
                <span>·</span>
                <span>{sections.length} sections</span>
                {currentRevision.generated_by === 'auto' && (
                  <>
                    <span>·</span>
                    <span className="flex items-center gap-0.5 text-purple-600">
                      ✦ AI generated
                    </span>
                  </>
                )}
              </div>
              {currentRevision.trigger_signal_headline && (
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">
                    Research Agent
                  </span>
                  <span className="flex items-center gap-1 text-[10px] text-gray-400">
                    Auto-generated when
                    <span className="inline-flex items-center gap-0.5 bg-amber-50 border border-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full font-medium">
                      ⚡ {currentRevision.trigger_signal_headline}
                    </span>
                    fired · {formatDate(currentRevision.created_at)}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {allRevisions.length > 1 && (
              <RevisionDropdown
                revisions={allRevisions}
                current={currentRevision}
                onSelect={handleSelectRevision}
              />
            )}
            <button
              onClick={handleGenerate}
              disabled={generating || phase === 'streaming' || phase === 'scanning'}
              className={`flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-lg border transition-all ${
                generating
                  ? 'bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-white border-gray-200 text-gray-700 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              <ReloadOutlined className={generating ? 'animate-spin' : ''} />
              {generating ? 'Regenerating...' : 'Regenerate'}
            </button>
          </div>
        </div>

        {/* Progress bar */}
        {showProgress && (
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-purple-600 flex items-center gap-1">
                ✦ {generating && briefStream.progress > 0
                  ? briefStream.statusLabel || `Generating... ${briefStream.progress}%`
                  : phase === 'scanning'
                    ? 'Scanning signal history...'
                    : `Generating sections... (${visibleCount}/${sections.length})`}
              </span>
              <span className="text-xs text-gray-400">{generating ? briefStream.progress : progress}%</span>
            </div>
            <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-500 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${generating ? briefStream.progress : progress}%` }}
              />
            </div>
            {agentThought && (
              <p className="text-xs text-purple-500 italic mt-1.5 animate-pulse">{agentThought}</p>
            )}
            {streamingSections.length > 0 && generating && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {streamingSections.map((s, i) => (
                  <span key={i} className="text-[10px] bg-purple-50 text-purple-600 px-1.5 py-0.5 rounded">
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Body: TOC sidebar + section list */}
      <div className="flex gap-6 items-start">

        {/* Sticky TOC */}
        <div className="w-52 shrink-0 sticky top-6">
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="px-3 py-2.5 border-b border-gray-100">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Contents</p>
            </div>
            <nav className="py-1">
              {sections.map((s, idx) => {
                const visible = phase === 'done' || idx < visibleCount;
                return (
                  <button
                    key={s.id}
                    disabled={!visible}
                    onClick={() => scrollToSection(`section-${s.id}`)}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors ${
                      !visible ? 'opacity-30 cursor-not-allowed' : ''
                    } ${
                      visible && activeSection === `section-${s.id}`
                        ? 'text-purple-700 bg-purple-50'
                        : visible ? 'text-gray-600 hover:text-gray-800 hover:bg-gray-50' : ''
                    }`}
                  >
                    <span className="text-[10px] leading-none w-4 shrink-0">
                      {SECTION_ICONS[s.id] || '•'}
                    </span>
                    <span className="leading-tight">{s.heading}</span>
                  </button>
                );
              })}
            </nav>

            {allRevisions.length > 1 && (
              <div className="border-t border-gray-100 px-3 py-2.5">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Revisions</p>
                <div className="space-y-1">
                  {allRevisions.slice(0, 5).map(r => (
                    <button
                      key={r.version}
                      onClick={() => handleSelectRevision(r)}
                      className={`w-full flex items-center gap-2 text-xs rounded px-1.5 py-1 text-left transition-colors ${
                        currentRevision?.version === r.version
                          ? 'bg-purple-100 text-purple-700 font-medium'
                          : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <span className="font-mono">v{r.version}</span>
                      <span className="truncate text-gray-400">{formatDate(r.created_at)}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Section content */}
        <div className="flex-1 min-w-0">
          {generating && !currentRevision ? (
            <div className="bg-white border border-gray-200 rounded-lg px-8 py-16 text-center">
              <div className="relative w-10 h-10 mx-auto mb-4">
                <LoadingOutlined className="text-3xl text-purple-400" />
              </div>
              <p className="text-sm font-medium text-gray-700 mb-1">
                {briefStream.statusLabel || 'Analysing latest signals...'}
              </p>
              {agentThought ? (
                <p className="text-xs text-purple-500 italic max-w-md mx-auto animate-pulse">{agentThought}</p>
              ) : (
                <p className="text-xs text-gray-400">
                  Pulling from signals and public intelligence sources
                </p>
              )}
              {briefStream.progress > 0 && (
                <div className="w-48 mx-auto mt-3">
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-purple-500 rounded-full transition-all duration-500 ease-out"
                      style={{ width: `${briefStream.progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          ) : phase === 'scanning' ? (
            <div className="bg-white border border-gray-200 rounded-lg px-8 py-16 text-center">
              <div className="w-10 h-10 rounded-full border-2 border-purple-200 border-t-purple-600 animate-spin mx-auto mb-4" />
              <p className="text-sm font-medium text-gray-700 mb-1">Scanning signal history...</p>
              <p className="text-xs text-gray-400">Compiling sources · drafting sections · checking coverage</p>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              {sections.map((section, idx) => {
                const visible = phase === 'done' || idx < visibleCount;
                const isCurrent = phase === 'streaming' && idx === visibleCount - 1;
                const isHighlightedSection = citationHighlight?.sectionId === section.id;

                return (
                  <div
                    key={section.id}
                    id={`section-${section.id}`}
                    ref={el => { sectionRefs.current[`section-${section.id}`] = el; }}
                    className="border-b border-gray-100 last:border-0"
                  >
                    {visible ? (
                      <div className="px-8 py-6" style={{ animation: phase !== 'done' ? 'fadeIn 0.4s ease-out' : undefined }}>
                        {/* Section header */}
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-base">{SECTION_ICONS[section.id] || '•'}</span>
                          <h2 className="text-sm font-bold text-gray-900">{section.heading}</h2>
                          <div className="flex-1 h-px bg-gray-100 ml-2" />
                          <span className="text-xs text-gray-300 font-mono shrink-0">
                            {String(idx + 1).padStart(2, '0')} / {String(sections.length).padStart(2, '0')}
                          </span>
                        </div>

                        {/* Insufficient data placeholder */}
                        {section.insufficient ? (
                          <div className="flex items-center gap-2 p-3 bg-gray-50 border border-dashed border-gray-200 rounded-lg text-xs text-gray-400">
                            <span>⚠</span>
                            Insufficient sourced data — this section will populate as signals are detected.
                          </div>
                        ) : (
                          <>
                            {/* Body with inline citations */}
                            {section.body && (
                              <p className="text-sm text-gray-700 leading-relaxed">
                                <CitedBody
                                  text={section.body}
                                  sources={section.sources}
                                  highlightIdx={isHighlightedSection ? citationHighlight!.sourceIdx : null}
                                  onCite={(si) => handleCite(section.id, si)}
                                />
                              </p>
                            )}

                            {/* Bullets */}
                            {section.bullets && section.bullets.length > 0 && (
                              <ul className="mt-3 space-y-1.5">
                                {section.bullets.map((bullet, bi) => (
                                  <li key={bi} className="flex items-start gap-2 text-sm text-gray-600">
                                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                                    <span className="leading-relaxed">{bullet}</span>
                                  </li>
                                ))}
                              </ul>
                            )}

                            {/* Source chips */}
                            {section.sources && section.sources.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-gray-50">
                                <span className="text-[10px] text-gray-400 self-center mr-0.5">Sources:</span>
                                {section.sources.map((src, si) => (
                                  <SourceCitationChip
                                    key={si}
                                    source={src}
                                    index={si}
                                    isHighlighted={isHighlightedSection && citationHighlight?.sourceIdx === si}
                                    chipRef={el => { sourceChipRefs.current[`${section.id}-${si}`] = el; }}
                                  />
                                ))}
                              </div>
                            )}

                            {/* Confidence indicator */}
                            {section.confidence != null && section.confidence > 0 && (
                              <div className="mt-2 flex items-center gap-1.5 text-[10px] text-gray-300">
                                <span>Confidence:</span>
                                <div className="w-16 h-1 bg-gray-100 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${
                                      section.confidence >= 0.8 ? 'bg-emerald-400' :
                                      section.confidence >= 0.5 ? 'bg-amber-400' : 'bg-gray-300'
                                    }`}
                                    style={{ width: `${section.confidence * 100}%` }}
                                  />
                                </div>
                                <span>{Math.round(section.confidence * 100)}%</span>
                              </div>
                            )}
                          </>
                        )}

                        {/* Streaming cursor */}
                        {isCurrent && (
                          <span className="inline-block w-0.5 h-4 bg-purple-500 animate-pulse ml-1 align-middle" />
                        )}
                      </div>
                    ) : (
                      <SectionSkeleton
                        heading={section.heading}
                        icon={SECTION_ICONS[section.id] || '•'}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Footer */}
          {phase === 'done' && currentRevision && (
            <div className="flex items-center justify-between pt-4 pb-2 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                ✦ Generated {formatDate(currentRevision.created_at)}
                {currentRevision.trigger_signal_headline && ` · ${currentRevision.trigger_signal_headline}`}
              </span>
              <span>
                {currentRevision.word_count?.toLocaleString() || 0} words · {sections.length} sections
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ResearchBriefPage;
