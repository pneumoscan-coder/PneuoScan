
"""
Google Places API (New) integration.

Searches for nearby hospitals, medical clinics, and doctors.
The Google API key is used only on the backend and is never
sent to the React Native application.
"""

import os
from urllib.parse import quote

import requests


GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places"

TIMEOUT = 15

# Fields requested for the nearby-doctors list.
NEARBY_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.shortFormattedAddress",
    "places.formattedAddress",
    "places.rating",
    "places.userRatingCount",
    "places.location",
    "places.currentOpeningHours.openNow",
])

# Fields requested only when the patient opens a specific place.
DETAILS_FIELD_MASK = ",".join([
    "id",
    "displayName",
    "formattedAddress",
    "nationalPhoneNumber",
    "websiteUri",
    "currentOpeningHours.openNow",
])


def _get_api_key() -> str:
    """Return the configured API key or raise a clear error."""
    if not GOOGLE_PLACES_API_KEY:
        raise RuntimeError(
            "GOOGLE_PLACES_API_KEY is not configured on the backend."
        )
    return GOOGLE_PLACES_API_KEY


def _get_google_error(data: dict) -> str:
    """Extract a useful error from a Places API (New) response."""
    error = data.get("error", {})

    if isinstance(error, dict):
        return (
            error.get("message")
            or error.get("status")
            or str(error)
        )

    return str(error) if error else "Unknown Google Places API error"


def search_nearby_doctors(
    lat: float,
    lng: float,
    radius_meters: int = 5000
) -> list[dict]:
    """
    Search for nearby hospitals, medical clinics, and doctors.

    Keeps the existing response structure so the React Native
    frontend does not need to change.
    """

    api_key = _get_api_key()

    if not -90 <= lat <= 90:
        raise ValueError("Latitude must be between -90 and 90.")

    if not -180 <= lng <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    if not 1 <= radius_meters <= 50000:
        raise ValueError("Radius must be between 1 and 50000 meters.")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": NEARBY_FIELD_MASK,
    }

    payload = {
        "includedTypes": [
            "hospital",
            "medical_clinic",
            "doctor"
        ],
        "maxResultCount": 20,
        "rankPreference": "DISTANCE",
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng
                },
                "radius": float(radius_meters)
            }
        }
    }

    try:
        response = requests.post(
            NEARBY_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=TIMEOUT
        )

        data = response.json()

        if not response.ok:
            raise RuntimeError(_get_google_error(data))

    except requests.exceptions.Timeout:
        raise RuntimeError("Google Places API request timed out.")

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Google Places API connection failed: {exc}")

    places = data.get("places", [])
    results = []

    for place in places:
        location = place.get("location", {})
        display_name = place.get("displayName", {})
        opening_hours = place.get("currentOpeningHours", {})

        results.append({
            # Keep the old response keys for frontend compatibility.
            "place_id": place.get("id"),
            "name": display_name.get("text"),
            "address": (
                place.get("shortFormattedAddress")
                or place.get("formattedAddress")
            ),
            "rating": place.get("rating"),
            "total_ratings": place.get("userRatingCount"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "open_now": opening_hours.get("openNow"),
        })

    return results


def get_place_details(place_id: str) -> dict:
    """
    Fetch full details for one selected place.

    The place ID comes from the nearby search response.
    """

    api_key = _get_api_key()

    if not place_id:
        raise ValueError("A valid place_id is required.")

    encoded_place_id = quote(place_id, safe="")

    url = f"{PLACE_DETAILS_URL}/{encoded_place_id}"

    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": DETAILS_FIELD_MASK,
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=TIMEOUT
        )

        data = response.json()

        if not response.ok:
            raise RuntimeError(_get_google_error(data))

    except requests.exceptions.Timeout:
        raise RuntimeError("Google Place Details request timed out.")

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Google Place Details connection failed: {exc}")

    display_name = data.get("displayName", {})
    opening_hours = data.get("currentOpeningHours", {})

    return {
        # Preserve the existing details response structure.
        "name": display_name.get("text"),
        "formatted_address": data.get("formattedAddress"),
        "phone_number": data.get("nationalPhoneNumber"),
        "website": data.get("websiteUri"),
        "open_now": opening_hours.get("openNow"),
    }
