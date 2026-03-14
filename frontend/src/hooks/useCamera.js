/**
 * Custom hook for managing webcam access and face capture.
 *
 * Handles the common pitfalls on Windows + Chrome:
 * - React.StrictMode double-mount (open → close → re-open causes timeout)
 * - Camera driver needing time to release between sessions
 * - Multiple rapid getUserMedia calls locking the hardware
 *
 * Strategy: Single getUserMedia call with simple constraints, proper
 * cleanup sequencing, and a short hardware-release delay before retries.
 */
import { useState, useCallback, useRef, useEffect } from 'react';

// Global mutex: prevents multiple hook instances from fighting over the camera.
// Only one getUserMedia call can be in-flight at a time.
let _cameraLock = false;
let _lockQueue = [];

function acquireLock() {
  return new Promise((resolve) => {
    if (!_cameraLock) {
      _cameraLock = true;
      resolve();
    } else {
      _lockQueue.push(resolve);
    }
  });
}

function releaseLock() {
  if (_lockQueue.length > 0) {
    const next = _lockQueue.shift();
    next();
  } else {
    _cameraLock = false;
  }
}

/**
 * Small helper — wait for `ms` milliseconds.
 */
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const useCamera = ({ autoStart = false, facingMode = 'user' } = {}) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const mountedRef = useRef(true);
  const startingRef = useRef(false); // prevent concurrent startCamera calls

  const [isActive, setIsActive] = useState(false);
  const [error, setError] = useState(null);
  const [hasPermission, setHasPermission] = useState(null);

  /**
   * Fully release the current camera stream and detach from the video element.
   */
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        track.stop();
      });
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }
    setIsActive(false);
  }, []);

  /**
   * Start the camera stream.
   *
   * Uses simple constraints for maximum compatibility.
   * Acquires a global lock so only one getUserMedia call runs at a time,
   * and adds a short delay after cleanup to let the camera driver release.
   */
  const startCamera = useCallback(async () => {
    // Prevent overlapping calls
    if (startingRef.current) return;
    startingRef.current = true;

    try {
      setError(null);

      // Acquire the global camera lock
      await acquireLock();

      // Release any previous stream
      stopCamera();

      // Give the camera driver time to fully release (critical on Windows)
      await wait(300);

      if (!mountedRef.current) {
        releaseLock();
        startingRef.current = false;
        return;
      }

      // Use the simplest constraints that work across all devices
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode },
        audio: false,
      });

      // Component might have unmounted during the async call
      if (!mountedRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        releaseLock();
        startingRef.current = false;
        return;
      }

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        try {
          await videoRef.current.play();
        } catch (playErr) {
          if (playErr.name === 'AbortError') {
            // play() was interrupted by a stop — expected in StrictMode
            releaseLock();
            startingRef.current = false;
            return;
          }
          throw playErr;
        }
      }

      if (mountedRef.current) {
        setIsActive(true);
        setHasPermission(true);
      }

      releaseLock();
      startingRef.current = false;
    } catch (err) {
      releaseLock();
      startingRef.current = false;

      if (!mountedRef.current) return;

      setIsActive(false);

      if (err.name === 'NotAllowedError') {
        setHasPermission(false);
        setError(
          'Camera permission denied. Please allow camera access in your browser settings and reload the page.'
        );
      } else if (err.name === 'NotFoundError') {
        setHasPermission(false);
        setError('No camera found. Please connect a camera and try again.');
      } else if (err.name === 'NotReadableError') {
        // "Timeout starting video source" falls here
        setHasPermission(true); // permission was granted, hardware issue
        setError(
          'Camera is busy. Close any other app using it (Zoom, Teams, etc.), then click Try Again.'
        );
      } else if (err.name === 'OverconstrainedError') {
        setHasPermission(true);
        setError('Camera does not support the requested settings. Try Again.');
      } else {
        setHasPermission(false);
        setError(`Camera error: ${err.message}`);
      }
    }
  }, [facingMode, stopCamera]);

  /**
   * Capture a frame from the video feed as a base64-encoded JPEG image.
   */
  const captureImage = useCallback(() => {
    if (!videoRef.current || !isActive) return null;

    const video = videoRef.current;
    const canvas = canvasRef.current || document.createElement('canvas');

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const ctx = canvas.getContext('2d');
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    return canvas.toDataURL('image/jpeg', 0.8);
  }, [isActive]);

  /**
   * Mount / unmount lifecycle.
   *
   * Uses a debounce timer so React.StrictMode's rapid unmount→remount
   * doesn't cause two competing getUserMedia calls.
   */
  useEffect(() => {
    mountedRef.current = true;

    // Delay the initial camera start to survive StrictMode double-mount.
    // In dev, React unmounts then remounts — the first mount's start gets
    // canceled by the cleanup, and only the second mount's timer fires.
    let timer;
    if (autoStart) {
      timer = setTimeout(() => {
        if (mountedRef.current) {
          startCamera();
        }
      }, 100);
    }

    return () => {
      mountedRef.current = false;
      if (timer) clearTimeout(timer);
      stopCamera();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    videoRef,
    canvasRef,
    isActive,
    error,
    hasPermission,
    startCamera,
    stopCamera,
    captureImage,
  };
};

export default useCamera;
