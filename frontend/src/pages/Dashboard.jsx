import React from 'react';
import { StatCard } from '../components/common/StatCard';

export const Dashboard = () => {
  return (
    <div className="container-fluid">
      <div className="row mb-4">
        <div className="col-12">
          <h2 className="mb-1">DPI Trust Framework</h2>
          <p className="text-muted fs-5">Identity, Credentials & Trust for Agentic AI</p>
        </div>
      </div>

      <div className="row mb-4">
        <div className="col-md-3">
          <StatCard title="Organizations" value="—" icon="building" description="Not connected" />
        </div>
        <div className="col-md-3">
          <StatCard title="Agents" value="—" icon="robot" description="Not connected" />
        </div>
        <div className="col-md-3">
          <StatCard title="Credentials" value="—" icon="card-heading" description="Not connected" />
        </div>
        <div className="col-md-3">
          <StatCard title="Delegations" value="—" icon="diagram-3" description="Not connected" />
        </div>
      </div>

      <div className="row mb-4">
        <div className="col-12">
          <div className="card bg-dark border-secondary">
            <div className="card-header border-secondary bg-transparent">
              <h5 className="mb-0">Trust Decision Pipeline</h5>
            </div>
            <div className="card-body">
              <div className="d-flex flex-column align-items-center text-center">
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Agent Identity</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Verifiable Credential</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Delegation</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Credential Status</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-secondary mb-2 w-50">Trust Evaluation</div>
                <i className="bi bi-arrow-down fs-4 text-muted mb-2"></i>
                <div className="p-3 bg-secondary rounded bg-opacity-25 border border-primary mb-2 w-50 text-primary fw-bold">Policy Authorization</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="row">
        <div className="col-12">
          <div className="card bg-dark border-secondary">
            <div className="card-header border-secondary bg-transparent">
              <h5 className="mb-0">System Capabilities</h5>
            </div>
            <div className="card-body">
              <ul className="list-group list-group-flush bg-transparent">
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Decentralized Agent Identity</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Verifiable Credentials</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Cryptographic Delegation</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Dynamic Trust Evaluation</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Policy-Based Authorization</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Cryptographic Revocation</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Cross-Organization Verification</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Audit & Traceability</li>
                <li className="list-group-item bg-transparent text-light border-secondary"><i className="bi bi-check-circle text-success me-2"></i> Hyperledger Fabric Anchoring</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
