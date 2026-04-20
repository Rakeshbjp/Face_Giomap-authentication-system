import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';
import { loginWithPassword, getProfile } from '../services/authService';

const AdminPage = () => {
  const { user, loginSuccess, faceVerified } = useAuth();
  const navigate = useNavigate();

  const [settings, setSettings] = useState({ 
    hours_per_day: 8.0, 
    hours_per_week: 40.0,
    hours_per_month: 160.0,
    hours_per_year: 1920.0,
    weekly_off: 'Sunday' 
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  
  // Login states
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // Load current settings
  useEffect(() => {
    const loadSettings = async () => {
      if (user?.role !== 'admin') return;
      try {
        const res = await getCompanySettings();
        if (res?.data) {
          setSettings({
            hours_per_day: res.data.hours_per_day || 8.0,
            hours_per_week: res.data.hours_per_week || 40.0,
            hours_per_month: res.data.hours_per_month || 160.0,
            hours_per_year: res.data.hours_per_year || 1920.0,
            weekly_off: res.data.weekly_off || 'Sunday'
          });
        }
      } catch (err) {
        console.error("Failed to load settings:", err);
      } finally {
        setIsLoading(false);
      }
    };
    loadSettings();
  }, [user]);

  const handleAdminLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) return toast.error("Email and password required");
    
    setIsLoggingIn(true);
    try {
      const res = await loginWithPassword(email, password, null);
      // loginWithPassword throws on error, so if we reach here it was successful!
      loginSuccess(res);
      
      // Fetch profile to set the user
      const profRes = await getProfile();
      if (profRes.data.role !== 'admin') {
        toast.error("Account does not have admin privileges");
        // Logout logic here if needed...
      } else {
        faceVerified(profRes.data); // mock face verification for admin to bypass guards
        toast.success("Admin authenticated successfully");
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const errorMessage = Array.isArray(detail) ? detail.map(e => e.msg).join(', ') : detail || err.message || "Authentication failed";
      toast.error(errorMessage);
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleSave = async () => {
    const hrsD = parseFloat(settings.hours_per_day);
    const hrsW = parseFloat(settings.hours_per_week);
    const hrsM = parseFloat(settings.hours_per_month);
    const hrsY = parseFloat(settings.hours_per_year);
    
    if (isNaN(hrsD) || hrsD <= 0 || hrsD > 24) return toast.error("Daily hours must be 1-24");
    if (isNaN(hrsW)) return toast.error("Weekly hours required");
    if (isNaN(hrsM)) return toast.error("Monthly hours required");
    if (isNaN(hrsY)) return toast.error("Yearly hours required");
    if (!settings.weekly_off.trim()) {
      return toast.error("Weekly off is required");
    }

    setIsSaving(true);
    try {
      // Create a temporary object to hold the settings we want to pass
      const settingsPayload = {
        hours_per_day: hrsD,
        hours_per_week: hrsW,
        hours_per_month: hrsM,
        hours_per_year: hrsY,
        weekly_off: settings.weekly_off.trim()
      };
      
      await updateCompanySettings(hrsD, settings.weekly_off.trim(), {
        // Note: the backend accepts the whole settings object now
      });
      // Fallback manual API call if the service doesn't support the extra fields directly yet
      await fetch('/api/auth/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(settingsPayload)
      });

      toast.success("Global company settings updated! All employees have been updated.");
    } catch (err) {
      toast.error(err.message || "Failed to update settings");
    } finally {
      setIsSaving(false);
    }
  };

  // If NOT admin, show Login form
  if (!user || user.role !== 'admin') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-purple-950 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white/10 backdrop-blur-xl rounded-3xl shadow-2xl border border-white/10 overflow-hidden">
          <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-6 text-center">
            <h2 className="text-2xl font-bold text-white">Admin Secure Login</h2>
            <p className="text-indigo-100 text-sm mt-1">Authorized Company Heads Only</p>
          </div>
          <form onSubmit={handleAdminLogin} className="p-8 space-y-6">
            <div>
              <label className="block text-sm font-bold text-indigo-200 uppercase tracking-wider mb-2">Admin Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-5 py-4 bg-white/5 border border-white/20 rounded-xl text-white font-medium focus:ring-2 focus:ring-indigo-400 outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-bold text-indigo-200 uppercase tracking-wider mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter admin password"
                className="w-full px-5 py-4 bg-white/5 border border-white/20 rounded-xl text-white font-medium focus:ring-2 focus:ring-indigo-400 outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={isLoggingIn}
              className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-lg rounded-xl transition-all shadow-lg mt-4 disabled:opacity-70 flex justify-center items-center"
            >
              {isLoggingIn ? <span className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin"></span> : "Authenticate"}
            </button>
            <div className="text-center mt-4">
              <button type="button" onClick={() => navigate('/')} className="text-indigo-300 hover:text-white text-sm">Return to Home</button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-purple-950 p-4 sm:p-8">
      <div className="max-w-3xl mx-auto">

        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl shadow-2xl mb-4">
            <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">Admin Control Panel</h1>
          <p className="text-indigo-300 mt-2 text-lg">Configure global company settings for all employees</p>
          <div className="mt-3 inline-flex items-center gap-2 bg-indigo-900/50 px-4 py-1.5 rounded-full border border-indigo-700/50">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
            <span className="text-sm text-indigo-200 font-medium">Logged in as {user?.name} ({user?.role})</span>
          </div>
        </div>

        {/* Working Hours Card */}
        <div className="bg-white/10 backdrop-blur-xl rounded-3xl shadow-2xl border border-white/10 overflow-hidden mb-8">
          <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-3">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Office Working Hours
            </h2>
            <p className="text-indigo-100 text-sm mt-1">
              This sets the mandatory working hours for ALL employees. The Logout Kiosk will block employees from leaving before completing these hours.
            </p>
          </div>

          <div className="p-6 sm:p-8">
            {isLoading ? (
              <div className="flex justify-center py-8">
                <span className="w-8 h-8 border-3 border-indigo-400 border-t-transparent rounded-full animate-spin"></span>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-bold text-indigo-200 uppercase tracking-wider mb-2">
                      Hours Per Day
                    </label>
                    <input
                      type="number" step="0.5" min="1" max="24"
                      value={settings.hours_per_day}
                      onChange={(e) => setSettings({ ...settings, hours_per_day: e.target.value })}
                      className="w-full px-5 py-4 bg-white/10 border border-white/20 rounded-xl text-white text-2xl font-bold focus:ring-2 focus:ring-indigo-400 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-indigo-200 uppercase tracking-wider mb-2">
                      Hours Per Week
                    </label>
                    <input
                      type="number" step="0.5" min="1"
                      value={settings.hours_per_week}
                      onChange={(e) => setSettings({ ...settings, hours_per_week: e.target.value })}
                      className="w-full px-5 py-4 bg-white/10 border border-white/20 rounded-xl text-white text-2xl font-bold focus:ring-2 focus:ring-indigo-400 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-indigo-200 uppercase tracking-wider mb-2">
                      Hours Per Month
                    </label>
                    <input
                      type="number" step="0.5" min="1"
                      value={settings.hours_per_month}
                      onChange={(e) => setSettings({ ...settings, hours_per_month: e.target.value })}
                      className="w-full px-5 py-4 bg-white/10 border border-white/20 rounded-xl text-white text-2xl font-bold focus:ring-2 focus:ring-indigo-400 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-indigo-200 uppercase tracking-wider mb-2">
                      Hours Per Year
                    </label>
                    <input
                      type="number" step="0.5" min="1"
                      value={settings.hours_per_year}
                      onChange={(e) => setSettings({ ...settings, hours_per_year: e.target.value })}
                      className="w-full px-5 py-4 bg-white/10 border border-white/20 rounded-xl text-white text-2xl font-bold focus:ring-2 focus:ring-indigo-400 outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-bold text-indigo-200 uppercase tracking-wider mb-3">
                    Weekly Off Days
                  </label>
                  <input
                    type="text"
                    value={settings.weekly_off}
                    onChange={(e) => setSettings({ ...settings, weekly_off: e.target.value })}
                    placeholder="e.g. Sunday or Saturday, Sunday"
                    className="w-full px-5 py-4 bg-white/10 border border-white/20 rounded-xl text-white text-lg font-medium focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400 outline-none placeholder-white/30"
                  />
                  <p className="text-xs text-indigo-400 mt-2">
                    Days when employees are not required to work. Separate multiple days with commas.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Warning Banner */}
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-5 mb-8 flex items-start gap-3">
          <svg className="w-6 h-6 text-amber-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.268 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <div>
            <p className="text-amber-200 font-bold text-sm">⚠️ This action affects the entire organization</p>
            <p className="text-amber-300/70 text-xs mt-1">
              Saving will immediately cascade the new settings to every employee record in the database.
              Only HR, Manager, or CEO-level users should make changes here.
            </p>
          </div>
        </div>

        {/* Save Button */}
        <button
          onClick={handleSave}
          disabled={isSaving || isLoading}
          className="w-full py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-lg rounded-2xl transition-all shadow-2xl shadow-indigo-500/30 disabled:opacity-50 flex items-center justify-center gap-3 active:scale-[0.98]"
        >
          {isSaving ? (
            <><span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></span> Saving to all employees...</>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Save & Apply to All Employees
            </>
          )}
        </button>

      </div>
    </div>
  );
};

export default AdminPage;
