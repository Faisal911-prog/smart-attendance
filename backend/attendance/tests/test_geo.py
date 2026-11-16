"""Unit tests for the geofence logic (no Django required)."""
import math
import unittest

from attendance.services import geo

SITE = (47.5316, 21.6273)  # placeholder lecture location in Debrecen


class HaversineTests(unittest.TestCase):
    def test_zero_distance(self):
        self.assertEqual(geo.haversine_m(*SITE, *SITE), 0.0)

    def test_one_degree_of_longitude_at_equator(self):
        # 2 * pi * R / 360 for the mean Earth radius
        self.assertAlmostEqual(geo.haversine_m(0, 0, 0, 1), 111_195.08, delta=1.0)

    def test_one_degree_of_latitude(self):
        self.assertAlmostEqual(geo.haversine_m(10, 20, 11, 20), 111_195.08, delta=1.0)

    def test_symmetry(self):
        a = geo.haversine_m(47.5, 21.6, 47.6, 21.7)
        b = geo.haversine_m(47.6, 21.7, 47.5, 21.6)
        self.assertAlmostEqual(a, b, places=6)

    def test_small_offset_is_about_111_metres(self):
        self.assertAlmostEqual(geo.haversine_m(SITE[0], SITE[1], SITE[0] + 0.001, SITE[1]), 111.2, delta=0.5)

    def test_antipodal_points_do_not_crash(self):
        half_circumference = math.pi * geo.EARTH_RADIUS_M
        self.assertAlmostEqual(geo.haversine_m(0, 0, 0, 180), half_circumference, delta=1.0)


class CoordinateValidationTests(unittest.TestCase):
    def test_valid_and_invalid(self):
        self.assertTrue(geo.is_valid_coordinate(0, 0))
        self.assertTrue(geo.is_valid_coordinate(-90, 180))
        self.assertFalse(geo.is_valid_coordinate(90.0001, 0))
        self.assertFalse(geo.is_valid_coordinate(0, -180.5))
        self.assertFalse(geo.is_valid_coordinate(float("nan"), 0))
        self.assertFalse(geo.is_valid_coordinate(0, float("inf")))
        self.assertFalse(geo.is_valid_coordinate(None, 0))


class CheckLocationTests(unittest.TestCase):
    def check(self, lat, lon, accuracy, radius=100, max_accuracy=100):
        return geo.check_location(SITE[0], SITE[1], radius, lat, lon, accuracy, max_accuracy)

    def test_inside_radius_is_ok(self):
        result = self.check(SITE[0] + 0.0005, SITE[1], 10)  # about 55 m
        self.assertTrue(result.ok)
        self.assertEqual(result.reason, "OK")
        self.assertLess(result.distance_m, 100)

    def test_outside_radius_is_rejected(self):
        result = self.check(SITE[0] + 0.01, SITE[1], 10)  # about 1.1 km
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "OUT_OF_RANGE")

    def test_poor_accuracy_is_rejected_even_when_close(self):
        result = self.check(SITE[0], SITE[1], 500)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "LOW_ACCURACY")

    def test_accuracy_does_not_extend_the_radius(self):
        # about 150 m away with an accuracy circle that would "reach" the site
        result = self.check(SITE[0] + 0.00135, SITE[1], 90)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "OUT_OF_RANGE")

    def test_bad_input(self):
        for lat, lon, acc in [(91, 0, 5), (0, 181, 5), (float("nan"), 0, 5), (0, 0, None), (0, 0, -1)]:
            with self.subTest(lat=lat, lon=lon, acc=acc):
                self.assertEqual(self.check(lat, lon, acc).reason, "BAD_COORDINATES")


if __name__ == "__main__":
    unittest.main()
