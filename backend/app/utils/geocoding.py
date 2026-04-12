# pyre-ignore-all-errors
"""
Reverse geocoding utility using OpenStreetMap Nominatim API.
Free, no API key required. Returns detailed address with road, area, city, state, country, pincode.
"""

import logging
import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


async def reverse_geocode(latitude: float, longitude: float) -> dict:
    """
    Convert latitude/longitude to a human-readable address.

    Returns a dict with:
      - road: street / road name
      - area: neighbourhood / suburb / village (most specific)
      - suburb: broader suburb / quarter
      - city: city / town / municipality
      - district: district / county
      - state: state / region
      - country: country name
      - pincode: postal code
      - display_name: full formatted address from Nominatim
    """
    result = {
        "road": "",
        "area": "",
        "suburb": "",
        "city": "",
        "district": "",
        "state": "",
        "country": "",
        "pincode": "",
        "display_name": "",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                NOMINATIM_URL,
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "format": "json",
                    "addressdetails": 1,
                    "namedetails": 1,
                    "zoom": 18,
                },
                headers={
                    "User-Agent": "FaceAuth/1.0 (face-auth-app)",
                    "Accept-Language": "en",
                },
            )
            response.raise_for_status()
            data = response.json()

        address = data.get("address", {})

        # Road / Street
        result["road"] = (
            address.get("road")
            or address.get("pedestrian")
            or address.get("footway")
            or ""
        )

        # Area: most specific locality name
        result["area"] = (
            address.get("neighbourhood")
            or address.get("suburb")
            or address.get("hamlet")
            or address.get("village")
            or address.get("quarter")
            or ""
        )

        # Suburb: broader area (if different from area)
        suburb = (
            address.get("suburb")
            or address.get("quarter")
            or address.get("village")
            or ""
        )
        # Only set suburb if it's different from area
        if suburb and suburb != result["area"]:
            result["suburb"] = suburb

        # City
        result["city"] = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or ""
        )

        # District / County
        result["district"] = (
            address.get("county")
            or address.get("state_district")
            or ""
        )

        # State
        result["state"] = address.get("state") or address.get("region") or ""

        # Country
        result["country"] = address.get("country") or ""

        # Pincode
        result["pincode"] = address.get("postcode") or ""

        # Full display name from Nominatim
        result["display_name"] = data.get("display_name", "")

        logger.info(
            f"Reverse geocoded ({latitude:.6f}, {longitude:.6f}) → "
            f"{result['road']}, {result['area']}, {result['city']}, {result['state']} - {result['pincode']}"
        )

    except Exception as e:
        logger.warning(f"Nominatim failed for ({latitude}, {longitude}): {e}. Attempting BigDataCloud fallback...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    "https://api.bigdatacloud.net/data/reverse-geocode-client",
                    params={"latitude": latitude, "longitude": longitude, "localityLanguage": "en"}
                )
                res.raise_for_status()
                data = res.json()
                
                result["city"] = data.get("city") or data.get("locality") or ""
                result["state"] = data.get("principalSubdivision") or ""
                result["country"] = data.get("countryName") or ""
                result["pincode"] = data.get("postcode") or ""
                result["display_name"] = ", ".join(filter(None, [result["city"], result["state"], result["country"]]))
                
                # In the free client API, road and area are not guaranteed, but context is accurately maintained
                logger.info(f"Fallback geocoded: {result['display_name']}")
        except Exception as fallback_e:
            logger.warning(f"Fallback geocoding also failed: {fallback_e}")

    return result
