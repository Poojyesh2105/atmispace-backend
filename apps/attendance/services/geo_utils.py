import math


class GeoUtils:
    EARTH_RADIUS_METERS = 6371000

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great-circle distance between two points on the Earth's surface
        using the Haversine formula.

        Args:
            lat1: Latitude of point 1 in decimal degrees.
            lon1: Longitude of point 1 in decimal degrees.
            lat2: Latitude of point 2 in decimal degrees.
            lon2: Longitude of point 2 in decimal degrees.

        Returns:
            Distance in metres.
        """
        r = GeoUtils.EARTH_RADIUS_METERS

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)

        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return r * c
