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
import tarfile
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

VERSION = '1.1'

import http, http.server, os, traceback, logging, socketserver
from contextlib import suppress, contextmanager
from urllib.parse import urlparse, parse_qs
from threading import Lock

logger = logging.getLogger(os.path.basename(__file__))
logger.addHandler(logging.NullHandler())

# workarounds for python 3.6

@contextmanager
def nullcontext():
    yield

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

# end of workarounds for python 3.6

lock = Lock()       # generic lock
locks = {}          # dict of file locks, key is path


@contextmanager
def manage_locks(fspath):
    with lock:
        filelock, counter = locks.get(fspath, (Lock(), 0))      # we might not have active lock for fspath
        locks[fspath] = (filelock, counter + 1)
    yield
    with lock:
        filelock, counter = locks[fspath]
        if counter > 1:
            locks[fspath] = (filelock, counter - 1)             # still more requests active for same fspath
        else:
            del locks[fspath]                                   # we are last fspath lock, so destroy lock object


class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):

    def log_message(self, percent_format, *args):
        logger.debug(f'{self.client_address[0]}:{self.client_address[1]:<5d} {percent_format % args}')

    def log_error(self, format, *args):
        logger.error(f'{self.client_address[0]}:{self.client_address[1]:<5d} {format % args}')

    def tgz_directory(self, path, fileio):
        with tarfile.open(fileobj=fileio, mode='w:gz') as tar:
            tar.add(path, arcname='.')
        return fileio

    def zip_directory(self, path, fileio):
        with ZipFile(fileio, 'w', ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(path):
                for file in files:
                    zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), path))
        return fileio

    def send_whole_response(self, status: int, *, reason=None, body='', headers=None):
        headers = {k.lower(): v for k, v in headers.items()} if headers else {}
        with suppress(Exception):
            body = body.encode()            # make sure we have bytes
        headers.update({'content-length': str(len(body)), 'content-type': headers.get('content-type', 'text/plain')})
        self.send_response(status, reason or http.HTTPStatus(status).name)
        [self.send_header(h, str(v)) for h, v in headers.items()]
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_GET(self):
        fspath = self.translate_path(self.path)
        parsed = urlparse(self.path)
        keywords = set([k for keys in parse_qs(parsed.query, keep_blank_values=True) for k in keys.split(',')])
        if not os.path.isdir(fspath):
            return super().do_GET()             # we do not have to do anything
        if sum(['plain' in keywords, 'tgz' in keywords, 'zip' in keywords]) > 1:
            return self.send_whole_response(400, body=f'plain, tgz, zip are mutually exclusive.\n')
        if 'plain' in parsed.query:
            return self.send_whole_response(200, body='\n'.join([f'{f}/' if os.path.isdir(f) else f for f in os.listdir(fspath)]) + '\n')
        elif 'tgz' in parsed.query:
            return self.send_whole_response(200, body=self.tgz_directory(fspath, BytesIO()).getvalue(),
                headers={'content-type': 'application/gzip', 'content-disposition': 'attachment; filename="unknown.tgz"'})
        elif 'zip' in parsed.query:
            return self.send_whole_response(200, body=self.zip_directory(fspath, BytesIO()).getvalue(),
                headers={'content-type': 'application/zip', 'content-disposition': f'attachment; filename="unknown.zip"'})
        else:
            return super().do_GET()

    def do_PUT(self):
        try:
            if not ('content-length' in self.headers or 'chunked' in self.headers.get("transfer-encoding", "")):
                return self.send_whole_response(400, body='No "Content-Length" header nor chunked encoding.\n')

            fspath = self.translate_path(self.path)
            parsed = urlparse(self.path)
            # allow use as well ',' as query args separator
            keywords = set([k for keys in parse_qs(parsed.query, keep_blank_values=True) for k in keys.split(',')])
            mode = 'ab' if 'append' in keywords else 'wb'
            flush = lambda x: x.flush() if 'append' in keywords or 'flush' in keywords else lambda x: None

            with manage_locks(fspath):

                if 'append' in keywords or 'nolock' in keywords:
                    filelock, recordlock = nullcontext(), locks[fspath][0]
                else:
                    filelock, recordlock = locks[fspath][0], nullcontext()

                with filelock:
                    if os.path.exists(fspath) and not ('overwrite' in keywords or 'append' in keywords):
                        logger.error(f'File "{parsed.path}" already exist.')
                        return self.send_whole_response(409, reason='File exists', body=f'File "{parsed.path}" already exists.\nUse "{parsed.path}?overwrite" or "{parsed.path}?append"\n')
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
                self.send_whole_response(200, body=f'File "{parsed.path}" {"updated" if "append" in self.headers else "uploaded"}.\n')

        except Exception as e:
            reason = f'Upload failed for "{self.requestline}"\n' + traceback.format_exc() + '\n'
            [logger.error(s) for s in reason.splitlines()]
            self.send_whole_response(500, body=reason)


if __name__ == '__main__':
    import argparse

    try:
        parser = argparse.ArgumentParser(description='Simple webserver with upload', epilog="EXAMPLE: curl --upload-file /etc/passwd http://localhost:9999/passwd")
        parser.add_argument('--level', required=False, choices=('ERROR', 'INFO', 'DEBUG'), default='INFO', help='Debug level')
        parser.add_argument('--listen', required=False, default='127.0.0.1', help='Listen address')
        parser.add_argument('--port', required=False, type=int, default=9999, help='Listen port')
        parser.add_argument('root', nargs='?', default='.')

        args = vars(parser.parse_args())

        logging.basicConfig(level=args['level'], format='%(asctime)s:%(levelname)-8s %(message)s')
        server_address = (args['listen'], int(args['port']))
        root = os.path.abspath(args['root'])
        logger.info(f'Serving on {args["listen"]}:{args["port"]} from "{root}", version {VERSION}')
        os.chdir(root)

        ThreadingHTTPServer(server_address, MyHTTPRequestHandler).serve_forever()
    except KeyboardInterrupt:
        logger.debug('Shutting down ...')
