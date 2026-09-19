import React from 'react';

export const Audit = () => {
  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Audit & Traceability</h2>
          <p className="text-muted">Immutable cryptographic logs anchored to Hyperledger Fabric.</p>
        </div>
      </div>
      <div className="card bg-dark border-secondary text-center p-5">
        <p className="text-muted mb-0">No audit logs retrieved.</p>
        <small className="text-muted">Connect to backend to view audit trails.</small>
      </div>
    </div>
  );
};
