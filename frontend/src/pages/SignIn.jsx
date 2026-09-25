import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { useAuth } from '../context/AuthContext';

export const SignIn = () => {
  const [organizations, setOrganizations] = useState([]);
  const [agents, setAgents] = useState([]);
  
  const [selectedOrg, setSelectedOrg] = useState('');
  const [selectedAgent, setSelectedAgent] = useState('');
  
  const [loadingOrgs, setLoadingOrgs] = useState(true);
  const [loadingAgents, setLoadingAgents] = useState(false);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    const fetchOrgs = async () => {
      try {
        const response = await apiClient.get('/organizations');
        setOrganizations(response.data);
      } catch (err) {
        setErrorMsg('Failed to load organizations.');
      } finally {
        setLoadingOrgs(false);
      }
    };
    fetchOrgs();
  }, []);

  useEffect(() => {
    if (selectedOrg) {
      const fetchAgents = async () => {
        setLoadingAgents(true);
        try {
          const response = await apiClient.get(`/agents?organization_id=${selectedOrg}`);
          setAgents(response.data);
          setSelectedAgent('');
        } catch (err) {
          setErrorMsg('Failed to load agents.');
        } finally {
          setLoadingAgents(false);
        }
      };
      fetchAgents();
    } else {
      setAgents([]);
      setSelectedAgent('');
    }
  }, [selectedOrg]);

  const handleSignIn = async (e) => {
    e.preventDefault();
    if (!selectedOrg || !selectedAgent) return;
    
    setIsAuthenticating(true);
    setErrorMsg('');
    
    try {
      const response = await apiClient.post('/auth/login/dev', {
        organization_id: selectedOrg,
        agent_id: selectedAgent
      });
      const { access_token } = response.data;
      if (access_token) {
        login(access_token);
        navigate('/dashboard', { replace: true });
      }
    } catch (err) {
      setErrorMsg('Authentication failed. Please try again.');
    } finally {
      setIsAuthenticating(false);
    }
  };

  return (
    <div className="d-flex flex-column vh-100 bg-dark text-light justify-content-center align-items-center">
      <div className="card bg-darker border-secondary shadow-lg" style={{ width: '400px', backgroundColor: '#1e1e1e' }}>
        <div className="card-body p-5">
          <div className="text-center mb-4">
            <h4 className="mb-1 fw-bold">DPI Trust Framework</h4>
            <p className="text-muted small">Authentication Portal</p>
          </div>

          {errorMsg && (
            <div className="alert alert-danger py-2 small mb-3">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSignIn}>
            <div className="mb-3">
              <label className="form-label text-muted small fw-semibold">Select Organization</label>
              <select 
                className="form-select bg-dark text-light border-secondary"
                value={selectedOrg}
                onChange={(e) => setSelectedOrg(e.target.value)}
                disabled={loadingOrgs || isAuthenticating}
              >
                <option value="">-- Choose an Organization --</option>
                {organizations.map(org => (
                  <option key={org.id} value={org.id}>{org.name}</option>
                ))}
              </select>
            </div>

            <div className="mb-4">
              <label className="form-label text-muted small fw-semibold">Select Agent</label>
              <select 
                className="form-select bg-dark text-light border-secondary"
                value={selectedAgent}
                onChange={(e) => setSelectedAgent(e.target.value)}
                disabled={!selectedOrg || loadingAgents || isAuthenticating}
              >
                <option value="">-- Choose an Agent --</option>
                {agents.map(agent => (
                  <option key={agent.id} value={agent.id}>{agent.name}</option>
                ))}
              </select>
            </div>

            <button 
              type="submit" 
              className="btn btn-primary w-100 py-2 fw-semibold"
              disabled={!selectedOrg || !selectedAgent || isAuthenticating}
            >
              {isAuthenticating ? 'Authenticating...' : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
