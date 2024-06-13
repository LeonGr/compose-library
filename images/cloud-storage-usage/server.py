import http.server
import socketserver
import subprocess
from dotenv import load_dotenv
import os
import json
import logging
from dataclasses import dataclass
import xml.etree.ElementTree as ET

PORT = 9393

@dataclass
class UsageRecord:
    total_bytes: int
    used_bytes: int

def get_env(name):
    load_dotenv()

    return os.getenv(name)


def get_webdav_usage_info(webdav_url, username, password) -> UsageRecord:
    xml_data = """
<?xml version="1.0" encoding="UTF-8" ?>
<D:propfind xmlns:D="DAV:">
<D:prop>
    <D:quota-available-bytes/>
    <D:quota-used-bytes/>
</D:prop>
</D:propfind>
    """

    response = subprocess.check_output(f"""
        curl --silent --user '{username}:{password}' --request PROPFIND {webdav_url} --max-time 10 \
            --data '{xml_data}' \
            --header 'Depth: 0'
        """,
        shell=True)

    usage_xml = response.decode().strip()

    root = ET.fromstring(usage_xml)
    namespaces = {'d': 'DAV:'}
    used_bytes = int(root.find('.//d:quota-used-bytes', namespaces).text)
    available_bytes = int(root.find('.//d:quota-available-bytes', namespaces).text)

    return UsageRecord(total_bytes=available_bytes + used_bytes, used_bytes=used_bytes)


def get_storagebox_usage_info(storagebox_url, username, password) -> UsageRecord:
    response = subprocess.check_output(f"""
        curl --silent --user '{username}:{password}' {storagebox_url} --max-time 10
              """, shell=True)

    raw_json = response.decode().strip()
    try:
        parsed = json.loads(raw_json)

        storagebox = parsed["storagebox"]
        usage_megabytes = storagebox["disk_usage"]
        total_megabytes = storagebox["disk_quota"]
        total_bytes = total_megabytes * 1000**2
        usage_bytes = usage_megabytes * 1000**2

        return UsageRecord(total_bytes=total_bytes, used_bytes=usage_bytes)
    except Exception:
        logging.warning(f"Could not get storagebox output, received:\n{raw_json}")
        raise


def get_storage_total_used_metric(storage_identifier, amount):
    return f"""cloud_storage_used{{identifier="{storage_identifier}"}} {amount}"""

def get_storage_total_free_metric(storage_identifier, amount):
    return f"""cloud_storage_free{{identifier="{storage_identifier}"}} {amount}"""


def get_metrics_message() -> str:
    ok_usage_messages = []
    ok_free_messages = []

    try:
        webdav_username = get_env("WEBDAV_USERNAME")
        webdav_password = get_env("WEBDAV_PASSWORD")
        webdav_url = get_env("WEBDAV_URL")

        webdav_usage_info = get_webdav_usage_info(webdav_url, webdav_username, webdav_password)

        webdav_usage = webdav_usage_info.used_bytes
        webdav_total = webdav_usage_info.total_bytes

        webdav_usage_message = get_storage_total_used_metric("webdav", webdav_usage)
        webdav_free_message = get_storage_total_free_metric("webdav", webdav_total - webdav_usage)

        ok_usage_messages.append(webdav_usage_message)
        ok_free_messages.append(webdav_free_message)
    except Exception as e:
        logging.error("Could not get webdav_usage_info", exc_info=e)

    try:
        storagebox_username = get_env("STORAGEBOX_USERNAME")
        storagebox_password = get_env("STORAGEBOX_PASSWORD")
        storagebox_url = get_env("STORAGEBOX_URL")

        storagebox_usage_info = get_storagebox_usage_info(
            storagebox_url, storagebox_username, storagebox_password)

        storagebox_usage = storagebox_usage_info.used_bytes
        storagebox_total = storagebox_usage_info.total_bytes

        storagebox_usage_message = get_storage_total_used_metric("storagebox", storagebox_usage)
        storagebox_free_message = get_storage_total_free_metric(
            "storagebox", storagebox_total - storagebox_usage)

        ok_usage_messages.append(storagebox_usage_message)
        ok_free_messages.append(storagebox_free_message)
    except Exception as e:
        logging.error("Could not get storagebox_usage_info", exc_info=e)

    output_message = ""

    if len(ok_usage_messages) > 0:
        output_message += "# TYPE cloud_storage_used gauge\n"

        for usage_message in ok_usage_messages:
            output_message += usage_message + "\n"

    if len(ok_free_messages) > 0:
        output_message += "# TYPE cloud_storage_free gauge\n"

        for free_message in ok_free_messages:
            output_message += free_message + "\n"

    return output_message


class PrometheusMetricsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        if self.path == "/metrics":
            message = get_metrics_message()
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

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
