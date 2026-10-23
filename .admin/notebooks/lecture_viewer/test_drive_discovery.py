"""Offline regression checks for public-folder channel discovery."""
import json
from pathlib import Path
from runpy import run_path
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

DRIVE = run_path(str(Path(__file__).with_name('drive_video.py')))


class DiscoveryTests(unittest.TestCase):
    def test_new_pairs_keep_order_and_use_current_file_ids(self):
        files = {'fri1.ethtv':'new-video-1', 'fri1.vtt':'caption-1',
                 'fri2.ethtv':'video-2', 'fri2.vtt':'caption-2',
                 'sat.ethtv':'video-3', 'sat.vtt':'caption-3',
                 'week2.ethtv':'video-4', 'uploading.ethtv':'not-ready'}
        configured = [dict(video=name, fit='cover' if name=='sat.ethtv' else 'contain',
                           video_id='old-id') for name in ['fri1.ethtv','fri2.ethtv','sat.ethtv']]
        discover = DRIVE['discover_channels']
        self.assertEqual(len(discover(files, configured)), 3)
        files['week2.vtt'] = 'caption-4'
        entries = discover(files, configured)
        self.assertEqual([e['video'] for e in entries], ['fri1.ethtv','fri2.ethtv','sat.ethtv','week2.ethtv'])
        self.assertEqual(entries[0]['video_id'], 'new-video-1')
        self.assertEqual(entries[2]['fit'], 'cover')
        self.assertEqual(entries[3]['captions_id'], 'caption-4')
        self.assertEqual(360/len(entries), 90)

    def test_folder_payload_names_and_duplicate_detection(self):
        def html(records):
            payload = json.dumps([records], ensure_ascii=True)
            escaped = ''.join('\\x%02x' % ord(char) for char in payload)
            return "<script>window['_DRIVE_ivd'] = '" + escaped + "';</script>"
        records = [['video-id', [], 'Lécture.ethtv', 'application/octet-stream'],
                   ['caption-id', [], 'Lécture.vtt', 'text/vtt']]
        files = DRIVE['parse_folder_listing'](html(records))
        self.assertEqual(files['Lécture.ethtv'], 'video-id')
        records.append(['other-id', [], 'Lécture.vtt', 'text/vtt'])
        with self.assertRaises(ValueError):
            DRIVE['parse_folder_listing'](html(records))

    def test_without_manifest_natural_order(self):
        files = {f'video{n}.{suffix}':f'id-{n}-{suffix}'
                 for n in [10,2,1] for suffix in ['ethtv','vtt']}
        self.assertEqual([entry['video'] for entry in DRIVE['discover_channels'](files)],
                         ['video1.ethtv','video2.ethtv','video10.ethtv'])


class ConnectionTests(unittest.TestCase):
    def test_transient_timeout_is_retried(self):
        operation = Mock(side_effect=[URLError(TimeoutError('timed out')), b'channels'])
        with patch.dict(DRIVE['retry_drive'].__globals__, sleep=Mock()):
            self.assertEqual(DRIVE['retry_drive'](operation, 'reading metadata'), b'channels')
        self.assertEqual(operation.call_count, 2)

    def test_persistent_timeout_has_recovery_message(self):
        operation = Mock(side_effect=TimeoutError('timed out'))
        with patch.dict(DRIVE['retry_drive'].__globals__, sleep=Mock()):
            with self.assertRaisesRegex(URLError, 'Rerun the Lecture Videos cell'):
                DRIVE['retry_drive'](operation, 'reading metadata')
        self.assertEqual(operation.call_count, 2)

    def test_permission_error_is_not_retried(self):
        error = HTTPError('https://drive.google.com', 403, 'Forbidden', {}, None)
        operation = Mock(side_effect=error)
        with self.assertRaises(HTTPError):
            DRIVE['retry_drive'](operation, 'reading metadata')
        self.assertEqual(operation.call_count, 1)


if __name__ == '__main__':
    unittest.main()
