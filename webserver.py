#! /usr/bin/env python3
"""
Very simple webserver with upload functionality (PUT)

Copyright (c) 2021, Ing. Jaromir Sedlacek
All rights reserved.

LICENSE: BSD3, https://github.com/sedlacek-modules/webserver/blob/master/LICENSE
README: https://github.com/sedlacek-modules/webserver/blob/master/README.md
"""

VERSION = '1.2'

import http, http.server, os, traceback, logging, socketserver
from contextlib import suppress, contextmanager
from urllib.parse import urlparse, parse_qs, unquote_plus
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
chunk_size = 4*1024*1024

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
        user_agent = self.headers.get('user-agent', '').lower()
        fspath = self.translate_path(self.path)
        if os.path.isdir(fspath) and (user_agent.startswith('curl') or user_agent.startswith('wget')):  # text/plain
            return self.send_whole_response(200, body='\n'.join([f'{f}/' if os.path.isdir(f) else f for f in os.listdir(fspath)]) + '\n')
        else:
            return super().do_GET()

    def do_PUT(self):
        global chunk_size
        try:
            chunked = 'chunked' in self.headers.get('transfer-encoding', '')
            parsed = urlparse(self.path)
            fspath = self.translate_path(self.path)
            action = 'created' if not os.path.exists(fspath) else 'updated' if chunked else 'replaced'

            if (not 'content-length' in self.headers and not chunked) or ('content-length' in self.headers and chunked):
                return self.send_whole_response(400, body='Invalid combination of "Content-Length" and chunked encoding.\n')

            with manage_locks(fspath):
                recordlock = locks[fspath][0] if chunked else nullcontext()
                filelock = locks[fspath][0] if not chunked else nullcontext()
                with filelock:
                    os.makedirs(os.path.dirname(fspath), exist_ok=True)
                    with open(fspath, 'ab' if chunked else 'wb') as w:
                        if chunked:
                            chunk_size = int(self.rfile.readline().strip(), 16)
                            while chunk_size > 0:
                                chunk = self.rfile.read(chunk_size)
                                with recordlock:
                                    w.write(chunk)
                                    w.flush()
                                self.rfile.readline()  # chunk ends with empty line
                                chunk_size = int(self.rfile.readline().strip(), 16)
                        else:
                            content_length = int(self.headers['content-length'])
                            while content_length > 0 and (chunk := self.rfile.read(min(chunk_size, content_length))):
                                w.write(chunk)
                                content_length -= len(chunk)

                return self.send_whole_response(200, body=f'File "{unquote_plus(parsed.path)}" {action}.\n')

        except Exception as e:
            reason = f'Failed for "{self.requestline}"\n' + traceback.format_exc() + '\n'
            [logger.error(s) for s in reason.splitlines()]
            self.send_whole_response(500, body=reason)


if __name__ == '__main__':
    import argparse

    try:
        parser = argparse.ArgumentParser(description='Simple webserver with upload', epilog="EXAMPLE: curl --upload-file /etc/passwd http://localhost:9999/passwd")
        parser.add_argument('--level', required=False, choices=('ERROR', 'INFO', 'DEBUG'), default='INFO', help='Debug level')
        parser.add_argument('--listen', required=False, default='127.0.0.1', help='Listen address')
        parser.add_argument('--port', required=False, type=int, default=9999, help='Listen port')
        parser.add_argument('--chunk', required=False, type=int, default=4*1024*1024, help='Chunk size [Bytes] for PUT requests')
        parser.add_argument('root', nargs='?', default='.')

        args = vars(parser.parse_args())
        chunk_size = args['chunk']

        logging.basicConfig(level=args['level'], format='%(asctime)s:%(levelname)-8s %(message)s')
        server_address = (args['listen'], int(args['port']))
        root = os.path.abspath(args['root'])
        logger.info(f'Serving on {args["listen"]}:{args["port"]} from "{root}", version {VERSION}')
        os.chdir(root)

        ThreadingHTTPServer(server_address, MyHTTPRequestHandler).serve_forever()
    except KeyboardInterrupt:
        logger.debug('Shutting down ...')
