"""P55 用。OpenAI 互換の呼び先のふりをして、必ず 400 を返す小さな口。LiteLLM から見て「呼び先が内容で断った」状態を作る。"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        self.rfile.read(n)
        body = json.dumps({'error': {'message': 'stub: invalid request (p55)', 'type': 'invalid_request_error', 'code': 'bad_request'}}).encode()
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


HTTPServer(('0.0.0.0', 8000), H).serve_forever()
