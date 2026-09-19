import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

export const Splash = () => {
  const navigate = useNavigate();
  const [fading, setFading] = useState(false);

  useEffect(() => {
    // Start fade out after 1.5s
    const fadeTimer = setTimeout(() => {
      setFading(true);
    }, 1500);

    // Navigate to dashboard after 2s (allowing 500ms for fade out)
    const navTimer = setTimeout(() => {
      navigate('/dashboard', { replace: true });
    }, 2000);

    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(navTimer);
    };
  }, [navigate]);

  return (
    <>
      <style>{`
        .splash-container {
          height: 100vh;
          width: 100vw;
          background-color: #212529; /* matching bootstrap bg-dark */
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          color: white;
          opacity: 1;
          transition: opacity 0.5s ease-out;
          position: fixed;
          top: 0;
          left: 0;
          z-index: 9999;
          padding: 2rem;
        }
        .splash-container.fading {
          opacity: 0;
        }
        .splash-logo {
          font-size: 2.5rem;
          font-weight: 700;
          letter-spacing: 0.15rem;
          margin-bottom: 0.5rem;
          text-align: center;
          animation: slideUp 0.8s ease-out forwards;
          color: #f8f9fa; /* text-light */
        }
        .splash-subtitle {
          font-size: 1.1rem;
          color: #adb5bd; /* text-muted */
          margin-bottom: 3rem;
          text-align: center;
          animation: slideUp 1s ease-out forwards;
        }
        .splash-pillars {
          display: flex;
          gap: 1rem;
          color: #6c757d;
          font-size: 0.9rem;
          letter-spacing: 0.1rem;
          text-transform: uppercase;
          flex-wrap: wrap;
          justify-content: center;
          animation: fadeIn 1.5s ease-out forwards;
        }
        .splash-spinner {
          margin-top: 4rem;
          width: 2.5rem;
          height: 2.5rem;
          border: 0.2rem solid rgba(255, 255, 255, 0.1);
          border-top-color: #0d6efd; /* text-primary */
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }
        
        @keyframes slideUp {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        @media (prefers-reduced-motion: reduce) {
          .splash-container, .splash-logo, .splash-subtitle, .splash-pillars, .splash-spinner {
            animation: none !important;
            transition: none !important;
          }
          /* Fallback static indicator if animation disabled */
          .splash-spinner::after {
            content: "•";
            color: #0d6efd;
            font-size: 3rem;
            line-height: 0.5;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
          }
          .splash-spinner {
            border: none;
            position: relative;
          }
        }
      `}</style>

      <div className={`splash-container ${fading ? 'fading' : ''}`}>
        <h1 className="splash-logo">DPI TRUST FRAMEWORK</h1>
        <p className="splash-subtitle">Decentralized Identity & Trust for Agentic AI</p>
        
        <div className="splash-pillars">
          <span>Identity</span>
          <span className="text-secondary">•</span>
          <span>Credentials</span>
          <span className="text-secondary">•</span>
          <span>Delegation</span>
          <span className="text-secondary">•</span>
          <span>Trust</span>
          <span className="text-secondary">•</span>
          <span>Verification</span>
        </div>
        
        <div className="splash-spinner" role="status" aria-label="Loading application"></div>
      </div>
    </>
  );
};
