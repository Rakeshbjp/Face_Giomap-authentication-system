/**
 * Authentication context providing user state across the application.
 */
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { getProfile } from '../services/authService';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isFaceVerified, setIsFaceVerified] = useState(false);
  const [loading, setLoading] = useState(true);

  /**
   * Check if user is already logged in on mount.
   */
  useEffect(() => {
    const checkAuth = async () => {
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
  const logout = useCallback(() => {
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
