import React from 'react';

export const Delegations = () => {
  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Delegations</h2>
          <p className="text-muted">Cryptographic delegations of authority within the trust framework.</p>
        </div>
      </div>
      <div className="card bg-dark border-secondary text-center p-5">
        <p className="text-muted mb-0">No delegation data loaded.</p>
        <small className="text-muted">Connect to backend to retrieve delegations.</small>
      </div>
    </div>
  );
};
