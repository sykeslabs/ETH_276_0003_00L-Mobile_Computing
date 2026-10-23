"""Loopback-only, range-capable streaming for the notebook's selected media files."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit
import re
import secrets
from runpy import run_path


def serve_recording(video, captions=None):
    token = secrets.token_urlsafe(24)
    video = Path(video)
    codec = run_path(str(Path(__file__).with_name('ethtv_format.py')))
    info = codec['inspect'](video) if video.suffix.lower() == '.ethtv' else None
    files = {f'/{token}/video.mp4': (video, 'video/mp4', info)}
    if captions:
        files[f'/{token}/captions.vtt'] = (Path(captions), 'text/vtt; charset=utf-8', None)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Range')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()

        def do_POST(self):
            if urlsplit(self.path).path != f'/{token}/state':
                self.send_error(404)
                return
            length = int(self.headers.get('Content-Length', '0'))
            if length > 16:
                self.send_error(400)
                return
            state = self.rfile.read(length).decode('ascii')
            if self.server.on_playback:
                self.server.on_playback(state == 'playing')
            self.send_response(204)
            self.end_headers()

        def do_HEAD(self):
            self.do_GET(head=True)

        def do_GET(self, head=False):
            if urlsplit(self.path).path == f'/{token}/tv' and self.server.tv_page:
                page = self.server.tv_page.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(page)))
                self.end_headers()
                if not head:
                    self.wfile.write(page)
                return
            if urlsplit(self.path).path == f'/{token}/player':
                track = '<track kind="captions" src="captions.vtt" srclang="en" label="English" default>' if captions else ''
                page = Path(__file__).with_suffix('.html').read_text(encoding='utf-8-sig').replace('<!--CAPTIONS-->', track).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(page)))
                self.end_headers()
                if not head:
                    self.wfile.write(page)
                return
            entry = files.get(urlsplit(self.path).path)
            if entry is None:
                self.send_error(404)
                return
            path, content_type, container = entry
            payload_offset = container['offset'] if container else 0
            size = container['size'] if container else path.stat().st_size
            start, end = 0, size - 1
            requested = self.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
                if not match or not any(match.groups()):
                    self.send_error(416)
                    return
                first, last = match.groups()
                if first:
                    start = int(first)
                    end = min(int(last), end) if last else end
                else:
                    start = max(0, size - int(last))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.end_headers()
                    return
            self.send_response(206 if requested else 200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(end - start + 1))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            if requested:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            if head:
                return
            try:
                with path.open('rb') as stream:
                    stream.seek(payload_offset + start)
                    position = start
                    remaining = end - start + 1
                    while remaining:
                        chunk = stream.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        if container:
                            chunk = codec['transform'](chunk, position, container['nonce'])
                        self.wfile.write(chunk)
                        position += len(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.tv_page = None
    server.on_playback = None
    Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/{token}'
    return server, base + '/video.mp4', base + '/captions.vtt' if captions else None
