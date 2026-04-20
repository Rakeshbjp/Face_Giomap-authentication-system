/**
 * Registration Page — Full user registration flow.
 *
 * Step 1: Fill in personal details (name, email, phone, password).
 * Step 2: Face capture in 4 directions with liveness detection.
 * Step 3: Submit registration with face images.
 */
import React, { useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import FaceCaptureRegistration from '../components/face/FaceCaptureRegistration';
import Spinner from '../components/ui/Spinner';
import { registerUser, checkUser } from '../services/authService';
import useGeolocation from '../hooks/useGeolocation';

const RegisterPage = () => {
  const navigate = useNavigate();
  const { position: geoPosition, loading: geoLoading, permissionDenied: geoDenied, refresh: geoRefresh } = useGeolocation({ watch: false });

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    designation: '',
    profession: '',
    joiningDate: '',
    password: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState({});
  const [step, setStep] = useState(1); // 1 = form, 2 = face capture, 3 = submitting
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [spoofError, setSpoofError] = useState(null);

  /**
   * Handle form field changes.
   */
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear error for this field
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  /**
   * Validate form fields before proceeding.
   */
  const validateForm = () => {
    const newErrors = {};

    if (!formData.name.trim() || formData.name.trim().length < 2) {
      newErrors.name = 'Full name is required (at least 2 characters)';
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      newErrors.email = 'Valid email address is required';
    }

    const phoneRegex = /^\+?\d{10,15}$/;
    const cleanedPhone = formData.phone.replace(/[\s\-()]/g, '');
    if (!phoneRegex.test(cleanedPhone)) {
      newErrors.phone = 'Valid phone number is required (10-15 digits)';
    }

    if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    } else {
      if (!/[A-Z]/.test(formData.password)) newErrors.password = 'Must contain uppercase letter';
      if (!/[a-z]/.test(formData.password)) newErrors.password = 'Must contain lowercase letter';
      if (!/\d/.test(formData.password)) newErrors.password = 'Must contain a digit';
      if (!/[!@#$%^&*(),.?":{}|<>]/.test(formData.password)) newErrors.password = 'Must contain a special character';
    }

    if (!formData.designation.trim() || formData.designation.trim().length < 2) {
      newErrors.designation = 'Designation is required';
    }
    if (!formData.profession) {
      newErrors.profession = 'Profession is required';
    }
    if (!formData.joiningDate) {
      newErrors.joiningDate = 'Joining date is required';
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /**
   * Proceed to face capture step.
   */
  const handleNext = async (e) => {
    e.preventDefault();
    if (validateForm()) {
      setIsSubmitting(true);
      const emailToCheck = formData.email.trim().toLowerCase();
      const phoneToCheck = formData.phone.replace(/[\s\-()]/g, '');
      const result = await checkUser(emailToCheck, phoneToCheck);
      setIsSubmitting(false);
      
      if (result.status) {
        setStep(2);
      } else {
        const errorMsg = result.message || 'User already registered';
        if (errorMsg.toLowerCase().includes('email') && errorMsg.toLowerCase().includes('phone')) {
          setErrors(prev => ({ ...prev, email: errorMsg, phone: errorMsg }));
          toast.error(errorMsg);
        } else if (errorMsg.toLowerCase().includes('email')) {
          setErrors(prev => ({ ...prev, email: errorMsg }));
          toast.error(errorMsg);
        } else if (errorMsg.toLowerCase().includes('phone')) {
          setErrors(prev => ({ ...prev, phone: errorMsg }));
          toast.error(errorMsg);
        } else {
          toast.error(errorMsg);
        }
      }
    }
  };

  /**
   * Handle face capture completion — submit the full registration.
   */
  const handleFaceCaptureComplete = useCallback(
    async (faceImages) => {
      setStep(3);
      setIsSubmitting(true);

      try {
        const payload = {
          name: formData.name.trim(),
          email: formData.email.trim().toLowerCase(),
          phone: formData.phone.replace(/[\s\-()]/g, ''),
          password: formData.password,
          designation: formData.designation.trim(),
          profession: formData.profession,
          joining_date: formData.joiningDate,
          face_images: faceImages,
        };
        if (geoPosition) {
          payload.location = {
            latitude: geoPosition.latitude,
            longitude: geoPosition.longitude,
          };
        }

        const result = await registerUser(payload);

        if (result.status) {
          toast.success('Registration successful! Please log in.');
          navigate('/login');
        } else {
          // If spoofing is detected, show the RED overlay on the camera stream
          if (result.message && result.message.toLowerCase().includes('spoof')) {
            setSpoofError(result.message);
          } else {
            toast.error(result.message || 'Registration failed');
          }
          setStep(2);
        }
      } catch (err) {
        if (err.isTimeout || err.friendlyMessage) {
          toast.error(err.friendlyMessage || 'Server is starting up — please try again in a few seconds.');
          setStep(2);
          return;
        }
        const detail = err.response?.data?.detail;
        const errorMsg = Array.isArray(detail) ? detail.map(e => e.msg).join(', ') : detail || 'Registration failed. Please try again.';
        
        if (typeof errorMsg === 'string' && errorMsg.toLowerCase().includes('spoof')) {
          setSpoofError(errorMsg);
        } else {
          toast.error(errorMsg);
        }
        setStep(2);
      } finally {
        setIsSubmitting(false);
      }
    },
    [formData, navigate]
  );

  /**
   * Skip face registration — register with password only.
   * Used when camera is not available.
   */
  const handleSkipFaceRegistration = useCallback(async () => {
    setStep(3);
    setIsSubmitting(true);

    try {
      const payload = {
        name: formData.name.trim(),
        email: formData.email.trim().toLowerCase(),
        phone: formData.phone.replace(/[\s\-()]/g, ''),
        password: formData.password,
        designation: formData.designation.trim(),
        profession: formData.profession,
        joining_date: formData.joiningDate,
        face_images: [],
      };
      if (geoPosition) {
        payload.location = {
          latitude: geoPosition.latitude,
          longitude: geoPosition.longitude,
        };
      }

      const result = await registerUser(payload);

      if (result.status) {
        toast.success('Registration successful (without face data). Please log in.');
        navigate('/login');
      } else {
        toast.error(result.message || 'Registration failed');
        setStep(2);
      }
    } catch (err) {
      if (err.isTimeout || err.friendlyMessage) {
        toast.error(err.friendlyMessage || 'Server is starting up — please try again in a few seconds.');
        setStep(2);
        return;
      }
      const detail = err.response?.data?.detail;
      const errorMsg = Array.isArray(detail) ? detail.map(e => e.msg).join(', ') : detail || 'Registration failed. Please try again.';
      toast.error(errorMsg);
      setStep(2);
    } finally {
      setIsSubmitting(false);
    }
  }, [formData, navigate]);

  return (
    <div className="min-h-screen min-h-[100dvh] bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center px-3 py-6 sm:p-4">
      <div className="w-full max-w-xl">
        {/* Card */}
        <div className="bg-white rounded-2xl shadow-xl p-4 sm:p-6 md:p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="w-14 h-14 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-3">
              <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Create Account</h1>
            <p className="text-gray-500 mt-1">
              {step === 1 && 'Fill in your details to get started'}
              {step === 2 && 'Capture your face for secure authentication'}
              {step === 3 && 'Completing registration...'}
            </p>
          </div>

          {/* Step indicator */}
          <div className="flex items-center justify-center gap-2 mb-6">
            <div className={`w-3 h-3 rounded-full ${step >= 1 ? 'bg-blue-600' : 'bg-gray-300'}`} />
            <div className={`w-12 h-0.5 ${step >= 2 ? 'bg-blue-600' : 'bg-gray-300'}`} />
            <div className={`w-3 h-3 rounded-full ${step >= 2 ? 'bg-blue-600' : 'bg-gray-300'}`} />
            <div className={`w-12 h-0.5 ${step >= 3 ? 'bg-blue-600' : 'bg-gray-300'}`} />
            <div className={`w-3 h-3 rounded-full ${step >= 3 ? 'bg-blue-600' : 'bg-gray-300'}`} />
          </div>

          {/* Step 1: Form */}
          {step === 1 && (
            <form onSubmit={handleNext} className="space-y-4">
              {/* Name */}
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                  Full Name
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  value={formData.name}
                  onChange={handleChange}
                  placeholder="John Doe"
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors ${
                    errors.name ? 'border-red-400' : 'border-gray-300'
                  }`}
                />
                {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name}</p>}
              </div>

              {/* Email */}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                  Email Address
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="john@example.com"
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors ${
                    errors.email ? 'border-red-400' : 'border-gray-300'
                  }`}
                />
                {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email}</p>}
              </div>

              {/* Phone */}
              <div>
                <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-1">
                  Phone Number
                </label>
                <input
                  id="phone"
                  name="phone"
                  type="tel"
                  value={formData.phone}
                  onChange={handleChange}
                  placeholder="+1234567890"
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors ${
                    errors.phone ? 'border-red-400' : 'border-gray-300'
                  }`}
                />
                {errors.phone && <p className="text-red-500 text-xs mt-1">{errors.phone}</p>}
              </div>

              {/* Auto-Generated Employee ID */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center gap-1">
                  Employee ID
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-semibold">Auto</span>
                </label>
                <input
                  type="text"
                  disabled
                  value="Generated automatically upon registration"
                  className="w-full px-4 py-2.5 border border-gray-200 bg-gray-50 text-gray-500 rounded-lg outline-none cursor-not-allowed"
                />
              </div>

              {/* Designation */}
              <div>
                <label htmlFor="designation" className="block text-sm font-medium text-gray-700 mb-1">
                  Designation
                </label>
                <input
                  id="designation"
                  name="designation"
                  type="text"
                  value={formData.designation}
                  onChange={handleChange}
                  placeholder="Software Engineer"
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors ${
                    errors.designation ? 'border-red-400' : 'border-gray-300'
                  }`}
                />
                {errors.designation && <p className="text-red-500 text-xs mt-1">{errors.designation}</p>}
              </div>

              {/* Profession */}
              <div>
                <label htmlFor="profession" className="block text-sm font-medium text-gray-700 mb-1">
                  Profession <span className="text-red-400">*</span>
                </label>
                <select
                  id="profession"
                  name="profession"
                  value={formData.profession}
                  onChange={handleChange}
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors bg-white ${
                    errors.profession ? 'border-red-400' : 'border-gray-300'
                  }`}
                >
                  <option value="" disabled>Select your profession</option>
                  <option value="Employee">Employee</option>
                  <option value="HR">HR</option>
                  <option value="Manager">Manager</option>
                  <option value="Team Leader">Team Leader</option>
                  <option value="Senior Manager">Senior Manager</option>
                  <option value="Director">Director</option>
                  <option value="Vice President">Vice President</option>
                  <option value="CTO">CTO</option>
                  <option value="CFO">CFO</option>
                  <option value="COO">COO</option>
                  <option value="CEO">CEO</option>
                  <option value="Managing Director">Managing Director</option>
                </select>
                {errors.profession && <p className="text-red-500 text-xs mt-1">{errors.profession}</p>}
                {formData.profession && formData.profession !== 'Employee' && (
                  <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                    Admin Portal access will be granted
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 gap-4">
                {/* Joining Date */}
                <div>
                  <label htmlFor="joiningDate" className="block text-sm font-medium text-gray-700 mb-1">
                    Joining Date
                  </label>
                  <input
                    id="joiningDate"
                    name="joiningDate"
                    type="date"
                    value={formData.joiningDate}
                    onChange={handleChange}
                    className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors ${
                      errors.joiningDate ? 'border-red-400' : 'border-gray-300'
                    }`}
                  />
                  {errors.joiningDate && <p className="text-red-500 text-xs mt-1">{errors.joiningDate}</p>}
                </div>
              </div>

              {/* Password */}
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Min 8 chars, uppercase, digit, special"
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors ${
                    errors.password ? 'border-red-400' : 'border-gray-300'
                  }`}
                />
                {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password}</p>}
              </div>

              {/* Confirm Password */}
              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                  Confirm Password
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  placeholder="Re-enter your password"
                  className={`w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors ${
                    errors.confirmPassword ? 'border-red-400' : 'border-gray-300'
                  }`}
                />
                {errors.confirmPassword && <p className="text-red-500 text-xs mt-1">{errors.confirmPassword}</p>}
              </div>

              {/* ── Registration Location Status ── */}
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
                    <div className="flex-1">
                      <span className="font-medium">📍 Registration location captured</span>
                      <p className="text-xs text-green-500 mt-0.5">You will only be able to login from this area (100m radius)</p>
                    </div>
                    <span className="text-xs text-green-500 font-mono">
                      {geoPosition.latitude.toFixed(4)}, {geoPosition.longitude.toFixed(4)}
                    </span>
                  </>
                ) : geoDenied ? (
                  <>
                    <div className="w-2.5 h-2.5 bg-red-500 rounded-full" />
                    <div className="flex-1">
                      <span className="font-medium">⚠️ Location denied</span>
                      <p className="text-xs text-red-500 mt-0.5">Click 🔒 in address bar → Allow location for login security</p>
                    </div>
                    <button onClick={geoRefresh} className="text-xs bg-red-100 hover:bg-red-200 px-2 py-1 rounded font-medium transition-colors">Retry</button>
                  </>
                ) : (
                  <>
                    <div className="w-2.5 h-2.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    <span className="font-medium">Detecting your location...</span>
                  </>
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors disabled:bg-blue-400"
              >
                {isSubmitting ? 'Checking details...' : 'Next: Face Registration →'}
              </button>
            </form>
          )}

          {/* Step 2: Face Capture */}
          {step === 2 && (
            <div>
              <FaceCaptureRegistration
                onCaptureComplete={handleFaceCaptureComplete}
                onCancel={() => setStep(1)}
                spoofError={spoofError}
                onDismissSpoof={() => setSpoofError(null)}
              />
              {/* Skip option for users without camera */}
              <div className="mt-4 pt-4 border-t border-gray-200 text-center">
                <p className="text-sm text-gray-500 mb-2">
                  Camera not available?
                </p>
                <button
                  onClick={handleSkipFaceRegistration}
                  disabled={isSubmitting}
                  className="text-sm text-gray-600 hover:text-blue-600 underline font-medium transition-colors"
                >
                  Register without face data →
                </button>
                <p className="text-xs text-gray-400 mt-1">
                  You can add face data later. Login will use email + password only.
                </p>
              </div>
            </div>
          )}

          {/* Step 3: Submitting */}
          {step === 3 && (
            <div className="text-center py-12">
              <Spinner size="lg" className="mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900">Creating your account...</h3>
              <p className="text-gray-500 mt-2">Processing face data and securing your account.</p>
            </div>
          )}

          {/* Footer link */}
          <div className="text-center mt-6 text-sm text-gray-500">
            Already have an account?{' '}
            <Link to="/login" className="text-blue-600 hover:underline font-medium">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
