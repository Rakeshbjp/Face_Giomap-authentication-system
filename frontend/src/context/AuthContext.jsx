/**
 * Authentication context providing user state across the application.
 */
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { getProfile, healthCheck, logoutUser } from '../services/authService';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isFaceVerified, setIsFaceVerified] = useState(false);
  const [loading, setLoading] = useState(true);

  /**
   * Check if user is already logged in on mount.
   * Also handles tokens passed via URL params from external login pages (e.g. login.html).
   */
  useEffect(() => {
    const checkAuth = async () => {
      // ── External login bridge ──
      // If tokens are passed as URL params (from login.html or any external entry point),
      // consume them into localStorage and strip from the URL.
      const urlParams = new URLSearchParams(window.location.search);
      const urlToken = urlParams.get('access_token');
      const urlRefresh = urlParams.get('refresh_token');
      const urlUserId = urlParams.get('user_id');
      const urlRequiresFace = urlParams.get('requires_face') !== 'false';

      if (urlToken && urlUserId) {
        localStorage.setItem('access_token', urlToken);
        if (urlRefresh) localStorage.setItem('refresh_token', urlRefresh);
        localStorage.setItem('user_id', urlUserId);

        // Clean the URL so tokens aren't visible / bookmarkable
        const cleanUrl = window.location.origin + window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);

        // If face verification IS required, set password-authenticated state and let LoginPage handle face step
        if (urlRequiresFace) {
          setIsAuthenticated(true);
          setIsFaceVerified(false);
          setLoading(false);
          return;
        }
      }

      const token = localStorage.getItem('access_token');
      const faceVerifiedFlag = localStorage.getItem('face_verified') === 'true';
      const noCameraLogin = localStorage.getItem('no_camera_login') === 'true';

      if (token && (faceVerifiedFlag || noCameraLogin)) {
        try {
          const result = await getProfile();
          if (result.status) {
            setUser(result.data);
            setIsAuthenticated(true);
            setIsFaceVerified(true);
          }
        } catch {
          logout();
        }
      } else {
        // No token (new user / not logged in) — Ping backend to wake up the free Render instance (cold start mitigation)
        healthCheck().catch(() => {});
      }
      setLoading(false);
    };
    checkAuth();
  }, []);

  /**
   * Store tokens after password login.
   */
  const loginSuccess = useCallback((tokenData) => {
    localStorage.setItem('access_token', tokenData.access_token);
    localStorage.setItem('refresh_token', tokenData.refresh_token);
    localStorage.setItem('user_id', tokenData.user_id);
    setIsAuthenticated(true);
    setIsFaceVerified(false);
  }, []);

  /**
   * Mark face verification as complete.
   */
  const faceVerified = useCallback((userData) => {
    setIsFaceVerified(true);
    setUser(userData);
    localStorage.setItem('face_verified', 'true');
  }, []);

  /**
   * Clear all auth state and tokens.
   */
  const logout = useCallback(async () => {
    // Record logout on backend FIRST only if we have a token
    const token = localStorage.getItem('access_token');
    if (token) {
      try {
        await logoutUser();
      } catch {
        // Ignore errors — user is logging out anyway
      }
    }
    // Now clear local state
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('face_verified');
    localStorage.removeItem('no_camera_login');
    setUser(null);
    setIsAuthenticated(false);
    setIsFaceVerified(false);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isFaceVerified,
        loading,
        loginSuccess,
        faceVerified,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

/**
 * Hook to consume authentication context.
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
