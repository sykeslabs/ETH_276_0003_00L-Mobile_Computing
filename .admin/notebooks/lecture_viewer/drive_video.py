"""Public Google Drive range streaming; media stays in Drive, never on disk."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from runpy import run_path
import secrets
from threading import Thread
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CODEC = run_path(str(Path(__file__).with_name('ethtv_format.py')))
DEFAULT_MANIFEST_ID = '12IOs_VDgaqkDMwBNuZ3Yb0SUFrbZHtUn'
DEFAULT_FOLDER_ID = '1_smrpOp_9FkNkUmVdhYZ0rOYrd7Zx_M9'


def download_url(file_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', file_id):
        raise ValueError('Invalid Google Drive file ID')
    return 'https://drive.usercontent.google.com/download?export=download&confirm=t&id=' + file_id


def retry_drive(operation, description):
    """Retry one transient connection failure; preserve permission/HTTP errors."""
    for attempt in range(2):
        try:
            return operation()
        except HTTPError:
            raise
        except (URLError, TimeoutError, ConnectionError) as error:
            if attempt:
                raise URLError(
                    f"Google Drive timed out or could not be reached while {description}. "
                    "Rerun the Lecture Videos cell. If this persists, check your "
                    "network/VPN and access to drive.google.com and "
                    "drive.usercontent.google.com. " + str(error)
                ) from error
            sleep(1)


def read_url(url, limit):
    def read():
        with urlopen(url, timeout=30) as response:
            return response.read(limit + 1)
    return retry_drive(read, 'reading the folder, channel list, or captions')


def read_small(file_id, limit=2 * 1024 * 1024):
    data = read_url(download_url(file_id), limit)
    if len(data) > limit:
        raise ValueError('Drive metadata or captions exceed the size limit')
    if data.lstrip().lower().startswith((b'<!doctype html', b'<html')):
        raise ValueError('Drive returned a sign-in or download-limit page. Check public sharing.')
    return data


def parse_folder_listing(html):
    """Read Drive's public folder data without executing its JavaScript."""
    match = re.search(r"window\['_DRIVE_ivd'\]\s*=\s*'((?:\\.|[^'\\])*)'", html)
    if not match:
        raise ValueError('Cannot read the public Drive folder. Check Anyone with the link sharing.')
    encoded = re.sub(r'\\x([0-9a-fA-F]{2})', lambda item: '\\u00' + item[1], match[1])
    decoded = json.loads('"' + encoded.replace("\\'", "'") + '"')
    tree = json.loads(decoded)
    files = {}

    def visit(node):
        if not isinstance(node, list):
            return
        if (len(node) >= 4 and isinstance(node[0], str) and isinstance(node[2], str)
                and isinstance(node[3], str) and '/' in node[3]
                and re.fullmatch(r'[A-Za-z0-9_-]+', node[0])):
            name, file_id = node[2], node[0]
            if name in files and files[name] != file_id:
                raise ValueError(f'Duplicate filename in Drive folder: {name}')
            files[name] = file_id
        for child in node:
            if isinstance(child, list):
                visit(child)

    visit(tree)
    return files


def list_public_folder(folder_id=DEFAULT_FOLDER_ID):
    download_url(folder_id)  # Validate the ID before constructing the folder URL.
    html = read_url('https://drive.google.com/drive/folders/' + folder_id, 10 * 1024 * 1024)
    if len(html) > 10 * 1024 * 1024:
        raise ValueError('Drive folder listing is too large')
    return parse_folder_listing(html.decode('utf-8'))


def discover_channels(files, configured=()):
    """Keep configured ordering; append new, complete video/caption pairs."""
    settings = {entry['video']: entry for entry in configured}
    paired = {name for name in files if name.lower().endswith('.ethtv')
              and str(Path(name).with_suffix('.vtt')) in files}
    ordered = [entry['video'] for entry in configured if entry['video'] in paired]

    def natural_key(name):
        return [int(part) if part.isdigit() else part.casefold() for part in re.split(r'(\d+)', name)]

    ordered.extend(sorted(paired.difference(ordered), key=natural_key))
    entries = []
    for name in ordered:
        entry = dict(settings.get(name, {}))
        caption_name = str(Path(name).with_suffix('.vtt'))
        entry.update(video=name, captions=caption_name, video_id=files[name], captions_id=files[caption_name])
        entry.setdefault('source', name)
        entry.setdefault('fit', 'contain')
        entries.append(entry)
    if not entries:
        raise ValueError('No complete .ethtv / same-named .vtt pairs found in the public Drive folder')
    return entries


def load_channels(file_id=None, folder_id=DEFAULT_FOLDER_ID):
    files = list_public_folder(folder_id)
    manifest_id = file_id or files.get('channels.json')
    configured = json.loads(read_small(manifest_id).decode('utf-8-sig')) if manifest_id else []
    if not isinstance(configured, list):
        raise ValueError('The online channel list is invalid')
    return discover_channels(files, configured)

