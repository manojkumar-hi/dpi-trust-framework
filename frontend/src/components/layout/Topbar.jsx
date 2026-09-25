import React, { useEffect, useState } from 'react';
import apiClient from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export const Topbar = () => {
  const [healthStatus, setHealthStatus] = useState('Checking...');
  const [isConnected, setIsConnected] = useState(false);
  const [agentName, setAgentName] = useState('Loading...');
  const { isAuthenticated, agentId, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await apiClient.get('/health');
        if (response.data && response.data.status === 'ok' || response.data.status === 'healthy') {
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

  useEffect(() => {
    if (isAuthenticated && agentId) {
      const fetchAgent = async () => {
        try {
          const response = await apiClient.get(`/agents/${agentId}`);
          setAgentName(response.data.name);
        } catch (e) {
          setAgentName('Agent');
        }
      };
      fetchAgent();
    }
  }, [isAuthenticated, agentId]);

  const handleSignOut = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <nav className="navbar navbar-expand navbar-dark bg-dark border-bottom border-secondary px-3">
      <span className="navbar-brand mb-0 h1">DPI TRUST FRAMEWORK</span>
      
      <div className="ms-auto d-flex align-items-center gap-3">
        {/* Backend health */}
        <div className="d-flex align-items-center me-3 border-end border-secondary pe-3">
          <span className="text-light me-2">System Status</span>
          <i className={`bi bi-circle-fill me-1 ${isConnected ? 'text-success' : 'text-danger'}`} style={{ fontSize: '0.6rem' }}></i>
          <span className={isConnected ? 'text-success' : 'text-danger'}>{healthStatus}</span>
        </div>

        {/* Auth Status */}
        {isAuthenticated && (
          <div className="d-flex align-items-center gap-2">
            <span className="badge bg-success">Authenticated</span>
            <span className="text-light small fw-bold">Signed in as: {agentName}</span>
            <button 
              className="btn btn-sm btn-outline-danger ms-2"
              onClick={handleSignOut}
            >
              Sign Out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
};
