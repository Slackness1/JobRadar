import type { ReactElement } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import AppLayout from './AppLayout';
import { readMockSession } from './auth/mockSession';
import Login from './pages/Login';

interface RequirePreviewSessionProps {
  children: ReactElement;
}

function RequirePreviewSession({ children }: RequirePreviewSessionProps) {
  if (readMockSession()) {
    return children;
  }

  return <Navigate to="/login" replace />;
}

function LoginRoute() {
  if (readMockSession()) {
    return <Navigate to="/" replace />;
  }

  return <Login />;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route
        path="*"
        element={(
          <RequirePreviewSession>
            <AppLayout />
          </RequirePreviewSession>
        )}
      />
    </Routes>
  );
}
