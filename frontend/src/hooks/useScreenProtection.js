import { useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

/**
 * Hook to deter and detect screen sharing for non-admin users.
 * Automatically logs out users if screen sharing or screen capture is detected.
 */
const useScreenProtection = () => {
  const { user, logout } = useAuth();

  useEffect(() => {
    // Only administrators are allowed to share the screen.
    // If a user is not logged in yet, or logged in as a normal user, block screen sharing.
    if (user && user.role === 'admin') {
      return;
    }

    let isLoggingOut = false;

    const triggerLogout = (reason) => {
      if (isLoggingOut) return;
      isLoggingOut = true;
      toast.error(`SECURITY ALERT: ${reason}`);
      // Give the toast a moment to display before forcing logout
      setTimeout(() => logout(), 500);
    };

    // 1. Intercept any native getDisplayMedia calls (prevents sharing from within the app context or extensions)
    if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {
      const originalGetDisplayMedia = navigator.mediaDevices.getDisplayMedia.bind(navigator.mediaDevices);
      
      navigator.mediaDevices.getDisplayMedia = async function (...args) {
        triggerLogout("Screen sharing is strictly prohibited for your account role. Automatically logging out.");
        return Promise.reject(new Error("Screen sharing blocked by security policy."));
      };
    }

    // 2. Prevent Print Screen key usage
    const handleKeyDown = (e) => {
      if (e.key === 'PrintScreen') {
        e.preventDefault();
        triggerLogout("Screen capturing is prohibited. You are being logged out.");
      }
      
      // Prevent common shortcut combos for screen snipping (Windows + Shift + S, Cmd + Shift + 4, etc.)
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 's' || e.key === 'S' || e.key === '4' || e.key === '5')) {
        e.preventDefault();
        triggerLogout("Screen capturing is prohibited. You are being logged out.");
      }
    };

    // Relaxed strict mode: Removed overly aggressive blur and visibility loss tracking
    // because mobile browsers trigger these frequently (keyboard popups, battery notifications, taking screenshots)

    window.addEventListener('keyup', handleKeyDown);
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keyup', handleKeyDown);
      window.removeEventListener('keydown', handleKeyDown);
      
      // Restore original display media API on unmount if it was hooked
      // Normally we would restore it, but modifying prototype globally might be permanent per session.
    };
  }, [user, logout]);
};

export default useScreenProtection;
