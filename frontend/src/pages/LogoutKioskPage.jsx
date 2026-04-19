import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { kioskGetEmployee, kioskLogoutEmployee } from '../services/authService';

const LogoutKioskPage = () => {
  const [employeeId, setEmployeeId] = useState('');
  const [employee, setEmployee] = useState(null);
  
  const [loginTimeInput, setLoginTimeInput] = useState('');
  const [currentTime, setCurrentTime] = useState(new Date());
  
  const [isLoading, setIsLoading] = useState(false);
  const [calcResult, setCalcResult] = useState(null);

  // Live clock
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Recalculate duration whenever login time or current time changes
  useEffect(() => {
    if (!employee || !loginTimeInput) {
      setCalcResult(null);
      return;
    }
    
    // Parse login time input (HH:mm)
    const [hoursStr, minutesStr] = loginTimeInput.split(':');
    const loginDate = new Date();
    loginDate.setHours(parseInt(hoursStr, 10));
    loginDate.setMinutes(parseInt(minutesStr, 10));
    loginDate.setSeconds(0);
    
    // If they supposedly logged in 'in the future' for today, maybe it was yesterday evening?
    // We'll assume simplest case: same day calculations.
    if (loginDate > currentTime) {
      loginDate.setDate(loginDate.getDate() - 1);
    }
    
    const diffMs = currentTime - loginDate;
    const diffHours = diffMs / (1000 * 60 * 60);
    
    setCalcResult({
      durationHours: diffHours,
      isAllowed: diffHours >= employee.hours_per_day,
      diffMs: diffMs,
    });
    
  }, [loginTimeInput, currentTime, employee]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!employeeId.trim()) return toast.error("Please enter Employee ID");
    
    setIsLoading(true);
    try {
      const res = await kioskGetEmployee(employeeId.trim());
      if (res.status && res.data) {
        setEmployee(res.data);
        
        // Auto-populate time if we have last login
        if (res.data.last_login_at) {
          const d = new Date(res.data.last_login_at);
          // Check if login was today
          const isToday = d.toDateString() === new Date().toDateString();
          if (isToday) {
            const hh = String(d.getHours()).padStart(2, '0');
            const mm = String(d.getMinutes()).padStart(2, '0');
            setLoginTimeInput(`${hh}:${mm}`);
          } else {
            setLoginTimeInput('');
          }
        } else {
          setLoginTimeInput('');
        }
        
        toast.success("Employee found");
      } else {
        toast.error(res.message || "Employee not found");
      }
    } catch (err) {
      toast.error(err.message || "Failed to fetch employee");
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = async () => {
    if (!calcResult?.isAllowed) {
      return toast.error("Logout not allowed. Working time not completed.");
    }
    
    setIsLoading(true);
    try {
      const durationMins = Math.floor(calcResult.diffMs / (1000 * 60));
      const res = await kioskLogoutEmployee(employee.employee_id, loginTimeInput, durationMins);
      if (res.status) {
        toast.success(`Goodbye ${employee.name}! You have been logged out.`);
        // Reset kiosk
        setEmployee(null);
        setEmployeeId('');
        setLoginTimeInput('');
      } else {
        toast.error(res.message || "Logout failed");
      }
    } catch (err) {
      toast.error("Failed to process logout");
    } finally {
      setIsLoading(false);
    }
  };

  const formatDuration = (ms) => {
    if (ms < 0) return "0 hrs 0 mins";
    const h = Math.floor(ms / (1000 * 60 * 60));
    const m = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60));
    return `${h} hrs ${m} mins`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-blue-100 flex items-center justify-center p-4">
      <div className="max-w-xl w-full bg-white rounded-3xl shadow-2xl overflow-hidden animate-fadeIn">
        
        {/* Header */}
        <div className="bg-indigo-600 p-6 text-white text-center rounded-b-3xl">
          <h1 className="text-3xl font-extrabold tracking-tight">🏢 Office Logout Kiosk</h1>
          <p className="text-indigo-100 mt-2 font-medium">Verify your working hours before departure</p>
        </div>

        <div className="p-8">
          
          {/* Step 1: Search */}
          {!employee ? (
            <form onSubmit={handleSearch} className="space-y-6">
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2">SCAN OR ENTER EMPLOYEE ID</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                       <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                  </div>
                  <input 
                    type="text" 
                    value={employeeId}
                    onChange={(e) => setEmployeeId(e.target.value.toUpperCase())}
                    placeholder="e.g. EMP-1A2B3C"
                    required
                    className="block w-full pl-12 pr-4 py-4 border-2 border-gray-200 rounded-xl focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 transition-all text-xl font-mono uppercase tracking-widest outline-none"
                  />
                </div>
              </div>
              <button 
                type="submit"
                disabled={isLoading}
                className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-lg rounded-xl transition-all shadow-md active:scale-[0.98] disabled:opacity-70 flex justify-center items-center"
              >
                {isLoading ? (
                  <span className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                ) : (
                  "Retrieve Profile"
                )}
              </button>
            </form>
          ) : (
            /* Step 2: Time Check */
            <div className="space-y-8 animate-fadeIn">
              
              {/* Employee Card */}
              <div className="flex items-center gap-4 bg-indigo-50 p-4 rounded-2xl border border-indigo-100">
                <div className="w-16 h-16 bg-indigo-200 rounded-full flex items-center justify-center text-indigo-700 font-bold text-2xl">
                  {employee.name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1">
                  <h2 className="text-xl font-bold text-gray-900">{employee.name}</h2>
                  <p className="text-indigo-600 font-semibold">{employee.designation}</p>
                  <p className="text-xs text-gray-500 font-mono mt-1">ID: {employee.employee_id}</p>
                </div>
                <button 
                  onClick={() => { setEmployee(null); setLoginTimeInput(''); }}
                  className="px-3 py-1.5 text-sm font-medium bg-white text-gray-600 rounded-lg shadow-sm border border-gray-200 hover:bg-gray-50"
                >
                  Change
                </button>
              </div>

              {/* Clocks */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 p-4 rounded-xl border border-gray-200 text-center">
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Live Current Time</label>
                  <p className="text-3xl font-mono text-gray-900 tracking-wider">
                    {currentTime.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </p>
                </div>
                <div className="bg-white p-4 rounded-xl border-2 border-indigo-200 text-center relative overflow-hidden">
                  <label className="block text-xs font-bold text-indigo-500 uppercase mb-2">Enter Login Time</label>
                  <input 
                    type="time" 
                    value={loginTimeInput}
                    onChange={(e) => setLoginTimeInput(e.target.value)}
                    className="w-full text-center text-2xl font-mono font-bold text-indigo-700 bg-transparent outline-none cursor-pointer"
                  />
                  <div className="absolute top-0 right-0 p-1 text-[10px] bg-indigo-100 text-indigo-700 font-bold rounded-bl-lg">EDITABLE</div>
                </div>
              </div>

              {/* Calculation Output */}
              {loginTimeInput && calcResult ? (
                <div className={`p-5 rounded-2xl border-2 transition-all duration-300 ${calcResult.isAllowed ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                  
                  <div className="flex justify-between items-end mb-4">
                    <div>
                      <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Time Logged Today</p>
                      <p className={`text-4xl font-extrabold ${calcResult.isAllowed ? 'text-green-600' : 'text-red-500'}`}>
                        {formatDuration(calcResult.diffMs)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Company Goal</p>
                      <p className="text-xl font-bold text-gray-700">{employee.hours_per_day} hrs</p>
                    </div>
                  </div>

                  {calcResult.isAllowed ? (
                    <div className="bg-green-100 text-green-800 p-3 rounded-lg text-center font-bold text-sm">
                      ✅ Working time completed. You may log out.
                    </div>
                  ) : (
                    <div className="bg-red-100 text-red-800 p-3 rounded-lg text-center font-bold text-md animate-pulse">
                      ❌ Working time not completed go and work!
                    </div>
                  )}

                </div>
              ) : (
                <div className="p-6 bg-gray-50 rounded-2xl border border-gray-100 text-center text-gray-400 font-medium">
                  Please enter your login time to verify hours.
                </div>
              )}

              {/* Actions */}
              <button
                onClick={handleLogout}
                disabled={!calcResult?.isAllowed || isLoading}
                className={`w-full py-4 font-bold text-lg rounded-xl transition-all shadow-md flex justify-center items-center ${
                  calcResult?.isAllowed 
                    ? 'bg-green-600 hover:bg-green-700 text-white active:scale-[0.98]' 
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                }`}
              >
                {isLoading ? (
                  <span className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                ) : calcResult?.isAllowed ? (
                  "Complete Logout"
                ) : (
                  "Cannot Logout Yet"
                )}
              </button>

            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default LogoutKioskPage;
