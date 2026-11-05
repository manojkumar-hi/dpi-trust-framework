import React from 'react';
import { NavLink } from 'react-router-dom';

export const Sidebar = () => {
  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: 'speedometer2' },
    { path: '/agents', label: 'Agents', icon: 'robot' },
    { path: '/credentials', label: 'Credentials', icon: 'card-heading' },
    { path: '/delegations', label: 'Delegations', icon: 'diagram-3' },
    { path: '/pre-authorization', label: 'Pre-Authorization', icon: 'shield-lock' },
    { path: '/trust', label: 'Trust', icon: 'shield-check' },
    { path: '/audit', label: 'Audit', icon: 'journal-text' }
  ];

  return (
    <>
      <style>{`
        .sidebar-link {
          color: #adb5bd;
          transition: all 0.2s ease;
          border-radius: 0.375rem;
          padding: 0.75rem 1rem;
          font-weight: 500;
        }
        .sidebar-link:hover {
          color: #fff;
          background-color: rgba(255, 255, 255, 0.05);
        }
        .sidebar-link.active {
          color: #fff;
          background-color: rgba(13, 110, 253, 0.15); /* light primary bg */
          border-left: 4px solid #0d6efd;
          border-top-left-radius: 0;
          border-bottom-left-radius: 0;
        }
      `}</style>
      <div className="d-flex flex-column flex-shrink-0 p-3 text-white bg-dark border-end border-secondary" style={{ width: '250px', minHeight: 'calc(100vh - 57px)' }}>
        <ul className="nav nav-pills flex-column mb-auto gap-1">
          {navItems.map((item) => (
            <li className="nav-item" key={item.path}>
              <NavLink 
                to={item.path} 
                className={({ isActive }) => `nav-link sidebar-link d-flex align-items-center ${isActive ? 'active' : ''}`}
              >
                <i className={`bi bi-${item.icon} me-3 fs-5`}></i>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
};
