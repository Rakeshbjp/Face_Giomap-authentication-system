/**
 * Custom hook to detect whether the device has a camera.
 *
 * IMPORTANT: Does NOT call getUserMedia to probe — that would lock the camera
 * and cause "Timeout starting video source" on the next component that tries
 * to use it.  Instead, relies solely on enumerateDevices().
 *
 * If enumerateDevices returns no videoinput before permission is granted,
 * we optimistically assume a camera *might* exist (hasCamera = true) and
 * let the actual camera component handle the error if it turns out there
 * isn't one.
 */
import { useState, useEffect } from 'react';

const useHasCamera = () => {
  const [hasCamera, setHasCamera] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const detect = async () => {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
          if (!cancelled) {
            setHasCamera(false);
            setChecking(false);
          }
          return;
        }

        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoInputs = devices.filter((d) => d.kind === 'videoinput');

        if (!cancelled) {
          if (videoInputs.length > 0) {
            // Definitely has a camera
            setHasCamera(true);
          } else {
            // No videoinput found — but this can happen before permission is
            // granted in some browsers.  Assume camera exists and let the
            // actual camera component surface the real error.
            setHasCamera(true);
          }
          setChecking(false);
        }
      } catch {
        if (!cancelled) {
          // Assume camera exists — let the real camera component decide
          setHasCamera(true);
          setChecking(false);
        }
      }
    };

    detect();

    return () => {
      cancelled = true;
    };
  }, []);

  return { hasCamera, checking };
};

export default useHasCamera;
