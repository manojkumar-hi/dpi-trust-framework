import React from 'react';

export const StatCard = ({ title, value, icon, description }) => {
  return (
    <>
      <style>{`
        .stat-card {
          transition: transform 0.2s ease, box-shadow 0.2s ease;
          background-color: #1a1d20; /* slightly lighter than bg-dark */
        }
        .stat-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 .5rem 1rem rgba(0,0,0,.15)!important;
        }
      `}</style>
      <div className="card text-white stat-card mb-3 border-secondary shadow-sm">
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="card-title mb-0 text-muted fw-semibold">{title}</h5>
            {icon && <div className="p-2 bg-primary bg-opacity-10 rounded"><i className={`bi bi-${icon} fs-4 text-primary`}></i></div>}
          </div>
          <h2 className="card-text fw-bold">{value}</h2>
          {description && <p className="card-text small text-muted mb-0">{description}</p>}
        </div>
      </div>
    </>
  );
};
