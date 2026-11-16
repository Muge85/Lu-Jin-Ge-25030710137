# -*- coding: utf-8 -*-
"""
本地预览服务器（带 no-cache 响应头，确保数据更新后浏览器总能加载最新文件）
用法：python serve.py [端口]，默认 8765
"""
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"Serving air_quality_web at http://localhost:{port}  (no-cache)")
    HTTPServer(("", port), NoCacheHandler).serve_forever()
