/**
 * FaceVerification — Real-time continuous face verification for login.
 *
 * Shows a live camera feed and continuously captures frames every few seconds
 * to verify the user's face against stored embeddings.
 *
 * Behavior:
 * - Automatically captures frames at regular intervals (every 3s)
 * - Shows a live TRUE/FALSE popup overlay with confidence score
 * - If face is obstructed or objects cover it → shows FALSE with reason
 * - If face matches → shows TRUE with "Face Verified!" and auto-proceeds
 * - If face doesn't match → shows FALSE with "Face Not Recognized"
 * - User can also click "Verify Now" for an immediate manual check
 */
import React, { useState, useCallback, useEffect, useRef } from 'react';
import useCamera from '../../hooks/useCamera';
import Spinner from '../ui/Spinner';

const SCAN_INTERVAL_MS = 3000; // Auto-scan every 3 seconds

const FaceVerification = ({ userId, onVerified, onFailed, onCancel, onSkip, verifyFn }) => {
  const { videoRef, isActive, error, startCamera, stopCamera, captureImage } = useCamera({ autoStart: true });
  const [status, setStatus] = useState('idle'); // idle | scanning | verified | failed
  const [message, setMessage] = useState('');
  const [confidence, setConfidence] = useState(null);
  const [showPopup, setShowPopup] = useState(false);
  const [autoScanEnabled, setAutoScanEnabled] = useState(true);
  const [scanCount, setScanCount] = useState(0);
  const popupTimer = useRef(null);
  const scanIntervalRef = useRef(null);
  const isScanningRef = useRef(false);
  const mountedRef = useRef(true);

  // Cleanup timers on unmount (camera lifecycle handled by useCamera with autoStart)
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (popupTimer.current) clearTimeout(popupTimer.current);
      if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
    };
  }, []);

  /**
   * Core verify logic — captures a frame and sends for verification.
   * Returns the result for the caller to act upon.
   */
  const doVerify = useCallback(async () => {
    if (!isActive || isScanningRef.current) return null;

    const image = captureImage();
    if (!image) {
      return { success: false, message: 'Could not capture image', confidence: null };
    }

    isScanningRef.current = true;
    setStatus('scanning');
    setShowPopup(false);

    try {
      const result = await verifyFn(userId, image);

      if (!mountedRef.current) return null;

      if (result.status) {
        setStatus('verified');
        setMessage('Face Verified!');
        setConfidence(result.confidence);
        setShowPopup(true);
        setScanCount((c) => c + 1);
        isScanningRef.current = false;
        return { success: true, result };
      } else {
        setStatus('failed');
        setMessage(result.message || 'Face Not Recognized');
        setConfidence(result.confidence ?? null);
        setShowPopup(true);
        setScanCount((c) => c + 1);
        isScanningRef.current = false;
        return { success: false, message: result.message };
      }
    } catch (err) {
      if (!mountedRef.current) return null;

      setStatus('failed');
      const raw = err.response?.data?.detail;
      const detail = Array.isArray(raw) ? raw.map((e) => e.msg).join(', ') : raw || 'Verification failed';
      setMessage(detail);
      setShowPopup(true);
      setScanCount((c) => c + 1);
      isScanningRef.current = false;
      return { success: false, message: detail };
    }
  }, [isActive, captureImage, userId, verifyFn]);

  /**
   * Auto-scan: Capture and verify at regular intervals.
   */
  useEffect(() => {
    if (!isActive || !autoScanEnabled) return;

    // Start scanning immediately after camera is active
    const startAutoScan = () => {
      // Initial delay to let the user position their face
      const initialDelay = setTimeout(() => {
        if (!mountedRef.current) return;
        doVerify().then((result) => {
          if (result?.success) {
            // Stop auto-scan on success
            setAutoScanEnabled(false);
            // Notify parent after showing success popup
            popupTimer.current = setTimeout(() => {
              onVerified && onVerified(result.result);
            }, 1500);
          }
        });
      }, 1500);

      // Then continue at intervals
      scanIntervalRef.current = setInterval(() => {
        if (!mountedRef.current || isScanningRef.current) return;
        doVerify().then((result) => {
          if (result?.success) {
            setAutoScanEnabled(false);
            if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
            popupTimer.current = setTimeout(() => {
              onVerified && onVerified(result.result);
            }, 1500);
          } else {
            // On failure, briefly show popup then auto-dismiss for next scan
            setTimeout(() => {
              if (mountedRef.current) {
                setShowPopup(false);
                setStatus('idle');
              }
            }, 2000);
          }
        });
      }, SCAN_INTERVAL_MS);

      return () => {
        clearTimeout(initialDelay);
        if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
      };
    };

    const cleanup = startAutoScan();
    return cleanup;
  }, [isActive, autoScanEnabled, doVerify, onVerified]);

  /**
   * Manual verify — user clicks "Verify Now"
   */
  const handleManualVerify = useCallback(async () => {
    const result = await doVerify();
    if (result?.success) {
      setAutoScanEnabled(false);
      if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
      popupTimer.current = setTimeout(() => {
        onVerified && onVerified(result.result);
      }, 1500);
    }
  }, [doVerify, onVerified]);

  /**
   * Dismiss the result popup and reset to idle.
   */
  const dismissPopup = useCallback(() => {
    setShowPopup(false);
    if (status === 'failed') {
      setStatus('idle');
      setMessage('');
      setConfidence(null);
    }
  }, [status]);

  // ── Camera error state ──
  if (error) {
    return (
      <div className="text-center p-8">
        <div className="text-red-500 mb-4">
          <svg className="w-16 h-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Camera Unavailable</h3>
        <p className="text-gray-600 mb-4">{error}</p>
        <div className="flex gap-3 justify-center mb-4">
          <button onClick={startCamera} className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            Retry Camera
          </button>
          {onCancel && (
            <button onClick={onCancel} className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
              Cancel
            </button>
          )}
        </div>

        {/* Skip face verification fallback */}
        {onSkip && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-500 mb-3">
              No camera available? You can continue with password-only login.
            </p>
            <button
              onClick={onSkip}
              className="px-6 py-2.5 bg-gray-700 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm font-medium"
            >
              Continue without camera →
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="text-center mb-4">
        <h3 className="text-xl font-semibold text-gray-900">Real-Time Face Verification</h3>
        <p className="text-sm text-gray-500 mt-1">
          Look directly at the camera — verification runs automatically
        </p>
      </div>

      {/* ── Live camera feed ── */}
      <div className="relative bg-black rounded-2xl overflow-hidden mb-4">
        <video ref={videoRef} autoPlay playsInline muted className="w-full rounded-2xl" style={{ transform: 'scaleX(-1)' }} />

        {/* Oval face guide */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div
            className={`w-56 h-72 rounded-full border-[3px] transition-all duration-500 ${
              status === 'verified'
                ? 'border-green-400 shadow-[0_0_30px_rgba(34,197,94,0.5)]'
                : status === 'failed'
                ? 'border-red-400 shadow-[0_0_30px_rgba(239,68,68,0.4)]'
                : status === 'scanning'
                ? 'border-blue-400 border-dashed animate-pulse'
                : 'border-blue-400 border-dashed'
            }`}
          />
        </div>

        {/* Scanning animation — sweep line */}
        {status === 'scanning' && (
          <div className="absolute inset-0 pointer-events-none">
            <div className="scan-line-realtime" />
          </div>
        )}

        {/* ── Result popup overlay ── */}
        {showPopup && (
          <div
            className={`absolute inset-0 flex flex-col items-center justify-center transition-all duration-300 ${
              status === 'verified' ? 'bg-green-500/20 backdrop-blur-sm' : 'bg-red-500/20 backdrop-blur-sm'
            }`}
            onClick={status === 'failed' ? dismissPopup : undefined}
            style={{ animation: 'fadeIn 0.3s ease-out' }}
          >
            {status === 'verified' ? (
              <>
                <div className="popup-icon-success">
                  <svg className="w-20 h-20 text-green-500 drop-shadow-lg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="mt-3 bg-white/95 px-6 py-3 rounded-xl shadow-lg text-center" style={{ animation: 'slideUp 0.3s ease-out' }}>
                  <p className="text-2xl font-extrabold text-green-600 mb-1">✓ TRUE</p>
                  <p className="text-sm font-bold text-green-700">Face Verified!</p>
                  {confidence !== null && (
                    <p className="text-xs text-green-600 mt-1">Confidence: {(confidence * 100).toFixed(1)}%</p>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="popup-icon-fail">
                  <svg className="w-20 h-20 text-red-500 drop-shadow-lg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="mt-3 bg-white/95 px-5 py-3 rounded-xl shadow-lg max-w-xs text-center" style={{ animation: 'slideUp 0.3s ease-out' }}>
                  <p className="text-2xl font-extrabold text-red-600 mb-1">✗ FALSE</p>
                  <p className="text-sm font-medium text-red-700 leading-snug">
                    {message || 'Face Not Recognized'}
                  </p>
                  {confidence !== null && (
                    <p className="text-xs text-red-500 mt-1">Confidence: {(confidence * 100).toFixed(1)}%</p>
                  )}
                </div>
                {!autoScanEnabled && (
                  <button
                    onClick={dismissPopup}
                    className="mt-3 text-sm text-gray-600 bg-white px-4 py-1.5 rounded-lg shadow hover:bg-gray-50"
                  >
                    Tap to retry
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Live status indicator ── */}
      <div className="text-center mb-4">
        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-medium transition-all duration-300 ${
          status === 'scanning'
            ? 'bg-blue-100 text-blue-700 border-blue-300'
            : status === 'verified'
            ? 'bg-green-100 text-green-700 border-green-300'
            : status === 'failed'
            ? 'bg-red-100 text-red-700 border-red-300'
            : 'bg-gray-100 text-gray-600 border-gray-300'
        }`}>
          {status === 'scanning' ? (
            <>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              <span>Scanning face...</span>
            </>
          ) : status === 'verified' ? (
            <>
              <div className="w-2 h-2 bg-green-500 rounded-full" />
              <span>Face matched — redirecting...</span>
            </>
          ) : status === 'failed' ? (
            <>
              <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              <span>No match — keep looking at camera</span>
            </>
          ) : (
            <>
              <div className="w-2 h-2 bg-gray-400 rounded-full live-indicator" />
              <span>Position your face in the oval</span>
            </>
          )}
        </div>
        {scanCount > 0 && (
          <p className="text-xs text-gray-400 mt-2">
            Scans performed: {scanCount}
          </p>
        )}
      </div>

      {/* ── Action buttons ── */}
      <div className="flex gap-3 justify-center">
        {onCancel && (
          <button
            onClick={onCancel}
            className="px-6 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        )}
        <button
          onClick={handleManualVerify}
          disabled={!isActive || status === 'scanning' || status === 'verified'}
          className="px-8 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
        >
          {status === 'scanning' ? (
            <span className="flex items-center gap-2">
              <Spinner size="sm" /> Verifying...
            </span>
          ) : (
            'Verify Now'
          )}
        </button>
      </div>

      {/* Auto-scan toggle */}
      <div className="flex items-center justify-center mt-3">
        <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={autoScanEnabled}
            onChange={(e) => setAutoScanEnabled(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          Auto-scan enabled
        </label>
      </div>
    </div>
  );
};

export default FaceVerification;
