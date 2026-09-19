import React from 'react';

export const LoadingState = ({ message = 'Loading...' }) => {
  return (
    <div className="d-flex flex-column justify-content-center align-items-center py-5 text-muted">
      <div className="spinner-border mb-3" role="status">
        <span className="visually-hidden">Loading...</span>
      </div>
      <p>{message}</p>
    </div>
  );
};
