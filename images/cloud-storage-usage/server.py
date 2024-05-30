import http.server
import socketserver
import subprocess
from dotenv import load_dotenv
import os
import json
import logging

PORT = 9393


def get_env(name):
    load_dotenv()

    return os.getenv(name)


def get_webdav_space_used(webdav_url, username, password):
    xml_data = """
<?xml version="1.0" encoding="UTF-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
    <D:quota-used-bytes/>
</D:prop>
</D:propfind>
    """

    response = subprocess.check_output(f"""
        curl --silent --user '{username}:{password}' --request PROPFIND {webdav_url} --max-time 10 \
            --data '{xml_data}' \
            --header 'Depth: 0' \
            | xmllint \
                --xpath '//*[local-name()="quota-used-bytes"]/text()' -
              """, shell=True)

    usage = response.decode().strip()
    return usage


def get_storagebox_space_used(storagebox_url, username, password):
    response = subprocess.check_output(f"""
        curl --silent --user '{username}:{password}' {storagebox_url} --max-time 10
              """, shell=True)

    raw_json = response.decode().strip()
    try:
        parsed = json.loads(raw_json)
        storagebox = parsed["storagebox"]
        usage = storagebox["disk_usage"]
    except Exception:
        logging.warning(f"Could not get storagebox output, received:\n{raw_json}")
        raise

    return usage


class PrometheusMetricsHandler(http.server.BaseHTTPRequestHandler):
    def get_webdav_space_used(self):
        username = get_env("WEBDAV_USERNAME")
        password = get_env("WEBDAV_PASSWORD")
        webdav_url = get_env("WEBDAV_URL")
        webdav_usage = get_webdav_space_used(webdav_url, username, password)

        return f"""# HELP webdav_total_used Total bytes used from STACK
# TYPE webdav_total_used gauge
webdav_total_used {webdav_usage}
    """

    def get_storagebox_space_used(self):
        username = get_env("STORAGEBOX_USERNAME")
        password = get_env("STORAGEBOX_PASSWORD")
        storagebox_url = get_env("STORAGEBOX_URL")
        storagebox_usage = int(get_storagebox_space_used(storagebox_url, username, password)) * (1024**2)

        return f"""# HELP storagebox_total_used Total bytes used from STACK
# TYPE storagebox_total_used gauge
storagebox_total_used {storagebox_usage}
    """

    def do_GET(self):
        self.send_response(200)
        if self.path == "/metrics":
            webdav_usage_message = self.get_webdav_space_used()
            storagebox_usage_message = self.get_storagebox_space_used()
            message = f"""{webdav_usage_message}
{storagebox_usage_message}
    """
            self.send_header('Content-type', 'text/plain')
        else:
            message = "cloud-storage-usage: see <a href=\"/metrics\">/metrics</a>"
            self.send_header('Content-type', 'text/html')

        self.end_headers()

        self.wfile.write(bytes(message, "utf8"))


if __name__ == "__main__":
    httpd = socketserver.TCPServer(("", PORT), PrometheusMetricsHandler)
    logging.basicConfig(level=logging.DEBUG)
    logging.info(f"serving at port {PORT}")

    httpd.serve_forever()
