/**
 * Navbar component with authentication-aware navigation.
 * Fully responsive — hamburger menu on mobile, inline links on desktop.
 */
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const Navbar = () => {
  const { isAuthenticated, isFaceVerified, user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    setMobileOpen(false);
    navigate('/login');
  };

  const closeMobile = () => setMobileOpen(false);

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-14 sm:h-16 items-center">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2" onClick={closeMobile}>
            <div className="w-7 h-7 sm:w-8 sm:h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 sm:w-5 sm:h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
            </div>
            <span className="text-lg sm:text-xl font-bold text-gray-900">FaceAuth</span>
          </Link>

          {/* Desktop navigation */}
          <div className="hidden sm:flex items-center gap-3 lg:gap-4">
            {isAuthenticated && isFaceVerified ? (
              <>
                <span className="text-sm text-gray-600 hidden md:block">
                  Welcome, <strong>{user?.name || 'User'}</strong>
                </span>
                <Link to="/dashboard" className="text-sm text-gray-600 hover:text-blue-600 transition-colors">
                  Dashboard
                </Link>
                <Link to="/location" className="text-sm text-gray-600 hover:text-blue-600 transition-colors flex items-center gap-1">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  Live Map
                </Link>
                {user?.role === 'admin' && (
                  <Link to="/admin" className="text-sm text-purple-600 hover:text-purple-800 transition-colors flex items-center gap-1 font-semibold">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Admin
                  </Link>
                )}
                <button
                  onClick={handleLogout}
                  className="px-3 lg:px-4 py-2 text-sm font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-colors"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors">
                  Login
                </Link>
                <Link to="/register" className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors">
                  Register
                </Link>
                <Link to="/logout-kiosk" className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-red-600 border border-red-200 rounded-lg transition-colors flex items-center gap-1">
                  <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  Logout Kiosk
                </Link>
              </>
            )}
          </div>

          {/* Mobile hamburger button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="sm:hidden p-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label="Toggle menu"
          >
            {mobileOpen ? (
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {mobileOpen && (
        <div className="sm:hidden bg-white border-t border-gray-100 shadow-lg animate-fadeIn">
          <div className="px-4 py-3 space-y-1">
            {isAuthenticated && isFaceVerified ? (
              <>
                <div className="px-3 py-2 text-sm text-gray-500 border-b border-gray-100 mb-1">
                  Signed in as <strong className="text-gray-900">{user?.name || 'User'}</strong>
                </div>
                <Link
                  to="/dashboard"
                  onClick={closeMobile}
                  className="block px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-blue-50 hover:text-blue-600 rounded-lg transition-colors"
                >
                  📊 Dashboard
                </Link>
                <Link
                  to="/location"
                  onClick={closeMobile}
                  className="block px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-blue-50 hover:text-blue-600 rounded-lg transition-colors"
                >
                  📍 Live Map
                </Link>
                {user?.role === 'admin' && (
                  <Link
                    to="/admin"
                    onClick={closeMobile}
                    className="block px-3 py-2.5 text-sm font-bold text-purple-600 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors"
                  >
                    ⚙️ Admin Panel
                  </Link>
                )}
                <button
                  onClick={handleLogout}
                  className="w-full text-left px-3 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors mt-1"
                >
                  🚪 Logout
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  onClick={closeMobile}
                  className="block px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-blue-50 hover:text-blue-600 rounded-lg transition-colors"
                >
                  Login
                </Link>
                <Link
                  to="/register"
                  onClick={closeMobile}
                  className="block px-3 py-2.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors text-center"
                >
                  Register
                </Link>
                <Link
                  to="/logout-kiosk"
                  onClick={closeMobile}
                  className="block px-3 py-2.5 mt-2 text-sm font-medium text-red-600 bg-red-50 border border-red-100 hover:bg-red-100 rounded-lg transition-colors text-center flex items-center justify-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  Office Logout Kiosk
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
