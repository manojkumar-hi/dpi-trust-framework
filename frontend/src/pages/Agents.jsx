import React from 'react';
import { LoadingState } from '../components/common/LoadingState';

export const Agents = () => {
  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2>Agents</h2>
          <p className="text-muted">Agent identities registered with the Trust Framework.</p>
        </div>
      </div>
      <div className="card bg-dark border-secondary text-center p-5">
        <p className="text-muted mb-0">No agent data loaded.</p>
        <small className="text-muted">Connect to backend to retrieve agents.</small>
      </div>
    </div>
  );
};
