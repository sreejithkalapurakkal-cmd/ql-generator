import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

const WelcomePage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-label">Getting Started</div>
          <h1 className="page-title">Welcome to qlGen</h1>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
            New Search
          </Button>
        </div>
      </div>

      {/* Hero Banner */}
      <div className="welcome-hero">
        <div className="welcome-hero-title-container">
          <h2 className="welcome-hero-title">Qualified Lead Generation</h2>
          <div className="welcome-hero-badge">AI-Powered</div>
        </div>
        <p className="welcome-hero-sub">
          qlGen discovers, enriches, and BANT-scores high-fit companies and contacts based on your Ideal Customer Profile —
          replacing hours of manual prospecting with a single, intelligent pipeline run.
        </p>
      </div>

      {/* How It Works */}
      <div className="welcome-section-title">How It Works</div>
      <div className="welcome-steps-row">
        <div className="welcome-step-card">
          <div className="wstep-num">01</div>
          <div className="wstep-title-container">
            <div className="wstep-icon">🎯</div>
            <div className="wstep-title">Define Your ICP</div>
          </div>
        </div>
        <div className="wstep-arrow">→</div>
        <div className="welcome-step-card">
          <div className="wstep-num">02</div>
          <div className="wstep-title-container">
            <div className="wstep-icon">🔍</div>
            <div className="wstep-title">AI Searches &amp; Enriches</div>
          </div>
        </div>
        <div className="wstep-arrow">→</div>
        <div className="welcome-step-card">
          <div className="wstep-num">03</div>
          <div className="wstep-title-container">
            <div className="wstep-icon">📊</div>
            <div className="wstep-title">BANT Scoring</div>
          </div>
        </div>
        <div className="wstep-arrow">→</div>
        <div className="welcome-step-card">
          <div className="wstep-num">04</div>
          <div className="wstep-title-container">
            <div className="wstep-icon">📤</div>
            <div className="wstep-title">Export Qualified Leads</div>
          </div>
        </div>
      </div>

      {/* Data Sources */}
      <div className="welcome-section-title">Data Sources</div>
      <div className="welcome-sources-grid">
        <div className="welcome-source-card">
          <img src="images/hunter.svg" alt="Hunter" className="welcome-source-icon" />
          <div className="wsource-name">Hunter</div>
          <div className="wsource-desc">Professional email discovery and verification at scale</div>
        </div>
        <div className="welcome-source-card">
          <img src="images/apollo.jpeg" alt="Apollo" className="welcome-source-icon" />
          <div className="wsource-name">Apollo</div>
          <div className="wsource-desc">B2B contact database with 275M+ verified records</div>
        </div>
        <div className="welcome-source-card">
          <img src="images/exa.jpeg" alt="Exa" className="welcome-source-icon" />
          <div className="wsource-name">Exa</div>
          <div className="wsource-desc">Neural web search for deep company intelligence</div>
        </div>
        <div className="welcome-source-card">
          <img src="images/tavily.jpeg" alt="Tavily" className="welcome-source-icon" />
          <div className="wsource-name">Tavily</div>
          <div className="wsource-desc">Real-time AI search optimised for business research</div>
        </div>
        <div className="welcome-source-card">
          <img src="images/duckduckgo.svg" alt="DuckDuckGo" className="welcome-source-icon" />
          <div className="wsource-name">DuckDuckGo</div>
          <div className="wsource-desc">Privacy-first web search for unbiased signals</div>
        </div>
        <div className="welcome-source-card">
          <img src="images/lusha.svg" alt="Lusha" className="welcome-source-icon" />
          <div className="wsource-name">Lusha</div>
          <div className="wsource-desc">Direct dials and mobile numbers for decision-makers</div>
        </div>
        <div className="welcome-source-card">
          <img src="images/clay.png" alt="Clay" className="welcome-source-icon" />
          <div className="wsource-name">Clay</div>
          <div className="wsource-desc">Workflow automation and multi-source enrichment layer</div>
        </div>
      </div>

      {/* CTA Bar */}
      <div className="welcome-cta-bar">
        <div>
          <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--g900)', letterSpacing: '-0.3px' }}>
            Ready to find your next best customers?
          </div>
          <div style={{ fontSize: 13.5, color: 'var(--g500)', marginTop: 4 }}>
            Create an ICP and let qlGen do the research.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
            New Search
          </Button>
        </div>
      </div>
    </div>
  );
};

export default WelcomePage;