class DriveVideo:
    def __init__(self, file_id):
        self.url = download_url(file_id)
        with self.open_range(0, CODEC['HEADER'].size - 1) as response:
            header = response.read(CODEC['HEADER'].size)
            total = int(response.headers['Content-Range'].split('/')[-1])
        if len(header) != CODEC['HEADER'].size:
            raise ValueError('Drive returned a truncated ETHTV header')
        magic, self.nonce, self.size, self.digest = CODEC['HEADER'].unpack(header)
        self.offset = CODEC['HEADER'].size
        if magic != CODEC['MAGIC'] or self.size + self.offset != total:
            raise ValueError('Invalid or incomplete ETHTV recording on Drive')

    def open_range(self, start, end):
        request = Request(self.url, headers={
            'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity',
        })
        response = retry_drive(lambda: urlopen(request, timeout=30), 'opening a video byte range')
        content_range = response.headers.get('Content-Range', '')
        if response.status != 206 or not content_range.startswith(f'bytes {start}-{end}/'):
            response.close()
            raise ValueError('Drive did not serve the requested byte range; check sharing or download limits')
        return response


def serve_drive_channels(entries):
    # Read only each video's 64-byte container header at startup.
    with ThreadPoolExecutor(max_workers=min(4, len(entries))) as pool:
        videos = list(pool.map(lambda entry: DriveVideo(entry['video_id']), entries))
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def headers_for(self, status, content_type, length, content_range=None):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(length))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Accept-Ranges', 'bytes')
            if content_range:
                self.send_header('Content-Range', content_range)
            self.end_headers()

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Range')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()

        def do_HEAD(self):
            self.do_GET(head=True)

        def do_GET(self, head=False):
            streaming = False
            try:
                if self.path == f'/{token}/tv':
                    data = self.server.tv_page.encode('utf-8')
                    self.headers_for(200, 'text/html; charset=utf-8', len(data))
                    if not head:
                        self.wfile.write(data)
                    return
                match = re.fullmatch('/' + token + r'/(video|captions)/(\d+)\.(mp4|vtt)', self.path)
                if not match or int(match[2]) >= len(entries):
                    self.send_error(404)
                    return
                kind, index, extension = match.groups()
                index = int(index)
                if kind == 'captions' and extension == 'vtt':
                    caption_id = entries[index].get('captions_id')
                    if not caption_id:
                        self.send_error(404)
                        return
                    data = read_small(caption_id)
                    if not data.decode('utf-8-sig').startswith('WEBVTT'):
                        raise ValueError('Drive caption file is not WebVTT')
                    self.headers_for(200, 'text/vtt; charset=utf-8', len(data))
                    if not head:
                        self.wfile.write(data)
                    return
                if kind != 'video' or extension != 'mp4':
                    self.send_error(404)
                    return
                video = videos[index]
                start, end = 0, video.size - 1
                requested = self.headers.get('Range')
                if requested:
                    parts = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
                    if not parts or not any(parts.groups()):
                        self.headers_for(416, 'text/plain', 0, f'bytes */{video.size}')
                        return
                    first, last = parts.groups()
                    if first:
                        start = int(first)
                        end = min(int(last), end) if last else end
                    else:
                        start = max(0, video.size - int(last))
                    if start > end or start >= video.size:
                        self.headers_for(416, 'text/plain', 0, f'bytes */{video.size}')
                        return
                content_range = f'bytes {start}-{end}/{video.size}' if requested else None
                if head:
                    self.headers_for(206 if requested else 200, 'video/mp4', end-start+1, content_range)
                    return
                # Translate logical MP4 offsets into ETHTV offsets on Drive.
                with video.open_range(start+video.offset, end+video.offset) as upstream:
                    self.headers_for(206 if requested else 200, 'video/mp4', end-start+1, content_range)
                    streaming = True
                    remaining, position = end-start+1, start
                    while remaining:
                        chunk = upstream.read(min(256 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(CODEC['transform'](chunk, position, video.nonce))
                        remaining -= len(chunk)
                        position += len(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except (HTTPError, URLError, OSError, ValueError) as error:
                if streaming:
                    self.close_connection = True
                else:
                    self.send_error(502, str(error))

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.tv_page = ''
    Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/{token}'
    channels = []
    for index, entry in enumerate(entries):
        filename = entry.get('source', entry.get('video', f'Lecture {index+1}'))
        channels.append(dict(label=Path(filename).stem, filename=filename,
                             video=f'{base}/video/{index}.mp4',
                             captions=f'{base}/captions/{index}.vtt' if entry.get('captions_id') else None,
                             fit=entry.get('fit', 'contain')))
    return server, base + '/tv', channels
