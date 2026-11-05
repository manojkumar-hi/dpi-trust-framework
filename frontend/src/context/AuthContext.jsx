import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '../api/auth';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [accessToken, setAccessToken] = useState(localStorage.getItem('access_token'));
  const [isAuthenticated, setIsAuthenticated] = useState(!!accessToken);
  const [agentId, setAgentId] = useState(null);
  const [orgId, setOrgId] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    if (accessToken) {
      localStorage.setItem('access_token', accessToken);
      setIsAuthenticated(true);
      try {
        const payload = JSON.parse(atob(accessToken.split('.')[1]));
        setAgentId(payload.dpi_agent_id || null);
        setOrgId(payload.dpi_org_id);
        if (payload.dpi_role === 'organization_admin') {
          authApi.currentUser().then(setCurrentUser).catch(() => setCurrentUser(null));
        }
      } catch (e) {
        console.error("Failed to parse token payload");
      }
    } else {
      localStorage.removeItem('access_token');
      setIsAuthenticated(false);
      setAgentId(null);
      setOrgId(null);
      setCurrentUser(null);
    }
  }, [accessToken]);

  const login = (token) => {
    setAccessToken(token);
  };

  const logout = async () => {
    try {
      if (accessToken) await authApi.logout();
    } finally {
      setAccessToken(null);
    }
  };

  return (
    <AuthContext.Provider value={{ accessToken, isAuthenticated, agentId, orgId, currentUser, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
