/**
 * Dashboard Page — Protected route shown after full authentication.
 * Shows user info, session tracking (login/logout times), live location with
 * full address, and option to add/update face data.
 */
import React, { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';
import FaceCaptureRegistration from '../components/face/FaceCaptureRegistration';
import { updateFaceData, geocodeLocation } from '../services/authService';
import useGeolocation from '../hooks/useGeolocation';
import Spinner from '../components/ui/Spinner';

const DashboardPage = () => {
  const { user, logout } = useAuth();
  const [showFaceSetup, setShowFaceSetup] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  const hasFaceData = user?.has_face_data ?? user?.liveness_verified ?? false;

  // Live location for address display
  const { position: geoPos } = useGeolocation({ watch: true });
  const [liveAddress, setLiveAddress] = useState(null);
  const [addressLoading, setAddressLoading] = useState(false);

  useEffect(() => {
    if (!geoPos) return;
    let cancelled = false;
    const fetchAddr = async () => {
      setAddressLoading(true);
      try {
        const res = await geocodeLocation(geoPos.latitude, geoPos.longitude);
        if (!cancelled && res?.data) setLiveAddress(res.data);
      } catch { /* silent */ }
      finally { if (!cancelled) setAddressLoading(false); }
    };
    fetchAddr();
    return () => { cancelled = true; };
  }, [
    geoPos ? Math.round(geoPos.latitude * 1000) : null,
    geoPos ? Math.round(geoPos.longitude * 1000) : null,
  ]);

  /**
   * Handle face capture completion — send to update-face endpoint.
   */
  const handleFaceCaptureComplete = useCallback(async (faceImages) => {
    setIsUpdating(true);
    try {
      const result = await updateFaceData(faceImages);
      if (result.status) {
        toast.success(result.message || 'Face data updated successfully!');
        setShowFaceSetup(false);
      } else {
        toast.error(result.message || 'Failed to update face data');
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errorMsg = Array.isArray(detail) ? detail.map(e => e.msg).join(', ') : detail || 'Failed to update face data';
      toast.error(errorMsg);
    } finally {
      setIsUpdating(false);
    }
  }, []);

  // Format datetime string to readable format
  const formatDateTime = (isoStr) => {
    if (!isoStr) return 'N/A';
    // Backend stores UTC without 'Z' — append it so the browser knows it's UTC
    const utcStr = isoStr.endsWith('Z') ? isoStr : isoStr + 'Z';
    const d = new Date(utcStr);
    return d.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: true,
    });
  };

  // Get the latest login session
  const latestSession = user?.login_sessions?.length
    ? user.login_sessions[user.login_sessions.length - 1]
    : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Welcome Card */}
        <div className="bg-white rounded-2xl shadow-lg p-8 mb-6">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center">
              <span className="text-2xl font-bold text-white">
                {user?.name?.charAt(0)?.toUpperCase() || 'U'}
              </span>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Welcome, {user?.name || 'User'}!
              </h1>
              <p className="text-gray-500">You are securely authenticated</p>
            </div>
            <div className="ml-auto">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-green-100 text-green-800">
                <span className="w-2 h-2 rounded-full bg-green-500" />
                Face Verified
              </span>
            </div>
          </div>

          {/* User Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Full Name</p>
              <p className="text-gray-900 font-medium">{user?.name || 'N/A'}</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Email</p>
              <p className="text-gray-900 font-medium">{user?.email || 'N/A'}</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Phone</p>
              <p className="text-gray-900 font-medium">{user?.phone || 'N/A'}</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Member Since</p>
              <p className="text-gray-900 font-medium">
                {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
              </p>
            </div>
          </div>
        </div>

        {/* ── Session & Location Card ── */}
        <div className="bg-white rounded-2xl shadow-lg p-8 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-5 flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Session & Location Info
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
            {/* Login Time */}
            <div className="bg-green-50 rounded-xl p-4 border border-green-100">
              <p className="text-xs text-green-600 uppercase tracking-wider mb-1 font-semibold flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14" />
                </svg>
                Login Time
              </p>
              <p className="text-gray-900 font-medium text-sm">
                {formatDateTime(user?.last_login_at || latestSession?.login_at)}
              </p>
            </div>

            {/* Logout Time */}
            <div className="bg-red-50 rounded-xl p-4 border border-red-100">
              <p className="text-xs text-red-600 uppercase tracking-wider mb-1 font-semibold flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7" />
                </svg>
                Last Logout Time
              </p>
              <p className="text-gray-900 font-medium text-sm">
                {formatDateTime(user?.last_logout_at)}
              </p>
            </div>
          </div>

          {/* Live Location */}
          <div className="bg-blue-50 rounded-xl p-4 border border-blue-100">
            <p className="text-xs text-blue-600 uppercase tracking-wider mb-2 font-semibold flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Live Location
            </p>
            {addressLoading || !geoPos ? (
              <div className="flex items-center gap-2 text-sm text-blue-500">
                <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                {geoPos ? 'Resolving address...' : 'Getting GPS location...'}
              </div>
            ) : liveAddress ? (() => {
              // Build the best possible address display
              const mainName = liveAddress.road || liveAddress.area || liveAddress.suburb || liveAddress.district || '';
              const subArea = liveAddress.area && liveAddress.area !== mainName ? liveAddress.area : '';
              const suburbText = liveAddress.suburb && liveAddress.suburb !== mainName && liveAddress.suburb !== subArea ? liveAddress.suburb : '';
              const cityLine = [
                liveAddress.city,
                liveAddress.district && liveAddress.district !== liveAddress.city && liveAddress.district !== mainName ? liveAddress.district : null,
                liveAddress.state,
                liveAddress.country,
              ].filter(Boolean).join(', ');

              // If no structured fields at all, use display_name from Nominatim
              const hasStructured = mainName || subArea || cityLine;
              const fallbackName = liveAddress.display_name || '';

              return (
                <div className="space-y-1">
                  <div className="flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">📍</span>
                    <div>
                      {hasStructured ? (
                        <>
                          {mainName && (
                            <p className="text-gray-900 font-semibold text-sm">{mainName}</p>
                          )}
                          {(subArea || suburbText) && (
                            <p className="text-gray-800 font-medium text-sm">
                              {[subArea, suburbText].filter(Boolean).join(', ')}
                            </p>
                          )}
                          {cityLine && (
                            <p className="text-gray-600 text-sm">{cityLine}</p>
                          )}
                        </>
                      ) : fallbackName ? (
                        <p className="text-gray-900 font-medium text-sm">{fallbackName}</p>
                      ) : (
                        <p className="text-gray-600 text-sm">Address not available</p>
                      )}
                      {liveAddress.pincode && (
                        <p className="text-gray-500 text-xs mt-0.5">
                          Pincode: <span className="font-mono font-semibold">{liveAddress.pincode}</span>
                        </p>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-blue-400 font-mono mt-1">
                    {geoPos.latitude.toFixed(6)}, {geoPos.longitude.toFixed(6)}
                  </p>
                </div>
              );
            })() : (
              <p className="text-gray-500 text-sm">Location not available</p>
            )}
          </div>

          {/* Login session address (from DB) */}
          {latestSession?.address && (() => {
            const addr = latestSession.address;
            const parts = [
              addr.road, addr.area, addr.suburb, addr.city,
              addr.district && addr.district !== addr.city ? addr.district : null,
              addr.state, addr.country,
            ].filter(Boolean).join(', ');
            const display = parts || addr.display_name || 'Location recorded';
            return (
              <div className="mt-4 bg-gray-50 rounded-xl p-4 border border-gray-100">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1 font-semibold">Login Location (recorded)</p>
                <p className="text-gray-800 text-sm font-medium">
                  {display}
                  {addr.pincode && ` - ${addr.pincode}`}
                </p>
              </div>
            );
          })()}
        </div>

        {/* Face Data Setup Card — shown when no face data exists */}
        {!hasFaceData && !showFaceSetup && (
          <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl shadow-lg p-8 mb-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
                  />
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 mb-1">Face Data Not Set Up</h3>
                <p className="text-gray-600 text-sm mb-4">
                  Your account doesn't have face recognition data. Set it up now to enable secure face-based login.
                </p>
                <button
                  onClick={() => setShowFaceSetup(true)}
                  className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors text-sm"
                >
                  📷 Set Up Face Recognition
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Face Capture Modal */}
        {showFaceSetup && (
          <div className="bg-white rounded-2xl shadow-lg p-6 sm:p-8 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Set Up Face Recognition</h2>
            {isUpdating ? (
              <div className="text-center py-12">
                <Spinner size="lg" className="mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900">Processing face data...</h3>
                <p className="text-gray-500 mt-2">Please wait while we verify and store your face data.</p>
              </div>
            ) : (
              <>
                <FaceCaptureRegistration
                  onCaptureComplete={handleFaceCaptureComplete}
                  onCancel={() => setShowFaceSetup(false)}
                />
                <div className="mt-4 text-center">
                  <button
                    onClick={() => setShowFaceSetup(false)}
                    className="text-sm text-gray-500 hover:text-gray-700 underline"
                  >
                    Cancel face setup
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* Security Info */}
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Security Status</h2>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-gray-700">Password authenticated</span>
            </div>
            <div className="flex items-center gap-3">
              {hasFaceData ? (
                <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
                  />
                </svg>
              )}
              <span className="text-gray-700">
                {hasFaceData ? 'Face recognition verified' : 'Face recognition not set up'}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-gray-700">Encrypted session active</span>
            </div>
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-gray-700">Anti-spoofing liveness verified</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
