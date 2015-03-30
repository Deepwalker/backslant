import sys
import os.path as op
import backslant
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.meta_path.insert(0, backslant.PymlFinder(op.dirname(__file__)))

import backslant_hook.templates.test as test

class BSHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()
        # self.wfile.write(b"Hello World !")
        for chunk in test.render(title='The Incredible'):
            if chunk:
                self.wfile.write(chunk.encode('utf-8'))
HTTPServer(('', 9000), BSHandler).serve_forever()
