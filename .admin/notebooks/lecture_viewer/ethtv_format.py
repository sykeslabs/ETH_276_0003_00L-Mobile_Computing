"""ETHTV v1: reversible header obfuscation for casual playback deterrence.

This is not encryption or DRM. The key is intentionally shipped with the player.
Pack future recordings with: python ethtv_format.py INPUT.mp4 OUTPUT.ethtv
The input must already use audio supported by VS Code (our copies use MP3).
"""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import struct

MAGIC = b'ETHTV001'
HEADER = struct.Struct('>8s16sQ32s')
SCRAMBLED_BYTES = 65536
SHARED_KEY = bytes.fromhex('ba2849b30a918eed7a2f34716f4a2d5d6e0ba183d317105ca167992f2a6c8e44')


def transform(data, offset, nonce):
    """Symmetric XOR of the initial 64 KiB, supporting arbitrary byte ranges."""
    count = min(len(data), max(0, SCRAMBLED_BYTES - offset))
    if not count:
        return data
    result = bytearray(data)
    position = 0
    while position < count:
        block, within = divmod(offset + position, 64)
        mask = hashlib.blake2b(nonce + block.to_bytes(8, 'big'), key=SHARED_KEY).digest()
        take = min(64 - within, count - position)
        for i in range(take):
            result[position + i] ^= mask[within + i]
        position += take
    return bytes(result)


def inspect(path):
    path = Path(path)
    with path.open('rb') as stream:
        header = stream.read(HEADER.size)
    if len(header) != HEADER.size:
        raise ValueError(f'Truncated ETHTV header: {path}')
    magic, nonce, size, digest = HEADER.unpack(header)
    if magic != MAGIC or path.stat().st_size != HEADER.size + size:
        raise ValueError(f'Invalid ETHTV file or unsupported version: {path}')
    return dict(offset=HEADER.size, nonce=nonce, size=size, sha256=digest)


def pack(source, destination):
    """Create a new container, preserving the source and refusing overwrites."""
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    if destination.suffix.lower() != '.ethtv':
        raise ValueError('Destination must use .ethtv')
    nonce, digest = secrets.token_bytes(16), hashlib.sha256()
    temporary = destination.with_name(destination.name + '.partial')
    offset = 0
    created = False
    try:
        with source.open('rb') as original, temporary.open('xb') as output:
            created = True
            first = original.read(1024 * 1024)
            if first[4:8] != b'ftyp':
                raise ValueError('Expected an MP4 file with an ftyp header')
            output.write(bytes(HEADER.size))
            chunk = first
            while chunk:
                digest.update(chunk)
                output.write(transform(chunk, offset, nonce))
                offset += len(chunk)
                chunk = original.read(1024 * 1024)
            output.seek(0)
            output.write(HEADER.pack(MAGIC, nonce, offset, digest.digest()))
        # Rename refuses an existing destination on Windows; recheck before commit.
        if destination.exists():
            raise FileExistsError(destination)
        temporary.rename(destination)
        return inspect(destination)
    finally:
        if created and temporary.exists():
            temporary.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    info = pack(args.source, args.destination)
    print(f'Packed {args.destination.name}: {info["size"]} bytes; source preserved')
