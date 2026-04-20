/**
 * Main App component.
 * Sets up routing, auth context, and layout.
 */
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/ui/Navbar';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import LocationPage from './pages/LocationPage';
import LogoutKioskPage from './pages/LogoutKioskPage';
import AdminPage from './pages/AdminPage';
import Spinner from './components/ui/Spinner';

/**
 * Protected route wrapper — requires full authentication (password + face).
 */
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, isFaceVerified, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated || !isFaceVerified) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

/**
 * Guest route wrapper — redirects to dashboard if already authenticated.
 */
const GuestRoute = ({ children }) => {
  const { isAuthenticated, isFaceVerified, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isAuthenticated && isFaceVerified) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

import useScreenProtection from './hooks/useScreenProtection';

const AppRoutes = () => {
  useScreenProtection();

  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route
          path="/login"
          element={
            <GuestRoute>
              <LoginPage />
            </GuestRoute>
          }
        />
        <Route
          path="/register"
          element={
            <GuestRoute>
              <RegisterPage />
            </GuestRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/location"
          element={
            <ProtectedRoute>
              <LocationPage />
            </ProtectedRoute>
          }
        />
        <Route path="/logout-kiosk" element={<LogoutKioskPage />} />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
};

const App = () => {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <AppRoutes />
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              borderRadius: '12px',
              background: '#333',
              color: '#fff',
              fontSize: '14px',
            },
          }}
        />
      </AuthProvider>
    </Router>
  );
};

export default App;
