import React from 'react';
import { NavLink } from 'react-router-dom';

export const Sidebar = () => {
  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: 'speedometer2' },
    { path: '/agents', label: 'Agents', icon: 'robot' },
    { path: '/credentials', label: 'Credentials', icon: 'card-heading' },
    { path: '/delegations', label: 'Delegations', icon: 'diagram-3' },
    { path: '/trust', label: 'Trust', icon: 'shield-check' },
    { path: '/verification', label: 'Verification', icon: 'check2-all' },
    { path: '/audit', label: 'Audit', icon: 'journal-text' }
  ];

  return (
    <div className="d-flex flex-column flex-shrink-0 p-3 text-white bg-dark border-end border-secondary" style={{ width: '250px', minHeight: 'calc(100vh - 57px)' }}>
      <ul className="nav nav-pills flex-column mb-auto">
        {navItems.map((item) => (
          <li className="nav-item mb-1" key={item.path}>
            <NavLink 
              to={item.path} 
              className={({ isActive }) => `nav-link text-white ${isActive ? 'active bg-primary' : ''}`}
            >
              <i className={`bi bi-${item.icon} me-2`}></i>
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  );
};
