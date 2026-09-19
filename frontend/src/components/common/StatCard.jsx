import React from 'react';

export const StatCard = ({ title, value, icon, description }) => {
  return (
    <div className="card text-white bg-dark mb-3 border-secondary">
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="card-title mb-0 text-muted">{title}</h5>
          {icon && <i className={`bi bi-${icon} fs-4 text-primary`}></i>}
        </div>
        <h2 className="card-text">{value}</h2>
        {description && <p className="card-text small text-muted">{description}</p>}
      </div>
    </div>
  );
};
