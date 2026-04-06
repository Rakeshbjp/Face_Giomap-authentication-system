# pyre-ignore-all-errors
"""
Reverse geocoding utility using OpenStreetMap Nominatim API.
Free, no API key required. Returns area name, city, state, country, pincode.
"""

import logging
import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


async def reverse_geocode(latitude: float, longitude: float) -> dict:
    """
    Convert latitude/longitude to a human-readable address.

    Returns a dict with:
      - area: neighbourhood / suburb / village
      - city: city / town
      - state: state / region
      - country: country name
      - pincode: postal code
      - display_name: full formatted address
    """
    result = {
        "area": "",
        "city": "",
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
                    "zoom": 18,
                },
                headers={"User-Agent": "FaceAuth/1.0"},
            )
            response.raise_for_status()
            data = response.json()

        address = data.get("address", {})

        # Area: neighbourhood > suburb > hamlet > village > town
        result["area"] = (
            address.get("neighbourhood")
            or address.get("suburb")
            or address.get("hamlet")
            or address.get("village")
            or address.get("town")
            or address.get("county")
            or ""
        )

        # City
        result["city"] = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("county")
            or ""
        )

        # State
        result["state"] = address.get("state") or address.get("region") or ""

        # Country
        result["country"] = address.get("country") or ""

        # Pincode
        result["pincode"] = address.get("postcode") or ""

        # Full display name
        result["display_name"] = data.get("display_name", "")

        logger.info(f"Reverse geocoded ({latitude}, {longitude}) → {result['area']}, {result['city']}")

    except Exception as e:
        logger.warning(f"Reverse geocoding failed for ({latitude}, {longitude}): {e}")

    return result
