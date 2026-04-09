/**
 * Axios-based API client for the Face Auth backend.
 * Handles base URL, auth headers, and error interceptors.
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 120s — Render free tier can take ~50s to cold-start
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — attach JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor — handle errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Timeout or network error (Render cold start)
    if (error.code === 'ECONNABORTED' || !error.response) {
      error.isTimeout = true;
      error.friendlyMessage = 'Server is waking up — please wait a moment and try again.';
      return Promise.reject(error);
    }
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      // Only auto-redirect for expired tokens, not for login/register failures
      if (!url.includes('/auth/login') && !url.includes('/auth/register')) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_id');
        if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
