/**
 * FaceCaptureRegistration — Multi-directional face capture for user registration.
 *
 * Guides the user through capturing their face from 4 directions:
 * Front, Left, Right, and Up/Down.
 * Returns 4 base64 images to the parent component.
 */
import React, { useState, useCallback, useEffect, useRef } from 'react';
import useCamera from '../../hooks/useCamera';
import StatusBadge from '../ui/StatusBadge';

const DIRECTIONS = [
  { id: 'front', label: 'Look Straight Ahead', icon: '😐', instruction: 'Position your face in the center of the frame and look directly at the camera.' },
  { id: 'left', label: 'Turn Left', icon: '👈', instruction: 'Slowly turn your head to the LEFT. Keep your face visible.' },
  { id: 'right', label: 'Turn Right', icon: '👉', instruction: 'Slowly turn your head to the RIGHT. Keep your face visible.' },
  { id: 'updown', label: 'Look Up then Down', icon: '👆', instruction: 'Slowly tilt your head UP, then bring it back DOWN.' },
];

const FaceCaptureRegistration = ({ onCaptureComplete, onCancel }) => {
  const { videoRef, isActive, error, startCamera, stopCamera, captureImage } = useCamera({ autoStart: true });
  const [currentStep, setCurrentStep] = useState(0);
  const [capturedImages, setCapturedImages] = useState([]);
  const [countdown, setCountdown] = useState(null);
  const [status, setStatus] = useState('idle');
  const [retryCount, setRetryCount] = useState(0);

  // Refs to always read the latest values inside async callbacks
  const currentStepRef = useRef(currentStep);
  const capturedImagesRef = useRef(capturedImages);
  const timerRef = useRef(null);

  useEffect(() => { currentStepRef.current = currentStep; }, [currentStep]);
  useEffect(() => { capturedImagesRef.current = capturedImages; }, [capturedImages]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  /**
   * Retry camera access with a delay so the camera driver can release.
   */
  const handleRetryCamera = useCallback(async () => {
    setRetryCount((c) => c + 1);
    // Stop first, wait, then start — gives the hardware time to release
    stopCamera();
    await new Promise((r) => setTimeout(r, 500));
    startCamera();
  }, [startCamera, stopCamera]);

  /**
   * Capture the current frame after a short countdown.
   */
  const handleCapture = useCallback(() => {
    if (!isActive || status === 'scanning' || status === 'verified') return;

    setCountdown(3);
    setStatus('scanning');

    let count = 3;
    timerRef.current = setInterval(() => {
      count -= 1;
      setCountdown(count);

      if (count <= 0) {
        clearInterval(timerRef.current);
        timerRef.current = null;

        const image = captureImage();
        if (image) {
          const step = currentStepRef.current;
          const prevImages = capturedImagesRef.current;
          const newImages = [...prevImages, image];

          setCapturedImages(newImages);
          capturedImagesRef.current = newImages;
          setStatus('verified');

          if (step < DIRECTIONS.length - 1) {
            setTimeout(() => {
              const nextStep = step + 1;
              setCurrentStep(nextStep);
              currentStepRef.current = nextStep;
              setStatus('idle');
              setCountdown(null);
            }, 1000);
          } else {
            setTimeout(() => {
              onCaptureComplete(newImages);
            }, 500);
          }
        } else {
          setStatus('failed');
          setCountdown(null);
        }
      }
    }, 1000);
  }, [isActive, status, captureImage, onCaptureComplete]);

  const handleRetry = useCallback(() => {
    setStatus('idle');
    setCountdown(null);
  }, []);

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
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Camera Access Required</h3>
        <p className="text-gray-600 mb-4">{error}</p>
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={handleRetryCamera}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Try Again {retryCount > 0 ? `(Attempt ${retryCount + 1})` : ''}
          </button>
          <p className="text-xs text-gray-400 max-w-xs">
            Close any other app using the camera (Zoom, Teams, etc.) and try again.
            If you just granted permission, wait a moment and retry.
          </p>
        </div>
      </div>
    );
  }

  // ── Camera starting state ──
  if (!isActive && !error) {
    return (
      <div className="text-center p-8">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
          <p className="text-gray-600 font-medium">Starting camera...</p>
          <p className="text-xs text-gray-400">Please allow camera access when prompted</p>
        </div>
      </div>
    );
  }

  const direction = DIRECTIONS[currentStep] || DIRECTIONS[0];

  return (
    <div className="w-full max-w-lg mx-auto">
      {/* Progress indicator */}
      <div className="flex items-center justify-between mb-6">
        {DIRECTIONS.map((d, i) => (
          <div key={d.id} className="flex items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
                i < currentStep
                  ? 'bg-green-500 text-white'
                  : i === currentStep
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-500'
              }`}
            >
              {i < currentStep ? '✓' : i + 1}
            </div>
            {i < DIRECTIONS.length - 1 && (
              <div className={`w-12 sm:w-16 h-1 mx-1 rounded ${i < currentStep ? 'bg-green-500' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Instruction */}
      <div className="text-center mb-4">
        <span className="text-4xl mb-2 block">{direction.icon}</span>
        <h3 className="text-lg font-semibold text-gray-900">{direction.label}</h3>
        <p className="text-sm text-gray-500 mt-1">{direction.instruction}</p>
      </div>

      {/* Camera View */}
      <div className="camera-container relative bg-black rounded-2xl overflow-hidden mb-4">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="webcam-video w-full"
        />

        {/* Face guide overlay */}
        <div className={`face-overlay ${status === 'verified' ? 'verified' : status === 'failed' ? 'failed' : ''}`} />

        {/* Scan line when scanning */}
        {status === 'scanning' && <div className="scan-line" />}

        {/* Countdown overlay */}
        {countdown !== null && (
          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-40">
            <span className="text-6xl font-bold text-white drop-shadow-lg">{countdown}</span>
          </div>
        )}
      </div>

      {/* Status */}
      <div className="text-center mb-4">
        <StatusBadge
          status={status}
          message={
            status === 'scanning'
              ? 'Scanning...'
              : status === 'verified'
              ? 'Captured!'
              : status === 'failed'
              ? 'No face detected. Try again.'
              : 'Position your face and click Capture'
          }
        />
      </div>

      {/* Controls */}
      <div className="flex gap-3 justify-center">
        {onCancel && (
          <button
            onClick={onCancel}
            className="px-6 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        )}

        {status === 'failed' ? (
          <button
            onClick={handleRetry}
            className="px-6 py-2.5 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors"
          >
            Retry
          </button>
        ) : (
          <button
            onClick={handleCapture}
            disabled={!isActive || status === 'scanning' || status === 'verified'}
            className="px-8 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {status === 'scanning' ? 'Capturing...' : `Capture ${direction.label}`}
          </button>
        )}
      </div>

      {/* Captured thumbnails */}
      {capturedImages.length > 0 && (
        <div className="mt-6">
          <p className="text-sm text-gray-500 mb-2">Captured ({capturedImages.length}/4):</p>
          <div className="flex gap-2 justify-center">
            {capturedImages.map((img, i) => (
              <img
                key={i}
                src={img}
                alt={`Capture ${i + 1}`}
                className="w-16 h-16 object-cover rounded-lg border-2 border-green-400"
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FaceCaptureRegistration;
