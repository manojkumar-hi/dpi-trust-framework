import React from 'react';

export const Verification = () => {
  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Verification Sandbox</h2>
          <p className="text-muted">Simulate Service Provider verification of credentials and status lists.</p>
        </div>
      </div>
      <div className="card bg-dark border-secondary text-center p-5">
        <p className="text-muted mb-0">No verification sandbox loaded.</p>
        <small className="text-muted">Connect to backend to run verifications.</small>
      </div>
    </div>
  );
};
