import React from 'react';

export const Credentials = () => {
  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Credentials</h2>
          <p className="text-muted">Verifiable Credentials issued to identities within the network.</p>
        </div>
      </div>
      <div className="card bg-dark border-secondary text-center p-5">
        <p className="text-muted mb-0">No credentials data loaded.</p>
        <small className="text-muted">Connect to backend to retrieve verifiable credentials.</small>
      </div>
    </div>
  );
};
