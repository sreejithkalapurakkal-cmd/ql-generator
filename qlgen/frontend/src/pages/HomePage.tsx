import React from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchOutlined, UnorderedListOutlined } from '@ant-design/icons';

const HomePage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div style={{
      flex: 1,
      background: '#f8fafc',
      backgroundImage: 'linear-gradient(to right, #e2e8f080 1px, transparent 1px), linear-gradient(to bottom, #e2e8f080 1px, transparent 1px)',
      backgroundSize: '40px 40px',
      overflow: 'hidden',
      minHeight: 'calc(100vh - 60px)',
    }}>
      <main style={{ display: 'flex', alignItems: 'center', minHeight: 'calc(100vh - 60px)' }}>
        <div style={{
          maxWidth: 1400,
          margin: '0 auto',
          padding: '48px 32px',
          width: '100%',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 64,
          alignItems: 'center',
        }}>
          {/* Left Column - Content */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24, zIndex: 10 }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 16px',
              borderRadius: 9999,
              background: '#fce7f3',
              border: '1px solid #fbcfe8',
              color: '#db2777',
              fontWeight: 600,
              fontSize: 14,
              width: 'fit-content',
              marginBottom: 8,
            }}>
              ⚡ AI-Powered Lead Discovery
            </div>

            <h1 style={{
              fontSize: 56,
              fontWeight: 800,
              color: 'var(--g900)',
              lineHeight: 1.1,
              margin: 0,
            }}>
              Build a pipeline of <br />
              <span className="text-gradient">qualified leads</span> in minutes.
            </h1>

            <p style={{
              fontSize: 18,
              color: 'var(--g600)',
              lineHeight: 1.6,
              maxWidth: 560,
              fontWeight: 500,
              margin: 0,
            }}>
              Convert your Ideal Customer Profile (ICP) into a sales-ready list of target companies and key decision-makers. qlGen automatically discovers, enriches, and BANT-scores every opportunity.
            </p>

            <div style={{ display: 'flex', flexDirection: 'row', gap: 16, marginTop: 24 }}>
              <button
                onClick={() => navigate('/icp/new')}
                style={{
                  padding: '16px 32px',
                  background: 'var(--purple)',
                  color: 'white',
                  fontWeight: 700,
                  borderRadius: 12,
                  boxShadow: '0 8px 20px rgba(92, 45, 143, 0.3)',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                  fontSize: 18,
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#6d28d9';
                  e.currentTarget.style.boxShadow = '0 12px 25px rgba(92, 45, 143, 0.4)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--purple)';
                  e.currentTarget.style.boxShadow = '0 8px 20px rgba(92, 45, 143, 0.3)';
                }}
              >
                <SearchOutlined style={{ fontSize: 20 }} /> Start Your Search
              </button>

              <button
                onClick={() => navigate('/all-leads')}
                style={{
                  padding: '16px 32px',
                  background: 'white',
                  color: 'var(--g800)',
                  border: '2px solid var(--g200)',
                  fontWeight: 700,
                  borderRadius: 12,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                  fontSize: 18,
                  transition: 'all 0.2s',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--g50)';
                  e.currentTarget.style.borderColor = 'var(--g300)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'white';
                  e.currentTarget.style.borderColor = 'var(--g200)';
                }}
              >
                <UnorderedListOutlined style={{ fontSize: 20 }} /> Explore past searches
              </button>
            </div>
          </div>

          {/* Right Column - Fanout Graphic */}
          <div className="fanout-container" style={{ display: 'flex' }}>
            <svg className="connecting-lines" viewBox="0 0 600 500" preserveAspectRatio="xMidYMid meet">
              <g stroke="#cbd5e1" strokeWidth="2" strokeDasharray="6,6" fill="none">
                <path d="M300,250 L110,380" />
                <path d="M300,250 L60,250" />
                <path d="M300,250 L140,100" />
                <path d="M300,250 L300,40" />
                <path d="M300,250 L460,100" />
                <path d="M300,250 L540,250" />
                <path d="M300,250 L490,380" />
              </g>
            </svg>

            <div className="central-hub">qlGen</div>

            <div className="fanout-node fanout-node-1">
              <img src="images/linkedin.png" alt="LinkedIn" />
              <span>LinkedIn</span>
            </div>

            <div className="fanout-node fanout-node-2">
              <img src="images/lusha.svg" alt="Lusha" />
              <span>Lusha</span>
            </div>

            <div className="fanout-node fanout-node-3">
              <img src="images/duckduckgo.svg" alt="DuckDuckGo" />
              <span>DuckDuckGo</span>
            </div>

            <div className="fanout-node fanout-node-4">
              <img src="images/tavily.jpeg" alt="Tavily" />
              <span>Tavily</span>
            </div>

            <div className="fanout-node fanout-node-5">
              <img src="images/apollo.jpeg" alt="Apollo.io" />
              <span>Apollo.io</span>
            </div>

            <div className="fanout-node fanout-node-6">
              <img src="images/exa.jpeg" alt="Exa.ai" />
              <span>Exa.ai</span>
            </div>

            <div className="fanout-node fanout-node-7">
              <img src="images/hunter.svg" alt="Hunter.io" />
              <span>Hunter.io</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default HomePage;
