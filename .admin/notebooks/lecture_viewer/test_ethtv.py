"""Regression checks for ETHTV byte ranges and non-destructive packaging."""
import hashlib
from pathlib import Path
from runpy import run_path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

CODEC = run_path(str(Path(__file__).with_name('ethtv_format.py')))
SERVE = run_path(str(Path(__file__).with_name('local_video.py')))['serve_recording']


class ContainerTests(unittest.TestCase):
    def test_roundtrip_ranges_and_captions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, packed, captions = root/'input.mp4', root/'test.ethtv', root/'test.vtt'
            data = b'\x00\x00\x00\x18ftypisom' + bytes(range(256)) * 800
            source.write_bytes(data)
            captions.write_text('WEBVTT\n', encoding='utf-8')
            info = CODEC['pack'](source, packed)
            self.assertEqual(source.read_bytes(), data)
            self.assertNotEqual(packed.read_bytes()[info['offset']:info['offset']+32], data[:32])
            self.assertEqual(info['sha256'], hashlib.sha256(data).digest())
            with self.assertRaises(FileExistsError):
                CODEC['pack'](source, packed)
            server, url, caption_url = SERVE(packed, captions)
            try:
                self.assertEqual(urlopen(url).read(), data)
                for start, end in [(0,31),(17,91),(65520,65570),(65536,65599),(len(data)-20,len(data)-1)]:
                    response = urlopen(Request(url, headers={'Range': f'bytes={start}-{end}'}))
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.read(), data[start:end+1])
                self.assertEqual(urlopen(Request(url, headers={'Range':'bytes=-41'})).read(), data[-41:])
                self.assertEqual(int(urlopen(Request(url, method='HEAD')).headers['Content-Length']), len(data))
                self.assertEqual(urlopen(caption_url).read(), b'WEBVTT\n')
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(url, headers={'Range': f'bytes={len(data)}-'}))
                self.assertEqual(error.exception.code, 416)
            finally:
                server.shutdown()
                server.server_close()

    def test_invalid_input_does_not_leave_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, packed = root/'bad.mp4', root/'bad.ethtv'
            source.write_bytes(b'not an mp4')
            with self.assertRaises(ValueError):
                CODEC['pack'](source, packed)
            self.assertFalse(packed.exists())
            self.assertFalse(packed.with_name(packed.name+'.partial').exists())


if __name__ == '__main__':
    unittest.main()
