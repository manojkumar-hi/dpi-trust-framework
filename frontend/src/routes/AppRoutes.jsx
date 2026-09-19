import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { Dashboard } from '../pages/Dashboard';
import { Agents } from '../pages/Agents';
import { Credentials } from '../pages/Credentials';
import { Delegations } from '../pages/Delegations';
import { Trust } from '../pages/Trust';
import { Verification } from '../pages/Verification';
import { Audit } from '../pages/Audit';

const NotFound = () => (
  <div className="container-fluid d-flex flex-column justify-content-center align-items-center h-100">
    <h1 className="display-1 text-muted">404</h1>
    <h2 className="text-light">Page Not Found</h2>
    <p className="text-muted">The requested resource could not be located in the Trust Framework.</p>
  </div>
);

export const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/credentials" element={<Credentials />} />
        <Route path="/delegations" element={<Delegations />} />
        <Route path="/trust" element={<Trust />} />
        <Route path="/verification" element={<Verification />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
};
