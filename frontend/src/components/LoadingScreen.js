import React from 'react';

const LoadingScreen = ({ fullscreen = false, progress = 0 }) => {
  // SVG border progress (rectangle)
  const size = 320;
  const border = 10;
  const box = size - border;
  const radius = 36;
  const perimeter = 2 * (box + box - 2 * radius) + 2 * Math.PI * radius;
  const progressLength = (progress / 100) * perimeter;

  // SVG path for rounded rectangle
  const rectPath = `M${border/2+radius},${border/2} \
    H${box+border/2-radius} \
    Q${box+border/2},${border/2} ${box+border/2},${border/2+radius} \
    V${box+border/2-radius} \
    Q${box+border/2},${box+border/2} ${box+border/2-radius},${box+border/2} \
    H${border/2+radius} \
    Q${border/2},${box+border/2} ${border/2},${box+border/2-radius} \
    V${border/2+radius} \
    Q${border/2},${border/2} ${border/2+radius},${border/2}`;

  return (
    <div className={`loading-screen ${fullscreen ? 'fullscreen' : ''}`} style={{
      minHeight: '100vh', minWidth: '100vw',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: fullscreen ? 'linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%)' : undefined
    }}>
      <div className="loading-content" style={{ position: 'relative', minHeight: size, minWidth: size }}>
        <svg width={size} height={size} style={{ position: 'absolute', top: 0, left: 0, zIndex: 1 }}>
          <path
            d={rectPath}
            fill="none"
            stroke="#f3f4f6"
            strokeWidth={border}
          />
          <path
            d={rectPath}
            fill="none"
            stroke="url(#splashGradient)"
            strokeWidth={border}
            strokeDasharray={perimeter}
            strokeDashoffset={perimeter - progressLength}
            style={{ transition: 'stroke-dashoffset 0.5s cubic-bezier(0.4,0,0.2,1)' }}
          />
          <defs>
            <linearGradient id="splashGradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#dc2626" />
              <stop offset="100%" stopColor="#b91c1c" />
            </linearGradient>
          </defs>
        </svg>
        <div style={{
          width: box - 48,
          height: box - 48,
          background: 'white',
          borderRadius: radius - 12,
          position: 'absolute',
          top: border + 24,
          left: border + 24,
          right: border + 24,
          bottom: border + 24,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 2,
          boxShadow: '0 8px 32px 0 rgba(0,0,0,0.04)'
        }}>
          <img 
            src="/Deriv.png" 
            alt="Deriv" 
            className="loading-logo"
            style={{ width: '180px', height: 'auto', objectFit: 'contain' }}
          />
        </div>
      </div>
    </div>
  );
};

export default LoadingScreen; 