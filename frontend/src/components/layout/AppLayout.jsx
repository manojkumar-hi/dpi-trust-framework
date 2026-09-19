import React from 'react';
import { Outlet } from 'react-router-dom';
import { Topbar } from './Topbar';
import { Sidebar } from './Sidebar';

export const AppLayout = () => {
  return (
    <div className="d-flex flex-column vh-100 bg-dark text-light overflow-hidden">
      <Topbar />
      <div className="d-flex flex-grow-1 overflow-hidden">
        <Sidebar />
        <main className="flex-grow-1 p-4 overflow-auto bg-darker" style={{ backgroundColor: '#121212' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};
