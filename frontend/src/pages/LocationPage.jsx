/**
 * LocationPage — Full-screen live location map with real-time GPS tracking.
 *
 * Shows the user's current position on an interactive OpenStreetMap.
 * If the user is logged in and has a registered location, it also shows
 * that location, the distance between them, and area names via reverse geocoding.
 */
import React, { useMemo, useState, useEffect } from 'react';
import useGeolocation from '../hooks/useGeolocation';
import LocationMap from '../components/map/LocationMap';
import { useAuth } from '../context/AuthContext';
import { geocodeLocation } from '../services/authService';

/**
 * Haversine distance in metres.
 */
function haversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6_371_000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const LocationPage = () => {
  const { position, error, loading, permissionDenied, refresh } = useGeolocation({ watch: true });
  const { user } = useAuth();

  const registeredLocation = user?.registered_location || null;
  const registeredAddress = user?.registered_address || null;

  // Reverse-geocoded address for current live location
  const [currentAddress, setCurrentAddress] = useState(null);
  const [addressLoading, setAddressLoading] = useState(false);

  // Fetch address when position changes significantly
  useEffect(() => {
    if (!position) return;
    let cancelled = false;
    const fetchAddress = async () => {
      setAddressLoading(true);
      try {
        const result = await geocodeLocation(position.latitude, position.longitude);
        if (!cancelled && result?.data) {
          setCurrentAddress(result.data);
        }
      } catch {
        // fallback silently
      } finally {
        if (!cancelled) setAddressLoading(false);
      }
    };
    fetchAddress();
    return () => { cancelled = true; };
  }, [
    // Only re-fetch when position changes by ~0.001° (~100m)
    position ? Math.round(position.latitude * 1000) : null,
    position ? Math.round(position.longitude * 1000) : null,
  ]);

  const distance = useMemo(() => {
    if (!position || !registeredLocation) return null;
    return haversineDistance(
      position.latitude,
      position.longitude,
      registeredLocation.latitude,
      registeredLocation.longitude
    );
  }, [position, registeredLocation]);

  const isWithinRange = distance !== null ? distance <= 100 : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900">
      {/* Header */}
      <div className="bg-black/20 backdrop-blur-sm border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2">
              <svg className="w-5 h-5 sm:w-7 sm:h-7 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Live Location
            </h1>
            <p className="text-xs sm:text-sm text-blue-300 mt-0.5">Real-time GPS tracking • OpenStreetMap</p>
          </div>
          <button
            onClick={refresh}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium flex items-center gap-2"
          >
            <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
        {/* ── Permission Denied Banner ── */}
        {permissionDenied && (
          <div className="mb-6 bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-5">
            <div className="flex items-start gap-3">
              <div className="text-yellow-400 text-2xl mt-0.5">⚠️</div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-yellow-300 mb-2">Location Permission Required</h3>
                <p className="text-yellow-200/80 text-sm mb-3">
                  You denied location access. To use the live map and location-based login, please enable it:
                </p>
                <div className="bg-black/20 rounded-lg p-4 mb-3">
                  <p className="text-yellow-100 text-sm font-medium mb-2">How to enable location:</p>
                  <ol className="text-yellow-200/70 text-sm space-y-1 list-decimal list-inside">
                    <li>Click the <strong>🔒 lock icon</strong> (or ⓘ icon) in your browser's address bar</li>
                    <li>Find <strong>"Location"</strong> and change it to <strong>"Allow"</strong></li>
                    <li>Reload this page or click <strong>"Try Again"</strong> below</li>
                  </ol>
                </div>
                <button
                  onClick={refresh}
                  className="px-5 py-2 bg-yellow-500 text-black rounded-lg hover:bg-yellow-400 transition-colors text-sm font-semibold"
                >
                  Try Again
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Info cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mb-4 sm:mb-6">
          {/* Current location */}
          <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/10">
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-3 h-3 rounded-full ${position ? 'bg-blue-500 animate-pulse' : error ? 'bg-red-500' : 'bg-gray-400 animate-pulse'}`} />
              <span className="text-sm font-medium text-blue-300">Current Location</span>
            </div>
            {loading && !position && !error ? (
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                <p className="text-white/60 text-sm">Getting location...</p>
              </div>
            ) : error && !position ? (
              <div>
                <p className="text-red-400 text-sm mb-2">{error}</p>
                <button onClick={refresh} className="text-xs text-blue-400 hover:text-blue-300 underline">
                  Retry
                </button>
              </div>
            ) : position ? (
              <div className="text-white">
                <p className="text-sm sm:text-lg font-mono font-bold">{position.latitude.toFixed(6)}</p>
                <p className="text-sm sm:text-lg font-mono font-bold">{position.longitude.toFixed(6)}</p>
                {position.accuracy && (
                  <p className="text-xs text-white/50 mt-1">Accuracy: ±{position.accuracy.toFixed(0)}m</p>
                )}
                {/* Area name */}
                {addressLoading ? (
                  <p className="text-xs text-blue-300 mt-2 flex items-center gap-1">
                    <span className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin inline-block" />
                    Detecting area...
                  </p>
                ) : currentAddress?.area ? (
                  <div className="mt-2 pt-2 border-t border-white/10">
                    <p className="text-sm text-blue-300 font-medium">📍 {currentAddress.area}</p>
                    <p className="text-xs text-white/50">
                      {[currentAddress.city, currentAddress.state].filter(Boolean).join(', ')}
                    </p>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          {/* Registered location */}
          <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/10">
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-3 h-3 rounded-full ${registeredLocation ? 'bg-green-500' : 'bg-gray-400'}`} />
              <span className="text-sm font-medium text-green-300">Registered Location</span>
            </div>
            {registeredLocation ? (
              <div className="text-white">
                <p className="text-sm sm:text-lg font-mono font-bold">{registeredLocation.latitude.toFixed(6)}</p>
                <p className="text-sm sm:text-lg font-mono font-bold">{registeredLocation.longitude.toFixed(6)}</p>
                <p className="text-xs text-white/50 mt-1">Login locked to this area (100m radius)</p>
                {/* Registered area name */}
                {registeredAddress?.area ? (
                  <div className="mt-2 pt-2 border-t border-white/10">
                    <p className="text-sm text-green-300 font-medium">📍 {registeredAddress.area}</p>
                    <p className="text-xs text-white/50">
                      {[registeredAddress.city, registeredAddress.state, registeredAddress.pincode].filter(Boolean).join(', ')}
                    </p>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="text-white/60 text-sm">No registered location yet. Register a new account to lock your location.</p>
            )}
          </div>

          {/* Distance / Status */}
          <div className={`backdrop-blur-md rounded-xl p-4 border ${
            isWithinRange === null
              ? 'bg-white/10 border-white/10'
              : isWithinRange
              ? 'bg-green-500/10 border-green-500/20'
              : 'bg-red-500/10 border-red-500/20'
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-3 h-3 rounded-full ${
                isWithinRange === null ? 'bg-gray-400' : isWithinRange ? 'bg-green-500' : 'bg-red-500'
              }`} />
              <span className={`text-sm font-medium ${
                isWithinRange === null ? 'text-gray-300' : isWithinRange ? 'text-green-300' : 'text-red-300'
              }`}>Login Status</span>
            </div>
            {distance !== null ? (
              <div>
                <p className={`text-2xl font-bold ${isWithinRange ? 'text-green-400' : 'text-red-400'}`}>
                  {distance < 1000 ? `${distance.toFixed(0)}m` : `${(distance / 1000).toFixed(2)}km`}
                </p>
                <p className={`text-sm mt-1 ${isWithinRange ? 'text-green-300' : 'text-red-300'}`}>
                  {isWithinRange ? '✓ Within login range' : '✗ Outside login range (max 100m)'}
                </p>
              </div>
            ) : (
              <p className="text-white/60 text-sm">
                {permissionDenied
                  ? 'Enable location to check login eligibility'
                  : !position
                  ? 'Waiting for location...'
                  : 'No registered location to compare'}
              </p>
            )}
          </div>
        </div>

        {/* Map or error */}
        {!position && (error || permissionDenied) ? (
          <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 text-center border border-white/10">
            <div className="text-6xl mb-4">{permissionDenied ? '📍' : '🗺️'}</div>
            <h3 className="text-lg font-semibold text-white mb-2">
              {permissionDenied ? 'Location Access Needed' : 'Location Unavailable'}
            </h3>
            <p className="text-white/60 mb-4 max-w-md mx-auto">
              {permissionDenied
                ? 'Allow location access to see your position on the map. Check the banner above for instructions.'
                : error}
            </p>
            <button
              onClick={refresh}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Try Again
            </button>
          </div>
        ) : (
          <LocationMap
            position={position}
            registeredLocation={registeredLocation}
            showAccuracy={true}
            followUser={true}
            height={typeof window !== 'undefined' && window.innerWidth < 640 ? 300 : 500}
            className="border border-white/10"
          />
        )}

        {/* Info footer */}
        <div className="mt-4 text-center text-sm text-white/40">
          <p>
            Location data is used for authentication security only.
            You can only login from within 100m of your registered location.
          </p>
        </div>
      </div>
    </div>
  );
};

export default LocationPage;
