import React from 'react';

export const StatusBadge = ({ status, text }) => {
  let badgeClass = 'bg-secondary';
  
  if (status === 'success' || status === 'active' || status === 'valid') {
    badgeClass = 'bg-success';
  } else if (status === 'warning' || status === 'pending') {
    badgeClass = 'bg-warning text-dark';
  } else if (status === 'danger' || status === 'revoked' || status === 'error') {
    badgeClass = 'bg-danger';
  }

  return (
    <span className={`badge ${badgeClass}`}>{text || status}</span>
  );
};
