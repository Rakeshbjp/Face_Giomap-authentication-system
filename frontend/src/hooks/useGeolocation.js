/**
 * Custom hook for real-time GPS location tracking.
 *
 * Uses the browser's Geolocation API with watchPosition for continuous updates.
 * Includes retry logic and clear permission-denied handling.
 */
import { useState, useEffect, useRef, useCallback } from 'react';

const useGeolocation = ({ enableHighAccuracy = true, watch = true } = {}) => {
  const [position, setPosition] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const watchIdRef = useRef(null);

  const options = {
    enableHighAccuracy,
    timeout: 15000,
    maximumAge: watch ? 5000 : 60000,
  };

  const handleSuccess = useCallback((pos) => {
    setPosition({
      latitude: pos.coords.latitude,
      longitude: pos.coords.longitude,
      accuracy: pos.coords.accuracy,
      altitude: pos.coords.altitude,
      speed: pos.coords.speed,
      heading: pos.coords.heading,
      timestamp: pos.timestamp,
    });
    setError(null);
    setPermissionDenied(false);
    setLoading(false);
  }, []);

  const handleError = useCallback((err) => {
    let message;
    switch (err.code) {
      case 1: // PERMISSION_DENIED
        message = 'Location permission denied.';
        setPermissionDenied(true);
        break;
      case 2: // POSITION_UNAVAILABLE
        message = 'Location unavailable. Make sure GPS/Location Services are enabled.';
        break;
      case 3: // TIMEOUT
        message = 'Location request timed out. Please try again.';
        break;
      default:
        message = `Location error: ${err.message}`;
    }
    setError(message);
    setLoading(false);
  }, []);

  const startWatching = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by this browser.');
      setLoading(false);
      return;
    }

    // Clear any old watch
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }

    setLoading(true);
    setError(null);

    if (watch) {
      watchIdRef.current = navigator.geolocation.watchPosition(
        handleSuccess,
        handleError,
        options
      );
    } else {
      navigator.geolocation.getCurrentPosition(handleSuccess, handleError, options);
    }
  }, [watch, handleSuccess, handleError]);

  useEffect(() => {
    startWatching();

    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Manually refresh / retry the position.
   * If permission was denied, this will re-trigger the browser prompt
   * (some browsers only re-prompt after the user resets site permissions).
   */
  const refresh = useCallback(() => {
    setPermissionDenied(false);
    startWatching();
  }, [startWatching]);

  return { position, error, loading, permissionDenied, refresh };
};

export default useGeolocation;
