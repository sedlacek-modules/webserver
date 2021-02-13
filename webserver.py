#! /usr/bin/env python3
"""
Very simple webserver with upload functionality (PUT)
Licensed under BSD3 license, please see LICENSE file

Copyright (c) 2021, Ing. Jaromir Sedlacek
All rights reserved.

Examples (bash syntax):
curl http://localhost:9999/dir/subdir/file --upload-file /etc/passwd
curl http://localhost:9999/dir/subdir/file?overwrite --upload-file /etc/passwd
curl http://localhost:9999/dir/subdir/file?append --upload-file /etc/passwd
while :; do date; sleep 10; done | curl --upload-file - http://localhost:9999/dir/subdir/file?append

Additionally following query args can ve used, both syntax invoke same behaviour
curl http://localhost:9999/dir/subdir/file?append,overwrite,nolock,flush
curl http://localhost:9999/dir/subdir/file?append?overwrite?nolock?flush

Please note
    append always locks before writing chunk
    locks are not file locks, they are implemented only within the server
"""

import http.server
from contextlib import suppress, nullcontext, contextmanager
from urllib.parse import urlparse, parse_qs
import os.path
import traceback
from threading import Lock

import logging
logger = logging.getLogger(os.path.basename(__file__))
logger.addHandler(logging.NullHandler())

lock = Lock()       # generic lock
locks = {}          # dict of file locks, key is path

@contextmanager
def manage_lock(fspath):
    with lock:
        filelock, counter = locks.get(fspath, (Lock(), 0))
        locks[fspath] = (filelock, counter + 1)
    yield
    with lock:
        filelock, counter = locks[fspath]
        if counter <= 1:
            del locks[fspath]
        else:
            locks[fspath] = (filelock, counter - 1)

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):

    def log_message(self, format, *args):
        logger.debug(f'{self.address_string()} {format%args}')

    def log_error(self, format, *args):
        logger.error(f'{self.address_string()} {format % args}')

    def send_whole_response(self, status, reason, body='', content_type='text/plain'):
        with suppress(Exception):
            body = body.encode()        # get bytes
        self.send_response(status, reason)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_PUT(self):
        try:
            if not ('content-length' in self.headers or 'chunked' in self.headers.get("transfer-encoding", "")):
                self.send_whole_response(400, 'Bad request', 'No "Content-Length" header nor chunked encoding.\n')
                return

            fspath = self.translate_path(self.path)
            parsed = urlparse(self.path)
            # allow use as well ',' as query args separator
            keywords = set([k for keys in parse_qs(parsed.query, keep_blank_values=True) for k in keys.split(',')])
            mode = 'ab' if 'append' in keywords else 'wb'
            flush = lambda x: x.flush() if 'append' in keywords else lambda x: None

            with manage_lock(fspath):
                if 'append' in keywords or 'nolock' in keywords:
                    filelock = nullcontext()
                    recordlock, _ = locks[fspath]
                else:
                    filelock, _ = locks[fspath]
                    recordlock = nullcontext()
                with filelock:
                    if os.path.exists(fspath) and not ('overwrite' in keywords or 'append' in keywords):
                        logger.error(f'File "{parsed.path}" already exist.')
                        self.send_whole_response(409, 'File exists', f'File "{parsed.path}" already exists.\nUse "{parsed.path}?overwrite" or "{parsed.path}?append"\n')
                        return
                    os.makedirs(os.path.dirname(fspath), exist_ok=True)
                    with open(fspath, mode) as w:
                        if 'content-length' in self.headers:
                            chunk = self.rfile.read(int(self.headers['content-length']))
                            with recordlock:
                                w.write(chunk)
                                flush(w)
                        else:
                            chunk_size = int(self.rfile.readline().strip(), 16)
                            while chunk_size > 0:
                                chunk = self.rfile.read(chunk_size)
                                with recordlock:
                                    w.write(chunk)
                                    flush(w)
                                self.rfile.readline()           # chunk ends with empty line
                                chunk_size = int(self.rfile.readline().strip(), 16)
                self.send_whole_response(200, 'OK', f'File "{parsed.path}" {"updated" if "append" in self.headers else "uploaded"}.\n')
        except Exception as e:
            reason = f'Upload failed for "{self.requestline}"\n' + traceback.format_exc() + '\n'
            self.send_whole_response(500, 'Internal Server Error', reason)
            [logger.error(s) for s in reason.splitlines()]


if __name__ == '__main__':
    import argparse

    try:
        parser = argparse.ArgumentParser(description='Simple webserver with upload', epilog="EXAMPLE: curl --upload-file /etc/passwd http://localhost:9999/passwd")
        parser.add_argument('--level', required=False, choices=('ERROR', 'INFO', 'DEBUG'), default='INFO', help='Debug level')
        parser.add_argument('--listen', required=False, default='127.0.0.1', help='Listen address')
        parser.add_argument('--port', required=False, type=int, default=9999, help='Listen port')
        parser.add_argument('root', nargs='?', default='.')

        args = vars(parser.parse_args())

        logging.basicConfig(level=args['level'], format='%(asctime)s:%(levelname)-8s%(name)s::  %(message)s')
        server_address = (args['listen'], int(args['port']))
        root = os.path.abspath(args['root'])
        logger.info(f'Serving on {args["listen"]}:{args["port"]} from "{root}"')
        os.chdir(root)
        http.server.ThreadingHTTPServer(server_address, MyHTTPRequestHandler).serve_forever()
    except KeyboardInterrupt:
        logger.debug('Shutting down ...')
        pass