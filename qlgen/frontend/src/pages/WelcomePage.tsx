import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import OrbitAnimation from '../components/OrbitAnimation';

const WelcomePage: React.FC = () => {
  const navigate = useNavigate();
  const bgCanvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const bgCanvas = bgCanvasRef.current;
    if (!bgCanvas) return;

    const parent = bgCanvas.parentElement;
    if (!parent) return;

    const pw = parent.clientWidth || 1200;
    const ph = parent.clientHeight || 900;
    bgCanvas.width = pw * window.devicePixelRatio;
    bgCanvas.height = ph * window.devicePixelRatio;
    bgCanvas.style.width = pw + 'px';
    bgCanvas.style.height = ph + 'px';

    const bc = bgCanvas.getContext('2d');
    if (!bc) return;
    bc.scale(window.devicePixelRatio, window.devicePixelRatio);

    const g1 = bc.createRadialGradient(pw * 0.5, -80, 0, pw * 0.5, -80, pw * 0.65);
    g1.addColorStop(0, 'rgba(124,58,237,0.07)');
    g1.addColorStop(1, 'rgba(124,58,237,0)');
    bc.beginPath();
    bc.rect(0, 0, pw, ph);
    bc.fillStyle = g1;
    bc.fill();

    const g2 = bc.createRadialGradient(pw * 0.85, ph * 0.1, 0, pw * 0.85, ph * 0.1, pw * 0.3);
    g2.addColorStop(0, 'rgba(59,130,246,0.06)');
    g2.addColorStop(1, 'rgba(59,130,246,0)');
    bc.beginPath();
    bc.rect(0, 0, pw, ph);
    bc.fillStyle = g2;
    bc.fill();

    bc.fillStyle = 'rgba(100,90,140,0.055)';
    const spacing = 36;
    for (let gx = spacing; gx < pw; gx += spacing) {
      for (let gy = spacing; gy < ph; gy += spacing) {
        bc.beginPath();
        bc.arc(gx, gy, 1.2, 0, Math.PI * 2);
        bc.fill();
      }
    }

    [0.32, 0.62, 0.88].forEach(frac => {
      bc.beginPath();
      bc.moveTo(0, ph * frac);
      bc.lineTo(pw, ph * frac);
      bc.strokeStyle = 'rgba(120,110,160,0.06)';
      bc.lineWidth = 1;
      bc.stroke();
    });
  }, []);

  return (
    <div style={{ width: '100%', background: '#F4F4F8', position: 'relative', minHeight: 'calc(100vh - 60px)', overflow: 'hidden' }}>
      <canvas ref={bgCanvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }} />
      {/* Hero Section */}
      <section className="wh-hero" style={{ position: 'relative', zIndex: 1 }}>
        <div className="wh-hero-left">
          <div className="wh-ai-badge">
            <div className="wh-ai-dot">✦</div>
            AI-Powered Lead Discovery
          </div>

          <h1 className="wh-hero-title">
            Build a pipeline of <em>qualified leads</em> <br />in minutes.
          </h1>

          <p className="wh-hero-sub">
            Describe your ideal customer once. qlGen searches across millions of companies, finds the best fits, and ranks them - so your team can focus on closing.
          </p>

          <p className="wh-cta-message">Ready to find your next best customers?</p>

          <div className="wh-buttons">
            <div className="wh-btn-group">
              <button className="wh-btn-primary" onClick={() => navigate('/icp/new')}>
                ✦ &nbsp;New Search
              </button>
              <span className="wh-btn-hint">Describe your ideal customer & let qlGen find high-fit leads.</span>
            </div>
            <div className="wh-btn-group">
              <button className="wh-btn-secondary" onClick={() => navigate('/dashboard')}>
                View Past Searches →
              </button>
              <span className="wh-btn-secondary-hint">View and manage your previously generated leads.</span>
            </div>
          </div>
        </div>
<<<<<<< HEAD
        <p className="welcome-hero-sub">
          qlGen discovers, enriches, and BANT-scores high-fit companies and contacts based on your Ideal Customer Profile —
          replacing hours of manual prospecting with a single, intelligent search.
        </p>
      </div>

      {/* How It Works */}
      <div className="welcome-section-title">How It Works</div>
      <div className="welcome-steps-row">
        <div className="welcome-step-card">
          <div className="wstep-num">01</div>
          <div className="wstep-title-container">
            <div className="wstep-icon">🎯</div>
            <div className="wstep-title">Define Search Criteria</div>
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
=======

        <div className="wh-hero-right">
          <OrbitAnimation />
        </div>
      </section>

      <hr className="wh-divider" />

      {/* How It Works */}
      <section className="wh-hiw">
        <div className="wh-section-eyebrow">Simple Process</div>
        <h2 className="wh-section-title">How It Works</h2>
>>>>>>> c5396d41 (feat: update ui styling)

        <div className="wh-steps">
          <div className="wh-step">
            <div className="wh-step-connector"></div>
            <div className="wh-step-icon-wrap">
              🎯
              <div className="wh-step-num">1</div>
            </div>
            <div className="wh-step-title">Define Your Ideal Customer</div>
            <div className="wh-step-desc">Tell qlGen who you're targeting - industry, size, location, and buyer role.</div>
          </div>
          <div className="wh-step">
            <div className="wh-step-connector"></div>
            <div className="wh-step-icon-wrap">
              🤖
              <div className="wh-step-num">2</div>
            </div>
            <div className="wh-step-title">AI Finds & Evaluates Prospects</div>
            <div className="wh-step-desc">qlGen searches across multiple data sources and shortlists the best-matching companies and contacts.</div>
          </div>
          <div className="wh-step">
            <div className="wh-step-icon-wrap">
              📊
              <div className="wh-step-num">3</div>
            </div>
            <div className="wh-step-title">Get Ranked Leads with BANT Score</div>
            <div className="wh-step-desc">Every lead is scored and ranked so your team always calls the right people first.</div>
          </div>
        </div>

        {/* BANT Mini Strip */}
        <div className="wh-bant">
          <div className="wh-bant-item">
            <div className="wh-bant-letter">B</div>
            <div className="wh-bant-word">Budget</div>
            <div className="wh-bant-phrase">Can they afford your solution?</div>
          </div>
<<<<<<< HEAD
          <div style={{ fontSize: 13.5, color: 'var(--g500)', marginTop: 4 }}>
            Define your search criteria and let qlGen do the research.
=======
          <div className="wh-bant-item">
            <div className="wh-bant-letter">A</div>
            <div className="wh-bant-word">Authority</div>
            <div className="wh-bant-phrase">Are we speaking to decision-makers?</div>
          </div>
          <div className="wh-bant-item">
            <div className="wh-bant-letter">N</div>
            <div className="wh-bant-word">Need</div>
            <div className="wh-bant-phrase">Do they match your offering?</div>
          </div>
          <div className="wh-bant-item">
            <div className="wh-bant-letter">T</div>
            <div className="wh-bant-word">Timeline</div>
            <div className="wh-bant-phrase">Are they ready to buy?</div>
>>>>>>> c5396d41 (feat: update ui styling)
          </div>
        </div>
      </section>
    </div>
  );
};

export default WelcomePage;
