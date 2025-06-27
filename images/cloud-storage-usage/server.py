import http.server
import socketserver
import subprocess
from dotenv import load_dotenv
import os
import json
import logging
from dataclasses import dataclass
import xml.etree.ElementTree as ET
import requests

PORT = 9393
#  PORT = 9394

@dataclass
class UsageRecord:
    total_bytes: int
    used_bytes: int

class StorageUsageRequest:
    def __init__(self, name, url, credentials, send_request_function):
        self.name = name
        def execute():
            return send_request_function(url, credentials)

        self.execute = execute

def get_env(name):
    load_dotenv()

    return os.getenv(name)


def get_webdav_usage_info(webdav_url, credentials) -> UsageRecord:
    xml_data = """<?xml version="1.0" encoding="UTF-8" ?><D:propfind xmlns:D="DAV:"><D:prop><D:quota-available-bytes/><D:quota-used-bytes/></D:prop></D:propfind>"""

    headers = {
        'Depth': '0',
    }

    response = requests.request('PROPFIND', webdav_url, headers=headers, data=xml_data, auth=credentials, timeout=10)

    root = ET.fromstring(response.text)
    namespaces = {'d': 'DAV:'}
    used_bytes = int(root.find('.//d:quota-used-bytes', namespaces).text)
    available_bytes = int(root.find('.//d:quota-available-bytes', namespaces).text)

    return UsageRecord(total_bytes=available_bytes + used_bytes, used_bytes=used_bytes)


def get_storagebox_usage_info(storagebox_url, credentials) -> UsageRecord:
    (username, password) = credentials
    response = requests.get(f'{storagebox_url}', auth=(f'{username}', f'{password}'), timeout=10)

    parsed = response.json()

    storagebox = parsed["storagebox"]
    usage_megabytes = storagebox["disk_usage"]
    total_megabytes = storagebox["disk_quota"]

    total_bytes = total_megabytes * 1000**2
    usage_bytes = usage_megabytes * 1000**2

    return UsageRecord(total_bytes=total_bytes, used_bytes=usage_bytes)


def get_storage_total_used_metric(storage_identifier, amount):
    return f"""cloud_storage_used{{identifier="{storage_identifier}"}} {amount}"""

def get_storage_total_free_metric(storage_identifier, amount):
    return f"""cloud_storage_free{{identifier="{storage_identifier}"}} {amount}"""


def get_metrics_message() -> str:
    ok_usage_messages = []
    ok_free_messages = []

    requests = [
        #  StorageUsageRequest("TransIP Stack", get_env("STACK_URL"), get_env("STACK_USERNAME"), get_env("STACK_PASSWORD"), get_webdav_usage_info),
        StorageUsageRequest("Hetzner Storagebox", get_env("STORAGEBOX_URL"), (get_env("STORAGEBOX_USERNAME"), get_env("STORAGEBOX_PASSWORD")), get_storagebox_usage_info),
        StorageUsageRequest("Infomaniak kDrive", get_env("KDRIVE_URL"), (get_env("KDRIVE_USERNAME"), get_env("KDRIVE_PASSWORD")), get_webdav_usage_info),
    ]

    for request in requests:
        try:
            usage_info = request.execute()

            used_bytes = usage_info.used_bytes
            total_bytes = usage_info.total_bytes

            usage_message = get_storage_total_used_metric(request.name, used_bytes)
            free_message = get_storage_total_free_metric(request.name, total_bytes - used_bytes)

            ok_usage_messages.append(usage_message)
            ok_free_messages.append(free_message)
        except Exception as e:
            logging.error("Could not get " + request.name, exc_info=e)


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
