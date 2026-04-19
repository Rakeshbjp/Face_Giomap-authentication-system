/**
 * Authentication API service functions.
 * Wraps all auth-related HTTP calls.
 */
import api from './api';

/**
 * Register a new user with face images.
 * @param {Object} data - { name, email, phone, password, face_images: [base64...] }
 * @returns {Promise} API response
 */
export const registerUser = async (data) => {
  const response = await api.post('/auth/register', data);
  return response.data;
};

/**
 * Check if a user is already registered.
 * @param {string} email
 * @param {string} phone
 * @returns {Promise} API response
 */
export const checkUser = async (email, phone) => {
  try {
    const response = await api.post('/auth/check-user', { email, phone });
    return response.data;
  } catch (err) {
    const detail = err.response?.data?.detail;
    const message = Array.isArray(detail)
      ? detail.map((e) => e.msg).join(', ')
      : detail || err.response?.data?.message || 'Server connection error';
    return { status: false, message: message };
  }
};

/**
 * Login with email and password.
 * @param {string} email
 * @param {string} password
 * @returns {Promise} API response with tokens
 */
export const loginWithPassword = async (email, password, location = null) => {
  const payload = { email, password };
  if (location) {
    payload.location = location;
  }
  const response = await api.post('/auth/login', payload);
  return response.data;
};

/**
 * Verify face against stored embeddings.
 * @param {string} userId
 * @param {string} faceImage - Base64-encoded face image
 * @returns {Promise} Verification result
 */
export const verifyFace = async (userId, faceImage, challengeFrame = null) => {
  const payload = {
    user_id: userId,
    face_image: faceImage,
  };
  if (challengeFrame) {
    payload.challenge_frame = challengeFrame;
  }
  const response = await api.post('/auth/verify-face', payload);
  return response.data;
};

/**
 * Login using face recognition.
 * @param {string} userId
 * @param {string} faceImage - Base64-encoded face image
 * @returns {Promise} API response with tokens
 */
export const faceLogin = async (userId, faceImage, location = null, challengeFrame = null) => {
  try {
    const payload = {
      user_id: userId,
      face_image: faceImage,
    };
    if (location) {
      payload.location = location;
    }
    if (challengeFrame) {
      payload.challenge_frame = challengeFrame;
    }
    const response = await api.post('/auth/face-login', payload);
    return response.data;
  } catch (err) {
    const detail = err.response?.data?.detail;
    const message = Array.isArray(detail)
      ? detail.map((e) => e.msg).join(', ')
      : detail || 'Face login failed';
    return { status: false, message, confidence: null };
  }
};

/**
 * Get current user's profile.
 * @returns {Promise} User profile data
 */
export const getProfile = async () => {
  const response = await api.get('/auth/profile');
  return response.data;
};

/**
 * Health check.
 * @returns {Promise}
 */
export const healthCheck = async () => {
  const response = await api.get('/auth/health');
  return response.data;
};

/**
 * Add or update face data for the authenticated user.
 * @param {string[]} faceImages - Array of 4 base64-encoded face images
 * @returns {Promise} API response
 */
export const updateFaceData = async (faceImages) => {
  const response = await api.put('/auth/update-face', { face_images: faceImages });
  return response.data;
};

/**
 * Logout — records logout time in the database.
 * @returns {Promise} API response
 */
export const logoutUser = async () => {
  try {
    const response = await api.post('/auth/logout');
    return response.data;
  } catch {
    // Silently fail — user is logging out anyway
    return { status: false };
  }
};

/**
 * Reverse-geocode latitude/longitude to human-readable address.
 * @param {number} latitude
 * @param {number} longitude
 * @returns {Promise} { area, city, state, country, pincode, display_name }
 */
export const geocodeLocation = async (latitude, longitude) => {
  const response = await api.post('/auth/geocode', { latitude, longitude });
  return response.data;
};

export const getCompanySettings = async () => {
  const response = await api.get('/auth/settings');
  return response.data;
};

export const updateCompanySettings = async (hours_per_day, weekly_off) => {
  try {
    const response = await api.post('/auth/settings', { hours_per_day, weekly_off });
    return response.data;
  } catch (err) {
    const detail = err.response?.data?.detail;
    if (detail) throw new Error(Array.isArray(detail) ? detail.map(e => e.msg).join(', ') : detail);
    throw new Error(err.response?.data?.message || 'Failed to update company settings');
  }
};

export const kioskGetEmployee = async (employee_id) => {
  const response = await api.get(`/auth/kiosk/${employee_id}`);
  return response.data;
};

export const kioskLogoutEmployee = async (employee_id) => {
  const response = await api.post('/auth/kiosk/logout', { employee_id });
  return response.data;
};
