/**
 * LocationMap — Interactive OpenStreetMap component with real-time location.
 *
 * Uses plain Leaflet (NOT react-leaflet) to avoid React 18/19 context
 * incompatibility issues. Manages the Leaflet map instance directly via refs.
 */
import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';

// Fix the default marker icon issue with bundlers (Vite/Webpack)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Custom pulsing blue dot icon for user location
const createUserIcon = () =>
  L.divIcon({
    className: 'user-location-marker',
    html: `
      <div style="position:relative;width:20px;height:20px;">
        <div style="
          position:absolute;inset:0;
          background:#3b82f6;
          border:3px solid #fff;
          border-radius:50%;
          box-shadow:0 0 8px rgba(59,130,246,0.6);
          z-index:2;
        "></div>
        <div style="
          position:absolute;inset:-8px;
          background:rgba(59,130,246,0.2);
          border-radius:50%;
          animation:locationPulse 2s ease-out infinite;
          z-index:1;
        "></div>
      </div>
    `,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });

// Registered location icon (green)
const createRegisteredIcon = () =>
  L.divIcon({
    className: 'registered-location-marker',
    html: `
      <div style="position:relative;width:20px;height:20px;">
        <div style="
          position:absolute;inset:0;
          background:#22c55e;
          border:3px solid #fff;
          border-radius:50%;
          box-shadow:0 0 8px rgba(34,197,94,0.6);
          z-index:2;
        "></div>
      </div>
    `,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });

/**
 * LocationMap component.
 *
 * @param {Object} props
 * @param {Object} props.position - { latitude, longitude, accuracy }
 * @param {Object} props.registeredLocation - Optional { latitude, longitude }
 * @param {boolean} props.showAccuracy - Show accuracy circle
 * @param {boolean} props.followUser - Auto-pan to user location
 * @param {number} props.height - Map height in pixels
 * @param {string} props.className - Additional CSS classes
 */
const LocationMap = ({
  position,
  registeredLocation = null,
  showAccuracy = true,
  followUser = true,
  height = 400,
  className = '',
}) => {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const userMarkerRef = useRef(null);
  const accuracyCircleRef = useRef(null);
  const registeredMarkerRef = useRef(null);
  const registeredCircleRef = useRef(null);
  const [isFollowing, setIsFollowing] = useState(followUser);

  // Initialize map once
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const defaultCenter = position
      ? [position.latitude, position.longitude]
      : [20.5937, 78.9629]; // India center

    const map = L.map(mapContainerRef.current, {
      center: defaultCenter,
      zoom: position ? 16 : 5,
      zoomControl: false,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);

    mapRef.current = map;

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update user marker when position changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !position) return;

    const latlng = [position.latitude, position.longitude];

    // User marker
    if (userMarkerRef.current) {
      userMarkerRef.current.setLatLng(latlng);
    } else {
      userMarkerRef.current = L.marker(latlng, { icon: createUserIcon() })
        .addTo(map)
        .bindPopup(
          `<div style="font-size:13px;">
            <p style="font-weight:600;color:#3b82f6;margin-bottom:4px;">📍 Your Location</p>
            <p>Lat: ${position.latitude.toFixed(6)}</p>
            <p>Lng: ${position.longitude.toFixed(6)}</p>
          </div>`
        );
    }

    // Update popup content
    userMarkerRef.current.setPopupContent(
      `<div style="font-size:13px;">
        <p style="font-weight:600;color:#3b82f6;margin-bottom:4px;">📍 Your Location</p>
        <p>Lat: ${position.latitude.toFixed(6)}</p>
        <p>Lng: ${position.longitude.toFixed(6)}</p>
        ${position.accuracy ? `<p style="color:#888;">Accuracy: ±${position.accuracy.toFixed(0)}m</p>` : ''}
      </div>`
    );

    // Accuracy circle
    if (showAccuracy && position.accuracy) {
      if (accuracyCircleRef.current) {
        accuracyCircleRef.current.setLatLng(latlng);
        accuracyCircleRef.current.setRadius(position.accuracy);
      } else {
        accuracyCircleRef.current = L.circle(latlng, {
          radius: position.accuracy,
          color: '#3b82f6',
          fillColor: '#3b82f6',
          fillOpacity: 0.1,
          weight: 1,
        }).addTo(map);
      }
    }

    // Auto-pan
    if (isFollowing) {
      map.setView(latlng, map.getZoom(), { animate: true, duration: 0.5 });
    }
  }, [position, isFollowing, showAccuracy]);

  // Update registered location marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Remove old
    if (registeredMarkerRef.current) {
      map.removeLayer(registeredMarkerRef.current);
      registeredMarkerRef.current = null;
    }
    if (registeredCircleRef.current) {
      map.removeLayer(registeredCircleRef.current);
      registeredCircleRef.current = null;
    }

    if (!registeredLocation) return;

    const latlng = [registeredLocation.latitude, registeredLocation.longitude];

    registeredMarkerRef.current = L.marker(latlng, { icon: createRegisteredIcon() })
      .addTo(map)
      .bindPopup(
        `<div style="font-size:13px;">
          <p style="font-weight:600;color:#22c55e;margin-bottom:4px;">🏠 Registered Location</p>
          <p>Lat: ${registeredLocation.latitude.toFixed(6)}</p>
          <p>Lng: ${registeredLocation.longitude.toFixed(6)}</p>
        </div>`
      );

    // 1km radius circle
    registeredCircleRef.current = L.circle(latlng, {
      radius: 1000,
      color: '#22c55e',
      fillColor: '#22c55e',
      fillOpacity: 0.08,
      weight: 2,
      dashArray: '6 4',
    }).addTo(map);
  }, [registeredLocation]);

  const handleZoomIn = () => mapRef.current?.zoomIn();
  const handleZoomOut = () => mapRef.current?.zoomOut();
  const handleRecenter = () => {
    if (position && mapRef.current) {
      mapRef.current.setView([position.latitude, position.longitude], 16, {
        animate: true,
        duration: 0.5,
      });
    }
    setIsFollowing(!isFollowing);
  };

  return (
    <div
      className={`relative rounded-2xl overflow-hidden shadow-lg ${className}`}
      style={{ height }}
    >
      <div ref={mapContainerRef} style={{ height: '100%', width: '100%' }} />

      {/* Recenter / follow toggle */}
      <button
        onClick={handleRecenter}
        className={`absolute bottom-4 right-4 z-[1000] p-3 rounded-full shadow-lg transition-all ${
          isFollowing
            ? 'bg-blue-600 text-white'
            : 'bg-white text-gray-600 hover:bg-gray-50'
        }`}
        title={isFollowing ? 'Stop following' : 'Follow my location'}
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
      </button>

      {/* Zoom controls */}
      <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-1">
        <button
          onClick={handleZoomIn}
          className="w-9 h-9 bg-white rounded-lg shadow flex items-center justify-center text-gray-700 hover:bg-gray-50 text-lg font-bold"
        >
          +
        </button>
        <button
          onClick={handleZoomOut}
          className="w-9 h-9 bg-white rounded-lg shadow flex items-center justify-center text-gray-700 hover:bg-gray-50 text-lg font-bold"
        >
          −
        </button>
      </div>
    </div>
  );
};

export default LocationMap;
