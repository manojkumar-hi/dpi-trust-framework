import http.client
import socket
import ssl
import ipaddress
from urllib.parse import urlparse

class SafeHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, ip_address, **kwargs):
        super().__init__(host, **kwargs)
        self.ip_address = ip_address
        
    def connect(self):
        sock = socket.create_connection((self.ip_address, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
        context = self._context or ssl.create_default_context()
        self.sock = context.wrap_socket(sock, server_hostname=self.host)

def is_safe_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            return False
        return True
    except ValueError:
        return False

def safe_fetch(url):
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS allowed")
    
    hostname = parsed.hostname
    port = parsed.port or 443
    
    addrs = socket.getaddrinfo(hostname, port, socket.AF_INET, socket.SOCK_STREAM)
    safe_ip = None
    for addr in addrs:
        ip = addr[4][0]
        if is_safe_ip(ip):
            safe_ip = ip
            break
            
    if not safe_ip:
        raise ValueError("No safe IP found")
        
    conn = SafeHTTPSConnection(hostname, safe_ip, timeout=5.0)
    conn.request("GET", parsed.path or "/")
    res = conn.getresponse()
    print("Status:", res.status)
    body = res.read(1024)
    print("Body preview:", body[:50])

if __name__ == "__main__":
    safe_fetch("https://example.com")
