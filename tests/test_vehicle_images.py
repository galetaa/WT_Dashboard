import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import vehicle_images


class VehicleImageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        vehicle_images._retry_after.clear()

    def test_fetch_uses_official_host_and_subsequent_request_is_cached(self):
        image = b'\x89PNG\r\n\x1a\nexample'
        response = MagicMock()
        response.__enter__.return_value.read.return_value = image
        with patch('vehicle_images.urllib.request.urlopen',return_value=response) as fetch:
            self.assertEqual(vehicle_images.get_image('tankModels/germ_leopard_I',self.directory.name),image)
            self.assertEqual(vehicle_images.get_image('germ_leopard_i',self.directory.name),image)
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(fetch.call_args.args[0].full_url,
                         'https://static.encyclopedia.warthunder.com/images/germ_leopard_i.png')
        self.assertTrue((Path(self.directory.name)/'germ_leopard_i.png').is_file())

    def test_unavailable_image_has_bounded_retry_and_no_invalid_cache(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'<html>missing</html>'
        with patch('vehicle_images.urllib.request.urlopen',return_value=response) as fetch:
            self.assertIsNone(vehicle_images.get_image('missing_unit',self.directory.name))
            self.assertIsNone(vehicle_images.get_image('missing_unit',self.directory.name))
        self.assertEqual(fetch.call_count,1)
        self.assertFalse(list(Path(self.directory.name).iterdir()))

    def test_invalid_identifier_is_rejected_before_network_access(self):
        with patch('vehicle_images.urllib.request.urlopen') as fetch:
            for identifier in ['..','unit?token=x','x.png','unit%2f..','']:
                with self.assertRaises(ValueError):
                    vehicle_images.get_image(identifier,self.directory.name)
        fetch.assert_not_called()
