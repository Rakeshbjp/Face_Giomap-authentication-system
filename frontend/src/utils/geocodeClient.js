/**
 * Client-side reverse geocoding using OpenStreetMap Nominatim.
 * Used as a fallback when the backend /api/auth/geocode is unavailable.
 */

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse';

/**
 * Reverse-geocode lat/lng → human-readable address.
 * @param {number} latitude
 * @param {number} longitude
 * @returns {Promise<{road, area, suburb, city, district, state, country, pincode, display_name}>}
 */
export async function reverseGeocodeClient(latitude, longitude) {
  const result = {
    road: '',
    area: '',
    suburb: '',
    city: '',
    district: '',
    state: '',
    country: '',
    pincode: '',
    display_name: '',
  };

  try {
    const params = new URLSearchParams({
      lat: latitude.toString(),
      lon: longitude.toString(),
      format: 'json',
      addressdetails: '1',
      zoom: '18',
    });

    const response = await fetch(`${NOMINATIM_URL}?${params}`, {
      headers: {
        'Accept-Language': 'en',
      },
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const addr = data.address || {};

    // Road
    result.road = addr.road || addr.pedestrian || addr.footway || '';

    // Area: most specific first
    result.area =
      addr.neighbourhood || addr.suburb || addr.hamlet ||
      addr.village || addr.quarter || addr.town || '';

    // Suburb (if different from area)
    const suburb = addr.suburb || addr.quarter || addr.village || '';
    if (suburb && suburb !== result.area) {
      result.suburb = suburb;
    }

    // City
    result.city = addr.city || addr.town || addr.municipality || '';

    // District
    result.district = addr.county || addr.state_district || '';

    // State & Country
    result.state = addr.state || addr.region || '';
    result.country = addr.country || '';
    result.pincode = addr.postcode || '';
    result.display_name = data.display_name || '';
  } catch (err) {
    console.warn('Nominatim client-side geocoding failed:', err, 'Attempting fallback...');
    try {
      const fallbackParams = new URLSearchParams({
        latitude: latitude.toString(),
        longitude: longitude.toString(),
        localityLanguage: 'en',
      });
      const res = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?${fallbackParams}`);
      if (res.ok) {
        const data = await res.json();
        result.city = data.city || data.locality || '';
        result.state = data.principalSubdivision || '';
        result.country = data.countryName || '';
        result.pincode = data.postcode || '';
        result.display_name = [result.city, result.state, result.country].filter(Boolean).join(', ');
      }
    } catch (fallbackErr) {
      console.warn('Fallback client-side geocoding also failed:', fallbackErr);
    }
  }

  return result;
}
