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
export const verifyFace = async (userId, faceImage) => {
  const response = await api.post('/auth/verify-face', {
    user_id: userId,
    face_image: faceImage,
  });
  return response.data;
};

/**
 * Login using face recognition.
 * @param {string} userId
 * @param {string} faceImage - Base64-encoded face image
 * @returns {Promise} API response with tokens
 */
export const faceLogin = async (userId, faceImage) => {
  const response = await api.post('/auth/face-login', {
    user_id: userId,
    face_image: faceImage,
  });
  return response.data;
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
