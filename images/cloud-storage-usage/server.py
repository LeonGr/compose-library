import http.server
import socketserver
import subprocess
from dotenv import load_dotenv
import os

PORT = 9393

def get_env(name):
    load_dotenv()

    return os.getenv(name)


class PrometheusMetricsHandler(http.server.BaseHTTPRequestHandler):
    def get_space_used(self):
        password = get_env("PASSWORD")
        webdav_url = get_env("WEBDAV_URL")

        xml_data = """
<?xml version="1.0" encoding="UTF-8" ?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:quota-used-bytes/>
    </D:prop>
</D:propfind>
        """


        response = subprocess.check_output(f"""
            curl --silent --user leongr:{password} --request PROPFIND {webdav_url} \
                --data '{xml_data}' \
                --header 'Depth: 0' \
                | xmllint \
                    --xpath '//*[local-name()="quota-used-bytes"]/text()' -
                  """, shell=True)

        usage = response.decode().strip()
        return f"""# HELP webdav_total_used Total bytes used from STACK
# TYPE webdav_total_used gauge
webdav_total_used {usage}
    """

    def do_GET(self):
        if self.path == "/metrics":
            message = self.get_space_used()
        else:
            message = "Hello World!"

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

        self.wfile.write(bytes(message, "utf8"))

httpd = socketserver.TCPServer(("", PORT), PrometheusMetricsHandler)
print("serving at port", PORT)

httpd.serve_forever()
