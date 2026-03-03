import React, { useEffect, useRef } from 'react';

interface Source {
  name: string;
  color: string;
  bg: string;
  desc: string;
  svg: string;
}

const SOURCES: Source[] = [
  {
    name: 'Hunter',
    color: '#E8490F',
    bg: '#FFF0EC',
    desc: 'Email discovery & verification',
    svg: '/images/hunter.svg',
  },
  {
    name: 'Apollo',
    color: '#5B4CFF',
    bg: '#EEECFF',
    desc: 'B2B contact database · 275M+ records',
    svg: '/images/apollo-circle.png',
  },
  {
    name: 'Exa',
    color: '#0FA37F',
    bg: '#E6F8F3',
    desc: 'Neural web search · deep company intel',
    svg: '/images/exa-circle.png',
  },
  {
    name: 'Tavily',
    color: '#0066FF',
    bg: '#E5EEFF',
    desc: 'Real-time AI-powered search',
    svg: '/images/tavily.jpeg',
  },
  {
    name: 'Lusha',
    color: '#2D9BF0',
    bg: '#E6F4FE',
    desc: 'Direct dials & decision-maker contacts',
    svg: '/images/lusha.svg',
  },
  {
    name: 'DuckDuckGo',
    color: '#DE5833',
    bg: '#FFF0EC',
    desc: 'Privacy-first web search signals',
    svg: '/images/duckduckgo.svg',
  },
];

const NODE_R = 28;
const NODE_R_HOV = 34;
const CENTER_R = 42;

