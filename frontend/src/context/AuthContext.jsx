import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [accessToken, setAccessToken] = useState(localStorage.getItem('access_token'));
  const [isAuthenticated, setIsAuthenticated] = useState(!!accessToken);
  const [agentId, setAgentId] = useState(null);
  const [orgId, setOrgId] = useState(null);

  useEffect(() => {
    if (accessToken) {
      localStorage.setItem('access_token', accessToken);
      setIsAuthenticated(true);
      try {
        const payload = JSON.parse(atob(accessToken.split('.')[1]));
        setAgentId(payload.dpi_agent_id || payload.sub);
        setOrgId(payload.dpi_org_id);
      } catch (e) {
        console.error("Failed to parse token payload");
      }
    } else {
      localStorage.removeItem('access_token');
      setIsAuthenticated(false);
      setAgentId(null);
      setOrgId(null);
    }
  }, [accessToken]);

  const login = (token) => {
    setAccessToken(token);
  };

  const logout = () => {
    setAccessToken(null);
  };

  return (
    <AuthContext.Provider value={{ accessToken, isAuthenticated, agentId, orgId, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
