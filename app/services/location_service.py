from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from ..schemas import LocationInfo, SuspiciousActivity


class LocationService:
    def __init__(self):
        self.location_data = {
            "jakarta": {"latitude": -6.2088, "longitude": 106.8456, "city": "Jakarta"},
            "bandung": {"latitude": -6.9175, "longitude": 107.6191, "city": "Bandung"},
            "bali": {"latitude": -8.3405, "longitude": 115.0920, "city": "Bali"},
            "aceh": {"latitude": 5.5481, "longitude": 95.3238, "city": "Aceh"},
            "kalimantan": {"latitude": -1.5000, "longitude": 113.9213, "city": "Kalimantan"}
        }

        self.user_location_history: Dict[str, list] = {}

    def get_location_info(self, location_key: str) -> Optional[LocationInfo]:
        """Get location information by key."""
        if location_key not in self.location_data:
            return None

        data = self.location_data[location_key]
        return LocationInfo(
            city=data["city"],
            latitude=data["latitude"],
            longitude=data["longitude"]
        )

    def calculate_distance(self, loc1: LocationInfo, loc2: LocationInfo) -> float:
        """Calculate distance between two locations (simplified)."""
        # Simplified distance calculation for demo purposes
        lat_diff = abs(loc1.latitude - loc2.latitude)
        lon_diff = abs(loc1.longitude - loc2.longitude)

        # Rough estimation: 1 degree = ~111 km
        distance = ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111
        return round(distance, 2)

    def estimate_travel_time(self, distance_km: float) -> int:
        """Estimate travel time between locations (simplified)."""
        # Assume average speed of 500 km/h (plane) for long distances
        # or 60 km/h (car) for short distances
        if distance_km > 200:
            return int((distance_km / 500) * 60)  # Minutes by plane
        else:
            return int((distance_km / 60) * 60)   # Minutes by car

    def check_suspicious_location(
        self,
        username: str,
        current_location_key: str
    ) -> Tuple[Optional[SuspiciousActivity], Optional[LocationInfo]]:
        """Check if current location indicates suspicious activity."""
        current_location = self.get_location_info(current_location_key)
        if not current_location:
            return None, None

        # Add to history
        now = datetime.utcnow()
        if username not in self.user_location_history:
            self.user_location_history[username] = []

        self.user_location_history[username].append({
            "location": current_location,
            "timestamp": now
        })

        # Keep only last 24 hours
        cutoff = now - timedelta(hours=24)
        self.user_location_history[username] = [
            entry for entry in self.user_location_history[username]
            if entry["timestamp"] > cutoff
        ]

        history = self.user_location_history[username]

        # Check for suspicious patterns
        if len(history) < 2:
            return None, None

        previous_entry = history[-2]
        previous_location = previous_entry["location"]
        time_diff = now - previous_entry["timestamp"]

        # Calculate distance and travel time
        distance = self.calculate_distance(current_location, previous_location)
        time_diff_minutes = int(time_diff.total_seconds() / 60)
        required_travel_time = self.estimate_travel_time(distance)

        current_location.distance_km = distance
        current_location.travel_time_minutes = time_diff_minutes

        suspicious_activity = None

        # Impossible travel detection
        if time_diff_minutes < required_travel_time and distance > 50:
            if distance > 500:  # Very long distance
                suspicious_activity = SuspiciousActivity(
                    isSuspicious=True,
                    suspicionLevel="high",
                    reason="Impossible travel detected",
                    details=[f"Travel from {previous_location.city} to {current_location.city} in {time_diff_minutes} minutes (required: {required_travel_time} minutes)", f"Distance: {distance} km"],
                    score=5
                )
            else:  # Medium distance, quick change
                suspicious_activity = SuspiciousActivity(
                    isSuspicious=True,
                    suspicionLevel="medium",
                    reason="Rapid location change detected",
                    details=[f"Quick travel from {previous_location.city} to {current_location.city} in {time_diff_minutes} minutes", f"Distance: {distance} km"],
                    score=3
                )

        # Multiple location pattern (3+ locations in 24h)
        elif len(set(entry["location"].city for entry in history)) >= 3:
            suspicious_activity = SuspiciousActivity(
                isSuspicious=True,
                suspicionLevel="medium",
                reason="Multiple location pattern detected",
                details=[f"Login from {len(set(entry['location'].city for entry in history))} different cities in 24 hours"],
                score=2
            )

        return suspicious_activity, previous_location


location_service = LocationService()