import React from 'react';

export const StatCard = ({ title, value, icon, description }) => {
  return (
    <div className="card stat-card mb-3 border-secondary shadow-sm">
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="card-title mb-0 fw-semibold">{title}</h5>
          {icon && <div className={`stat-card-icon stat-card-icon-${icon}`}><i className={`bi bi-${icon} fs-4`}></i></div>}
        </div>
        <h2 className="card-text stat-card-value fw-bold">{value}</h2>
        {description && <p className="card-text small text-muted mb-0">{description}</p>}
      </div>
    </div>
  );
};
