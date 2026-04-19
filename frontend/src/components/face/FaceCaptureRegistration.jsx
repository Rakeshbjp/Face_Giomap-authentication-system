/**
 * FaceCaptureRegistration — Live face detection + auto-capture.
 *
 * Detects face in real-time using canvas skin-tone analysis.
 * Only captures when a face is clearly detected.
 * Shows real-time feedback: searching → detected → countdown → captured.
 */
import React, { useState, useCallback, useEffect, useRef } from 'react';
import useCamera from '../../hooks/useCamera';

const DIRECTIONS = [
  { id: 'front', label: 'Look Straight Ahead', icon: '😐', instruction: 'Look directly at the camera' },
  { id: 'left', label: 'Turn Left', icon: '👈', instruction: 'Slowly turn your head to the left' },
  { id: 'right', label: 'Turn Right', icon: '👉', instruction: 'Slowly turn your head to the right' },
  { id: 'updown', label: 'Tilt Up & Down', icon: '👆', instruction: 'Slowly tilt your head up, then down' },
];

const HOLD_SECONDS = 3;

const FaceCaptureRegistration = ({ onCaptureComplete, onCancel, spoofError, onDismissSpoof }) => {
  const { videoRef, isActive, error, startCamera, stopCamera, captureImage } = useCamera({ autoStart: true });

  const [currentStep, setCurrentStep] = useState(0);
  const [capturedImages, setCapturedImages] = useState([]);
  const [phase, setPhase] = useState('waiting'); // waiting | countdown | captured | done
  const [countdown, setCountdown] = useState(HOLD_SECONDS);
  const [faceDetected, setFaceDetected] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  // Refs to avoid stale closures in timers/intervals
  const capturedRef = useRef([]);
  const currentStepRef = useRef(0);
  const phaseRef = useRef('waiting');
  const countdownTimerRef = useRef(null);
  const transitionTimerRef = useRef(null);
  const detectionTimerRef = useRef(null);
  const mountedRef = useRef(true);
  const consecutiveRef = useRef(0);
  const captureImageRef = useRef(captureImage);
  const onCaptureCompleteRef = useRef(onCaptureComplete);

  // Keep refs in sync with latest values
  useEffect(() => { currentStepRef.current = currentStep; }, [currentStep]);
  useEffect(() => { capturedRef.current = capturedImages; }, [capturedImages]);
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  useEffect(() => { captureImageRef.current = captureImage; }, [captureImage]);
  useEffect(() => { onCaptureCompleteRef.current = onCaptureComplete; }, [onCaptureComplete]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
      if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
      if (detectionTimerRef.current) clearTimeout(detectionTimerRef.current);
    };
  }, []);

  /**
   * Detect face presence by analysing skin-tone pixels in the centre of the video.
   */
  const detectFace = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.readyState < 2 || video.videoWidth === 0) return false;

    try {
      const canvas = document.createElement('canvas');
      const sz = 120;
      canvas.width = sz;
      canvas.height = sz;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });

      // Crop the center 50% of the video (where the face guide is)
      const vw = video.videoWidth;
      const vh = video.videoHeight;
      ctx.drawImage(video, vw * 0.25, vh * 0.15, vw * 0.5, vh * 0.7, 0, 0, sz, sz);
      const { data } = ctx.getImageData(0, 0, sz, sz);

      let skin = 0;
      let total = 0;

      for (let i = 0; i < data.length; i += 16) { // Sample every 4th pixel
        const r = data[i], g = data[i + 1], b = data[i + 2];
        total++;
        if (r > 60 && g > 40 && b > 20 && r > g && r > b && (r - g) > 10 && (r - b) > 15) {
          skin++;
        }
      }

      return (skin / total) > 0.08;
    } catch {
      return false;
    }
  }, [videoRef]);

  /**
   * Perform capture, save image, advance to next step.
   * Uses refs so it always reads the latest state.
   */
  const doCapture = useCallback(() => {
    if (!mountedRef.current) return;

    // Stop detection during transition
    if (detectionTimerRef.current) {
      clearTimeout(detectionTimerRef.current);
      detectionTimerRef.current = null;
    }

    const image = captureImageRef.current();
    if (!image) {
      // Failed — reset to waiting
      setPhase('waiting');
      phaseRef.current = 'waiting';
      setCountdown(HOLD_SECONDS);
      consecutiveRef.current = 0;
      return;
    }

    const newImages = [...capturedRef.current, image];
    setCapturedImages(newImages);
    capturedRef.current = newImages;
    setPhase('captured');
    phaseRef.current = 'captured';

    const step = currentStepRef.current;

    if (step < DIRECTIONS.length - 1) {
      transitionTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return;
        const next = step + 1;
        setCurrentStep(next);
        currentStepRef.current = next;
        setPhase('waiting');
        phaseRef.current = 'waiting';
        setCountdown(HOLD_SECONDS);
        setFaceDetected(false);
        consecutiveRef.current = 0;
      }, 1200);
    } else {
      setPhase('done');
      phaseRef.current = 'done';
      transitionTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return;
        onCaptureCompleteRef.current(newImages);
      }, 800);
    }
  }, []); // No deps needed — everything uses refs

  /**
   * Main detection + countdown loop.
   * Runs every 200ms while camera is active and we're in waiting/countdown phase.
   */
  useEffect(() => {
    if (!isActive) return;

    // Only run detection in waiting or countdown phases
    if (phase === 'captured' || phase === 'done') return;

    let countValue = HOLD_SECONDS;
    let countdownRunning = false;
    let lastTickTime = 0;

    const tick = () => {
      if (!mountedRef.current) return;

      const currentPhase = phaseRef.current;
      if (currentPhase === 'captured' || currentPhase === 'done') return;

      const hasFace = detectFace();

      if (hasFace) {
        consecutiveRef.current++;
        setFaceDetected(true);

        if (consecutiveRef.current >= 2 && !countdownRunning) {
          // Face stably detected — start countdown
          countdownRunning = true;
          countValue = HOLD_SECONDS;
          setPhase('countdown');
          phaseRef.current = 'countdown';
          setCountdown(countValue);
          lastTickTime = Date.now();
        }

        if (countdownRunning) {
          const now = Date.now();
          if (now - lastTickTime >= 1000) {
            countValue -= 1;
            setCountdown(countValue);
            lastTickTime = now;

            if (countValue <= 0) {
              // CAPTURE!
              countdownRunning = false;
              doCapture();
              return; // Stop the loop — doCapture handles the transition
            }
          }
        }
      } else {
        consecutiveRef.current = 0;
        setFaceDetected(false);

        if (countdownRunning) {
          // Face lost during countdown — reset
          countdownRunning = false;
          countValue = HOLD_SECONDS;
          setPhase('waiting');
          phaseRef.current = 'waiting';
          setCountdown(HOLD_SECONDS);
        }
      }

      detectionTimerRef.current = setTimeout(tick, 200);
    };

    // Start the detection loop after a brief delay
    detectionTimerRef.current = setTimeout(tick, 300);

    return () => {
      if (detectionTimerRef.current) {
        clearTimeout(detectionTimerRef.current);
        detectionTimerRef.current = null;
      }
    };
  }, [isActive, phase, currentStep, detectFace, doCapture]);

  const handleRetryCamera = useCallback(async () => {
    setRetryCount((c) => c + 1);
    stopCamera();
    await new Promise((r) => setTimeout(r, 500));
    startCamera();
  }, [startCamera, stopCamera]);

  // When spoofError is set, pause scanning visually.
  // When user dismisses it, reset the whole process to 0.
  const handleRetrySpoof = () => {
    setCurrentStep(0);
    setCapturedImages([]);
    setPhase('waiting');
    setFaceDetected(false);
    consecutiveRef.current = 0;
    if (onDismissSpoof) onDismissSpoof();
  };

  // ── Camera error ──
  if (error) {
    return (
      <div className="text-center p-8">
        <div className="text-red-500 mb-4">
          <svg className="w-16 h-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Camera Access Required</h3>
        <p className="text-gray-600 mb-4">{error}</p>
        <button onClick={handleRetryCamera}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          Try Again {retryCount > 0 ? `(Attempt ${retryCount + 1})` : ''}
        </button>
      </div>
    );
  }

  const direction = DIRECTIONS[currentStep] || DIRECTIONS[0];
  const isCaptured = phase === 'captured';
  const isDone = phase === 'done';
  const isCountdown = phase === 'countdown';

  const guideColor = isCaptured
    ? 'border-green-400 shadow-[0_0_30px_rgba(74,222,128,0.5)]'
    : isCountdown
    ? 'border-green-400 animate-pulse shadow-[0_0_20px_rgba(74,222,128,0.4)]'
    : faceDetected
    ? 'border-green-400 shadow-[0_0_15px_rgba(74,222,128,0.3)]'
    : 'border-blue-300/60';

  const statusMsg = isDone
    ? { text: '✅ All captures complete!', cls: 'bg-green-100 text-green-700' }
    : isCaptured
    ? { text: '✅ Captured! Moving to next...', cls: 'bg-green-100 text-green-700' }
    : isCountdown
    ? { text: `😊 Face detected! Capturing in ${countdown}...`, cls: 'bg-green-100 text-green-700' }
    : faceDetected
    ? { text: '✅ Face found! Hold still...', cls: 'bg-green-100 text-green-700' }
    : { text: '👤 Position your face inside the oval', cls: 'bg-blue-100 text-blue-700' };

  return (
    <div className="w-full max-w-lg mx-auto">
      {/* Progress */}
      <div className="flex items-center justify-between mb-5">
        {DIRECTIONS.map((d, i) => (
          <div key={d.id} className="flex items-center">
            <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${
              i < currentStep ? 'bg-green-500 text-white scale-90'
                : i === currentStep ? 'bg-blue-600 text-white ring-4 ring-blue-200 scale-110'
                : 'bg-gray-200 text-gray-400'
            }`}>
              {i < currentStep ? '✓' : i + 1}
            </div>
            {i < DIRECTIONS.length - 1 && (
              <div className={`w-10 sm:w-16 h-1 mx-1 rounded transition-colors duration-500 ${i < currentStep ? 'bg-green-500' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Instruction */}
      <div className="text-center mb-3">
        <span className="text-3xl mb-1 block">{direction.icon}</span>
        <h3 className="text-lg font-bold text-gray-900">{direction.label}</h3>
        <p className="text-sm text-gray-500">{direction.instruction}</p>
      </div>

      {/* Camera */}
      <div className="relative bg-black rounded-2xl overflow-hidden mb-4 shadow-lg" style={{ minHeight: '300px' }}>
        <video ref={videoRef} autoPlay playsInline muted className="w-full rounded-2xl"
          style={{ transform: 'scaleX(-1)' }} />

        {/* Loading overlay */}
        {!isActive && !error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900 rounded-2xl z-10">
            <div className="w-10 h-10 border-4 border-blue-300 border-t-blue-600 rounded-full animate-spin mb-3" />
            <p className="text-white font-medium">Starting camera...</p>
          </div>
        )}

        {/* Face guide oval */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className={`w-44 h-56 sm:w-52 sm:h-64 rounded-[50%] border-[3px] border-dashed transition-all duration-500 ${guideColor}`} />
        </div>

        {/* Face detection badge */}
        {isActive && !isCaptured && !isDone && (
          <div className="absolute top-3 right-3 z-10">
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium backdrop-blur-sm ${
              faceDetected ? 'bg-green-500/80 text-white' : 'bg-gray-600/80 text-white'
            }`}>
              <span className={`w-2 h-2 rounded-full ${faceDetected ? 'bg-green-300 animate-pulse' : 'bg-gray-300 animate-pulse'}`} />
              {faceDetected ? 'Face ✓' : 'No face'}
            </div>
          </div>
        )}

        {/* Countdown */}
        {isCountdown && countdown > 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-20 h-20 rounded-full bg-green-600/70 backdrop-blur-sm flex items-center justify-center shadow-lg">
              <span className="text-4xl font-bold text-white">{countdown}</span>
            </div>
          </div>
        )}

        {/* Scan line */}
        {isCountdown && (
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-green-400 to-transparent opacity-80"
              style={{ animation: 'scanLine 1.5s ease-in-out infinite' }} />
          </div>
        )}

        {/* Flash on capture */}
        {isCaptured && <div className="absolute inset-0 bg-white/40 pointer-events-none" style={{ animation: 'flashFade 0.4s ease-out' }} />}

        {/* Success check */}
        {isCaptured && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="bg-green-500/90 rounded-full w-16 h-16 flex items-center justify-center" style={{ animation: 'scaleIn 0.3s ease-out' }}>
              <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>
        )}

        {/* Done overlay */}
        {isDone && !spoofError && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm z-10">
            <div className="text-center">
              <div className="bg-green-500 rounded-full w-16 h-16 mx-auto mb-3 flex items-center justify-center">
                <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <p className="text-white font-semibold text-lg">All captures complete!</p>
              <p className="text-white/70 text-sm">Processing your face data...</p>
            </div>
          </div>
        )}

        {/* ── Result popup overlay (Spoofing) ── */}
        {spoofError && (
          <div
            className="absolute inset-0 flex flex-col items-center justify-center bg-red-500/20 backdrop-blur-sm z-50 transition-all duration-300"
            style={{ animation: 'fadeIn 0.3s ease-out' }}
          >
            <div className="popup-icon-fail">
              <svg className="w-20 h-20 text-red-500 drop-shadow-lg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="mt-3 bg-white/95 px-5 py-3 rounded-xl shadow-lg max-w-xs text-center" style={{ animation: 'slideUp 0.3s ease-out' }}>
              <p className="text-2xl font-extrabold text-red-600 mb-1">✗ FALSE</p>
              <p className="text-sm font-medium text-red-700 leading-snug">
                {spoofError || 'Face is not clearly visible'}
              </p>
              <p className="text-xs text-red-400 mt-1">Keep your face still, clearly visible, with no obstructions</p>
            </div>
            <button
              onClick={handleRetrySpoof}
              className="mt-3 text-sm text-gray-600 bg-white px-4 py-1.5 rounded-lg shadow hover:bg-gray-50 uppercase font-bold tracking-wider"
            >
              Tap to retry
            </button>
          </div>
        )}
      </div>

      {/* Status */}
      <div className="text-center mb-4">
        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all duration-300 ${statusMsg.cls}`}>
          {statusMsg.text}
        </div>
      </div>

      {/* Thumbnails */}
      <div className="flex gap-2 justify-center mb-4">
        {capturedImages.map((img, i) => (
          <div key={i} className="relative">
            <img src={img} alt={`Capture ${i + 1}`}
              className="w-14 h-14 object-cover rounded-lg border-2 border-green-400 shadow-md"
              style={{ transform: 'scaleX(-1)' }} />
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>
        ))}
        {Array.from({ length: 4 - capturedImages.length }).map((_, i) => (
          <div key={`e-${i}`} className="w-14 h-14 rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center">
            <span className="text-gray-300 text-xs">{capturedImages.length + i + 1}</span>
          </div>
        ))}
      </div>

      {/* Back */}
      {onCancel && !isDone && (
        <div className="text-center">
          <button onClick={onCancel} className="px-6 py-2 text-gray-500 hover:text-gray-700 text-sm transition-colors">
            ← Back
          </button>
        </div>
      )}

      <style>{`
        @keyframes scanLine { 0% { top: 0; } 50% { top: 100%; } 100% { top: 0; } }
        @keyframes scaleIn { 0% { transform: scale(0); } 100% { transform: scale(1); } }
        @keyframes flashFade { 0% { opacity: 1; } 100% { opacity: 0; } }
      `}</style>
    </div>
  );
};

export default FaceCaptureRegistration;