const OrbitAnimation: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const bgCanvasRef = useRef<HTMLCanvasElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>();
  const tRef = useRef(0);
  const pulsePhaseRef = useRef(0);
  const hoveredIdxRef = useRef(-1);
  const iconsRef = useRef<HTMLImageElement[]>([]);
  const phasesRef = useRef<number[]>([]);

  useEffect(() => {
    // Pre-load icons
    iconsRef.current = SOURCES.map(s => {
      const img = new Image();
      img.src = s.svg;
      return img;
    });

    phasesRef.current = SOURCES.map((_, i) => (i / SOURCES.length) * Math.PI * 2);

    const canvas = canvasRef.current;
    const bgCanvas = bgCanvasRef.current;
    const tooltip = tooltipRef.current;
    if (!canvas || !bgCanvas || !tooltip) return;

    const wrap = canvas.parentElement;
    if (!wrap) return;

    const W = wrap.clientWidth || 520;
    const H = wrap.clientHeight || 420;

    [canvas, bgCanvas].forEach(c => {
      c.width = W * window.devicePixelRatio;
      c.height = H * window.devicePixelRatio;
      c.style.width = W + 'px';
      c.style.height = H + 'px';
    });

    const ctx = canvas.getContext('2d');
    const bgCtx = bgCanvas.getContext('2d');
    if (!ctx || !bgCtx) return;

    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    bgCtx.scale(window.devicePixelRatio, window.devicePixelRatio);

    const cx = W / 2;
    const cy = H / 2;
    const PAD = NODE_R_HOV + 18;
    const R = Math.min(W / 2, H / 2) - PAD;

    // Draw static background
    const drawOrbitBg = () => {
      bgCtx.clearRect(0, 0, W, H);
      bgCtx.beginPath();
      bgCtx.arc(cx, cy, R, 0, Math.PI * 2);
      bgCtx.strokeStyle = 'rgba(92,45,143,0.10)';
      bgCtx.lineWidth = 1.5;
      bgCtx.setLineDash([3, 8]);
      bgCtx.stroke();
      bgCtx.setLineDash([]);

      SOURCES.forEach((_, i) => {
        const angle = (i / SOURCES.length) * Math.PI * 2 - Math.PI / 2;
        const tx = cx + R * Math.cos(angle);
        const ty = cy + R * Math.sin(angle);
        bgCtx.beginPath();
        bgCtx.arc(tx, ty, 3, 0, Math.PI * 2);
        bgCtx.fillStyle = 'rgba(92,45,143,0.15)';
        bgCtx.fill();
      });
    };

    drawOrbitBg();

    const hexAlpha = (hex: string, a: number) => {
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return `rgba(${r},${g},${b},${a})`;
    };

    const getNodePositions = (time: number) => {
      return SOURCES.map((_, i) => {
        const baseAngle = (i / SOURCES.length) * Math.PI * 2 - Math.PI / 2;
        const drift = Math.sin(time * 0.5 + phasesRef.current[i]) * 0.03;
        const angle = baseAngle + drift;
        const rDrift = Math.sin(time * 0.35 + phasesRef.current[i] * 1.3) * 3;
        return {
          x: cx + (R + rDrift) * Math.cos(angle),
          y: cy + (R + rDrift) * Math.sin(angle),
        };
      });
    };

    const drawConnection = (x1: number, y1: number, x2: number, y2: number, color: string, alpha: number) => {
      const grad = ctx.createLinearGradient(x1, y1, x2, y2);
      grad.addColorStop(0, hexAlpha('#9b6dd6', alpha * 0.7));
      grad.addColorStop(0.55, hexAlpha(color, alpha * 0.55));
      grad.addColorStop(1, hexAlpha(color, alpha * 0.10));
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = grad;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 6]);
      ctx.lineDashOffset = -tRef.current * 20;
      ctx.stroke();
      ctx.setLineDash([]);

      const prog = ((tRef.current * 0.4 + phasesRef.current[SOURCES.findIndex(s => s.color === color)]) % 1 + 1) % 1;
      const dx = x1 + (x2 - x1) * prog;
      const dy = y1 + (y2 - y1) * prog;
      ctx.beginPath();
      ctx.arc(dx, dy, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = hexAlpha(color, alpha * 0.9);
      ctx.fill();
    };

    const drawNode = (x: number, y: number, src: Source, idx: number, isHovered: boolean) => {
      const r = isHovered ? NODE_R_HOV : NODE_R;
      const glowR = r + (isHovered ? 22 : 14);

      const glow = ctx.createRadialGradient(x, y, r * 0.5, x, y, glowR);
      glow.addColorStop(0, hexAlpha(src.color, isHovered ? 0.25 : 0.10));
      glow.addColorStop(1, hexAlpha(src.color, 0));
      ctx.beginPath();
      ctx.arc(x, y, glowR, 0, Math.PI * 2);
      ctx.fillStyle = glow;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = '#fff';
      ctx.shadowColor = hexAlpha(src.color, isHovered ? 0.5 : 0.2);
      ctx.shadowBlur = isHovered ? 22 : 8;
      ctx.fill();
      ctx.shadowBlur = 0;

      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.strokeStyle = hexAlpha(src.color, isHovered ? 0.9 : 0.45);
      ctx.lineWidth = isHovered ? 2.5 : 1.8;
      ctx.stroke();

      const img = iconsRef.current[idx];
      const iconSize = r;
      if (img.complete && img.naturalWidth > 0) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(x, y, r - 3, 0, Math.PI * 2);
        ctx.clip();
        ctx.drawImage(img, x - iconSize / 2, y - iconSize / 2, iconSize, iconSize);
        ctx.restore();
      } else {
        ctx.font = `700 ${r * 0.52}px 'DM Sans', sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = src.color;
        ctx.fillText(src.name.slice(0, 2), x, y);
      }

      if (isHovered) {
        ctx.font = "600 11px 'DM Sans', sans-serif";
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillStyle = src.color;
        ctx.fillText(src.name, x, y + r + 5);
      }
    };

    const drawCenter = (pulse: number) => {
      const cr = CENTER_R;

      const p1 = cr + 14 + Math.sin(pulse) * 6;
      const ringGrad1 = ctx.createRadialGradient(cx, cy, cr, cx, cy, p1 + 12);
      ringGrad1.addColorStop(0, 'rgba(124,58,237,0.10)');
      ringGrad1.addColorStop(1, 'rgba(124,58,237,0)');
      ctx.beginPath();
      ctx.arc(cx, cy, p1 + 12, 0, Math.PI * 2);
      ctx.fillStyle = ringGrad1;
      ctx.fill();

      const p2 = cr + 8 + Math.sin(pulse * 0.7 + 1.2) * 5;
      ctx.beginPath();
      ctx.arc(cx, cy, p2, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(124,58,237,0.09)';
      ctx.lineWidth = 1;
      ctx.stroke();

      const innerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr + 6);
      innerGlow.addColorStop(0, 'rgba(167,105,255,0.12)');
      innerGlow.addColorStop(1, 'rgba(92,45,143,0)');
      ctx.beginPath();
      ctx.arc(cx, cy, cr + 6, 0, Math.PI * 2);
      ctx.fillStyle = innerGlow;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy, cr, 0, Math.PI * 2);
      const cGrad = ctx.createRadialGradient(cx - 10, cy - 12, 2, cx, cy, cr);
      cGrad.addColorStop(0, '#ffffff');
      cGrad.addColorStop(0.5, '#f5f0ff');
      cGrad.addColorStop(1, '#ede8ff');
      ctx.fillStyle = cGrad;
      ctx.shadowColor = 'rgba(92,45,143,0.22)';
      ctx.shadowBlur = 24;
      ctx.fill();
      ctx.shadowBlur = 0;

      ctx.beginPath();
      ctx.arc(cx, cy, cr, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(124,58,237,0.22)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      const sheenGrad = ctx.createLinearGradient(cx - cr * 0.5, cy - cr * 0.6, cx + cr * 0.2, cy);
      sheenGrad.addColorStop(0, 'rgba(255,255,255,0.9)');
      sheenGrad.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.beginPath();
      ctx.arc(cx, cy, cr - 2, Math.PI * 1.2, Math.PI * 1.9);
      ctx.strokeStyle = sheenGrad;
      ctx.lineWidth = 3;
      ctx.stroke();

      ctx.font = "900 21px 'DM Sans', sans-serif";
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#3b0764';
      ctx.fillText('ql', cx, cy - 7);

      ctx.font = "500 11px 'DM Sans', sans-serif";
      ctx.fillStyle = 'rgba(92,45,143,0.65)';
      ctx.fillText('Gen', cx, cy + 10);

      ctx.font = "10px sans-serif";
      ctx.fillStyle = 'rgba(124,58,237,0.45)';
      ctx.fillText('✦', cx + cr * 0.52, cy - cr * 0.48);
    };

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      const nodes = getNodePositions(tRef.current);

      SOURCES.forEach((src, i) => {
        const { x, y } = nodes[i];
        const isHov = hoveredIdxRef.current === i;
        const baseAlpha = isHov ? 0.9 : (hoveredIdxRef.current >= 0 ? 0.12 : 0.5);
        const alpha = baseAlpha + Math.sin(tRef.current * 1.1 + phasesRef.current[i]) * 0.04;
        drawConnection(cx, cy, x, y, src.color, alpha);
      });

      drawCenter(pulsePhaseRef.current);

      nodes.forEach(({ x, y }, i) => {
        drawNode(x, y, SOURCES[i], i, hoveredIdxRef.current === i);
      });
    };

    const loop = () => {
      tRef.current += 0.007;
      pulsePhaseRef.current += 0.035;
      draw();
      rafRef.current = requestAnimationFrame(loop);
    };

    const onMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const nodes = getNodePositions(tRef.current);
      let found = -1;
      nodes.forEach(({ x, y }, i) => {
        if (Math.hypot(mx - x, my - y) < NODE_R_HOV + 4) found = i;
      });
      hoveredIdxRef.current = found;

      if (found >= 0) {
        const { x, y } = nodes[found];
        const src = SOURCES[found];
        tooltip.textContent = src.name + '  ·  ' + src.desc;
        tooltip.style.left = x + 'px';
        tooltip.style.top = (y - NODE_R_HOV - 14) + 'px';
        tooltip.style.opacity = '1';
        canvas.style.cursor = 'pointer';
      } else {
        tooltip.style.opacity = '0';
        canvas.style.cursor = 'default';
      }
    };

    const onMouseLeave = () => {
      hoveredIdxRef.current = -1;
      tooltip.style.opacity = '0';
    };

    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseleave', onMouseLeave);
    loop();

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      canvas.removeEventListener('mousemove', onMouseMove);
      canvas.removeEventListener('mouseleave', onMouseLeave);
    };
  }, []);

  return (
    <div className="wh-orbit-wrap">
      <canvas ref={bgCanvasRef} id="orbitBgCanvas" />
      <canvas ref={canvasRef} className="wh-orbit-canvas" />
      <div ref={tooltipRef} className="wh-orbit-tooltip" />
    </div>
  );
};

export default OrbitAnimation;
