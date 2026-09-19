import React, { useEffect, useState } from 'react';
import apiClient from '../../api/client';

export const Topbar = () => {
  const [healthStatus, setHealthStatus] = useState('Checking...');
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await apiClient.get('/health');
        if (response.data && response.data.status === 'ok') {
          setHealthStatus('Backend Connected');
          setIsConnected(true);
        } else {
          setHealthStatus('Backend Status Unknown');
          setIsConnected(false);
        }
      } catch (error) {
        setHealthStatus('Backend Offline');
        setIsConnected(false);
      }
    };

    checkHealth();
  }, []);

  return (
    <nav className="navbar navbar-expand navbar-dark bg-dark border-bottom border-secondary px-3">
      <span className="navbar-brand mb-0 h1">DPI TRUST FRAMEWORK</span>
      
      <div className="ms-auto d-flex align-items-center">
        <span className="text-light me-3">System Status</span>
        <div className="d-flex align-items-center">
          <i className={`bi bi-circle-fill me-2 ${isConnected ? 'text-success' : 'text-danger'}`} style={{ fontSize: '0.6rem' }}></i>
          <span className={isConnected ? 'text-success' : 'text-danger'}>{healthStatus}</span>
        </div>
      </div>
    </nav>
  );
};
