import React, { useState, useEffect } from 'react';
import './TopNav.css';

export default function TopNav({ onMenuClick, pageTitle }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  };

  const formatDate = (date) => {
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <header className="top-nav">
      <div className="top-nav-left">
        <button className="menu-toggle" onClick={onMenuClick} aria-label="Toggle navigation">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
        <h2 className="page-title">{pageTitle}</h2>
      </div>
      <div className="top-nav-center">
        <div className="datetime">
          <div className="date">{formatDate(time)}</div>
          <div className="clock">{formatTime(time)} UTC</div>
        </div>
      </div>
      <div className="top-nav-right">
        <div className="operator-info">
          <div className="operator-avatar">OP</div>
          <span className="operator-name">Operator</span>
        </div>
      </div>
    </header>
  );
}