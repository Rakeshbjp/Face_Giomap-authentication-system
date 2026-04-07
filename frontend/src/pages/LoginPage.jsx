/**
 * Login Page — Dual authentication flow.
 *
 * Option 1: Email + Password → then face verification.
 * Option 2: Direct face login (if user_id is known).
 *
 * Face verification is ALWAYS required before granting full access.
 * Camera availability is no longer a gate — let the camera components
 * handle their own error states with retry.
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';
import { loginWithPassword, verifyFace, faceLogin, getProfile, geocodeLocation } from '../services/authService';
import { reverseGeocodeClient } from '../utils/geocodeClient';
import FaceVerification from '../components/face/FaceVerification';
import Spinner from '../components/ui/Spinner';
import useGeolocation from '../hooks/useGeolocation';

const LoginPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated, loginSuccess, faceVerified } = useAuth();
  const { position: geoPosition, loading: geoLoading, error: geoError, permissionDenied: geoDenied, refresh: geoRefresh } = useGeolocation({ watch: false });

  // State
  const [loginMode, setLoginMode] = useState('password'); // 'password' | 'face'
  const [step, setStep] = useState('credentials'); // 'credentials' | 'face-verify'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [userId, setUserId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [locationError, setLocationError] = useState(null); // location mismatch error
  const [regAddress, setRegAddress] = useState(null); // resolved registered location address
  const [curAddress, setCurAddress] = useState(null); // resolved current location address

  // When locationError is set, extract coordinates and reverse-geocode them
  useEffect(() => {
    if (!locationError) {
      setRegAddress(null);
      setCurAddress(null);
      return;
    }

    const regMatch = locationError.match(/Registered:\s*\(([-\d.]+),\s*([-\d.]+)\)/);
    const curMatch = locationError.match(/Current:\s*\(([-\d.]+),\s*([-\d.]+)\)/);

    const resolveAddress = async (lat, lng) => {
      try {
        const res = await geocodeLocation(lat, lng);
        if (res?.data && (res.data.area || res.data.road || res.data.display_name)) return res.data;
      } catch { /* backend failed */ }
      // Fallback to client-side
      return await reverseGeocodeClient(lat, lng);
    };

    if (regMatch) {
      resolveAddress(parseFloat(regMatch[1]), parseFloat(regMatch[2])).then(setRegAddress);
    }
    if (curMatch) {
      resolveAddress(parseFloat(curMatch[1]), parseFloat(curMatch[2])).then(setCurAddress);
    }
  }, [locationError]);

  /**
   * Auto-advance to face verification if arriving from an external login (login.html).
   * Tokens are already in localStorage via AuthContext's URL-param bridge.
   */
  useEffect(() => {
    const storedUserId = localStorage.getItem('user_id');
    if (isAuthenticated && storedUserId && step === 'credentials') {
      setUserId(storedUserId);
      setStep('face-verify');
    }
  }, [isAuthenticated, step]);

  /**
   * Handle email + password login.
   */
  const handlePasswordLogin = async (e) => {
    e.preventDefault();
    const newErrors = {};

    if (!email.trim()) newErrors.email = 'Email is required';
    if (!password) newErrors.password = 'Password is required';
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setIsLoading(true);
    setErrors({});

    try {
      // Build location payload if available
      const locationData = geoPosition
        ? { latitude: geoPosition.latitude, longitude: geoPosition.longitude }
        : null;

      const result = await loginWithPassword(email.trim().toLowerCase(), password, locationData);

      // Store tokens and user_id
      loginSuccess(result);
      setUserId(result.user_id);
      setLocationError(null);

      // If user has no face data, skip face verification entirely
      if (!result.requires_face_verification) {
        try {
          localStorage.setItem('no_camera_login', 'true');
          const profile = await getProfile();
          faceVerified(profile.data);
          toast.success('Welcome back!');
          navigate('/dashboard');
        } catch {
          toast.error('Failed to load profile');
        }
        return;
      }

      toast.success('Password verified! Now verify your face.');
      setStep('face-verify');
    } catch (err) {
      // Timeout / cold-start — show a friendly wake-up message
      if (err.isTimeout || err.friendlyMessage) {
        toast.error(err.friendlyMessage || 'Server is starting up — please try again in a few seconds.');
        return;
      }

      const detail = err.response?.data?.detail || '';
      const errorMsg = Array.isArray(detail) ? detail.map(e => e.msg).join(', ') : detail || 'Login failed. Check your credentials.';

      // Detect location mismatch error
      if (typeof errorMsg === 'string' && errorMsg.toLowerCase().includes('location mismatch')) {
        setLocationError(errorMsg);
      } else if (typeof errorMsg === 'string' && errorMsg.toLowerCase().includes('location is required')) {
        setLocationError(errorMsg);
      } else {
        setLocationError(null);
        toast.error(errorMsg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle successful face verification.
   */
  const handleFaceVerified = useCallback(
    async (result) => {
      try {
        // If face-login mode, result already has tokens — store them
        if (loginMode === 'face' && result.access_token) {
          loginSuccess(result);
        }

        // Fetch user profile
        const profile = await getProfile();
        faceVerified(profile.data);
        toast.success('Welcome back!');
        navigate('/dashboard');
      } catch {
        toast.error('Failed to load profile');
      }
    },
    [loginMode, loginSuccess, faceVerified, navigate]
  );

  /**
   * Handle failed face verification.
   */
  const handleFaceFailed = useCallback(
    (msg) => {
      toast.error(msg || 'Face verification failed');
    },
    []
  );

  /**
   * Verify function passed to FaceVerification component.
   * Uses verify-face (after password login) or face-login (direct face login).
   */
  const verifyFn = useCallback(
    async (uid, image) => {
      if (loginMode === 'face') {
        const locationData = geoPosition
          ? { latitude: geoPosition.latitude, longitude: geoPosition.longitude }
          : null;
        return await faceLogin(uid, image, locationData);
      }
      return await verifyFace(uid, image);
    },
    [loginMode, geoPosition]
  );

  /**
   * Skip face verification — proceed with password-only login.
   * Only available when camera is not working.
   */
  const handleSkipFaceVerification = useCallback(async () => {
    try {
      localStorage.setItem('no_camera_login', 'true');
      const profile = await getProfile();
      faceVerified(profile.data);
      toast.success('Logged in without face verification');
      navigate('/dashboard');
    } catch {
      toast.error('Failed to load profile');
    }
  }, [faceVerified, navigate]);

  return (
    <div className="min-h-screen min-h-[100dvh] bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center px-3 py-6 sm:p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl p-4 sm:p-6 md:p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="w-14 h-14 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-3">
              <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Welcome Back</h1>
            <p className="text-gray-500 mt-1">
              {step === 'credentials' ? 'Sign in to your account' : 'Verify your identity'}
            </p>
          </div>

          {/* ─── Location Mismatch Error Popup ─── */}
          {locationError && (
            <div className="mb-6 animate-fadeIn">
              <div className="bg-red-50 border-2 border-red-300 rounded-xl p-5 sm:p-6">
                {/* Big FAIL icon */}
                <div className="text-center mb-4">
                  <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3 popup-icon-fail">
                    <svg className="w-12 h-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </div>
                  <h3 className="text-2xl font-extrabold text-red-600 mb-1">LOGIN FAILED</h3>
                  <p className="text-sm font-bold text-red-500 uppercase tracking-wide">Location Mismatch Detected</p>
                </div>

                {/* Distance info */}
                {(() => {
                  const distMatch = locationError.match(/(\d+)m away/);
                  const maxMatch = locationError.match(/Max allowed: (\d+)m/);
                  const regMatch = locationError.match(/Registered: \(([-\d.]+), ([-\d.]+)\)/);
                  const curMatch = locationError.match(/Current: \(([-\d.]+), ([-\d.]+)\)/);
                  const dist = distMatch ? distMatch[1] : null;
                  const maxDist = maxMatch ? maxMatch[1] : null;

                  return (
                    <div className="space-y-3 mb-4">
                      {/* Distance badge */}
                      {dist && (
                        <div className="bg-red-100 rounded-lg p-3 text-center">
                          <p className="text-3xl font-extrabold text-red-600">
                            {parseInt(dist) >= 1000 ? `${(parseInt(dist)/1000).toFixed(1)} km` : `${dist}m`}
                          </p>
                          <p className="text-xs text-red-500 font-medium mt-1">
                            away from registered location {maxDist && `(max ${maxDist}m allowed)`}
                          </p>
                        </div>
                      )}


                      {/* Location comparison — addresses instead of coordinates */}
                      <div className="grid grid-cols-2 gap-2">
                        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                          <p className="text-xs font-semibold text-green-600 mb-1">📍 Registered Location</p>
                          {regAddress ? (
                            <div className="text-left">
                              {regAddress.road && <p className="text-xs font-medium text-green-800">{regAddress.road}</p>}
                              <p className="text-xs text-green-700">
                                {regAddress.area || regAddress.suburb || ''}
                              </p>
                              <p className="text-xs text-green-600">
                                {[regAddress.city, regAddress.state].filter(Boolean).join(', ')}
                              </p>
                              {regAddress.pincode && (
                                <p className="text-xs text-green-500">{regAddress.pincode}</p>
                              )}
                            </div>
                          ) : regMatch ? (
                            <div className="flex items-center justify-center gap-1 text-xs text-green-500">
                              <div className="w-3 h-3 border border-green-400 border-t-transparent rounded-full animate-spin" />
                              Resolving...
                            </div>
                          ) : null}
                        </div>

                        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                          <p className="text-xs font-semibold text-red-600 mb-1">📍 Your Current Location</p>
                          {curAddress ? (
                            <div className="text-left">
                              {curAddress.road && <p className="text-xs font-medium text-red-800">{curAddress.road}</p>}
                              <p className="text-xs text-red-700">
                                {curAddress.area || curAddress.suburb || ''}
                              </p>
                              <p className="text-xs text-red-600">
                                {[curAddress.city, curAddress.state].filter(Boolean).join(', ')}
                              </p>
                              {curAddress.pincode && (
                                <p className="text-xs text-red-500">{curAddress.pincode}</p>
                              )}
                            </div>
                          ) : curMatch ? (
                            <div className="flex items-center justify-center gap-1 text-xs text-red-500">
                              <div className="w-3 h-3 border border-red-400 border-t-transparent rounded-full animate-spin" />
                              Resolving...
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  );
                })()}

                {/* Message */}
                <div className="bg-red-100/50 rounded-lg p-3 mb-4">
                  <p className="text-sm text-red-700 leading-relaxed text-center">
                    <strong>You can only login from your registered location.</strong><br />
                    To login from this new location, you must register a new account first.
                  </p>
                </div>

                {/* Actions */}
                <div className="flex flex-col gap-2">
                  <a
                    href="/register"
                    className="block text-center px-5 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm font-bold shadow-lg"
                  >
                    🔄 Register New Account from This Location
                  </a>
                  <button
                    onClick={() => setLocationError(null)}
                    className="text-sm text-red-400 hover:text-red-600 underline py-1"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ─── Credentials Step ─── */}
          {step === 'credentials' && (
            <>
              {/* Login mode toggle — always show both options */}
              <div className="flex bg-gray-100 rounded-lg p-1 mb-6">
                <button
                  className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                    loginMode === 'password'
                      ? 'bg-white shadow text-blue-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                  onClick={() => setLoginMode('password')}
                >
                  Email + Password
                </button>
                <button
                  className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                    loginMode === 'face'
                      ? 'bg-white shadow text-blue-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                  onClick={() => setLoginMode('face')}
                >
                  Face Login
                </button>
              </div>

              {loginMode === 'password' ? (
                <form onSubmit={handlePasswordLogin} className="space-y-4">
                  {/* Email */}
                  <div>
                    <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                      Email
                    </label>
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => { setEmail(e.target.value); setErrors((p) => ({ ...p, email: '' })); }}
                      placeholder="john@example.com"
                      className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors ${
                        errors.email ? 'border-red-400' : 'border-gray-300'
                      }`}
                    />
                    {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email}</p>}
                  </div>

                  {/* Password */}
                  <div>
                    <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                      Password
                    </label>
                    <input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: '' })); }}
                      placeholder="Enter your password"
                      className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors ${
                        errors.password ? 'border-red-400' : 'border-gray-300'
                      }`}
                    />
                    {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password}</p>}
                  </div>

                  {/* ── Live Location Status ── */}
                  <div className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm ${
                    geoPosition
                      ? 'bg-green-50 border-green-200 text-green-700'
                      : geoDenied
                      ? 'bg-red-50 border-red-200 text-red-600'
                      : 'bg-blue-50 border-blue-200 text-blue-600'
                  }`}>
                    {geoPosition ? (
                      <>
                        <div className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse" />
                        <span className="font-medium">📍 Location detected</span>
                        <span className="text-xs text-green-500 ml-auto font-mono">
                          {geoPosition.latitude.toFixed(4)}, {geoPosition.longitude.toFixed(4)}
                        </span>
                      </>
                    ) : geoDenied ? (
                      <>
                        <div className="w-2.5 h-2.5 bg-red-500 rounded-full" />
                        <div className="flex-1">
                          <span className="font-medium">⚠️ Location denied</span>
                          <p className="text-xs text-red-500 mt-0.5">Click 🔒 in address bar → Location → Allow, then:</p>
                        </div>
                        <button onClick={geoRefresh} className="text-xs bg-red-100 hover:bg-red-200 px-2 py-1 rounded font-medium transition-colors">Retry</button>
                      </>
                    ) : (
                      <>
                        <div className="w-2.5 h-2.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                        <span className="font-medium">Detecting location...</span>
                      </>
                    )}
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium transition-colors flex items-center justify-center"
                  >
                    {isLoading ? <Spinner size="sm" /> : 'Sign In'}
                  </button>
                </form>
              ) : (
                /* Face login mode — requires user_id or email */
                <div className="space-y-4">
                  <div>
                    <label htmlFor="userId" className="block text-sm font-medium text-gray-700 mb-1">
                      User ID or Email
                    </label>
                    <input
                      id="userId"
                      type="text"
                      value={userId}
                      onChange={(e) => setUserId(e.target.value)}
                      placeholder="Enter your email or User ID"
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                  </div>
                  <button
                    onClick={() => {
                      if (!userId.trim()) {
                        toast.error('Please enter your User ID or email');
                        return;
                      }
                      setStep('face-verify');
                    }}
                    className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
                  >
                    Continue to Face Scan
                  </button>
                </div>
              )}
            </>
          )}

          {/* ─── Face Verification Step ─── */}
          {step === 'face-verify' && (
            <FaceVerification
              userId={userId}
              onVerified={handleFaceVerified}
              onFailed={handleFaceFailed}
              onCancel={() => setStep('credentials')}
              onSkip={loginMode === 'password' ? handleSkipFaceVerification : undefined}
              verifyFn={verifyFn}
            />
          )}

          {/* Footer */}
          <div className="text-center mt-6 text-sm text-gray-500">
            Don't have an account?{' '}
            <Link to="/register" className="text-blue-600 hover:underline font-medium">
              Sign up
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
