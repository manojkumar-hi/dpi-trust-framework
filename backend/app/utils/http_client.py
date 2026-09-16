import http.client
import socket
import ssl
import ipaddress
import urllib.parse
from contextlib import closing

class HTTPClientError(Exception):
    pass

class SSRFSecurityError(HTTPClientError):
    pass

class SafeHTTPSConnection(http.client.HTTPSConnection):
    """
    An HTTPS connection that explicitly connects to a pre-resolved, safe IP address
    while preserving the original hostname for SNI and certificate validation.
    This protects against DNS rebinding.
    """
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

def is_safe_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            return False
        return True
    except ValueError:
        return False

def fetch_status_list_artifact(url: str, max_size_bytes: int = 2 * 1024 * 1024, timeout_sec: float = 5.0) -> bytes:
    """
    Fetches an external status list artifact with strict SSRF and size bounds.
    Returns the raw bytes of the response body.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise SSRFSecurityError("Only HTTPS URLs are allowed")
    
    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("Invalid URL hostname")
        
    port = parsed.port or 443
    
    # 1. Resolve and validate IP
    try:
        addrs = socket.getaddrinfo(hostname, port, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise HTTPClientError(f"DNS resolution failed") from e
        
    safe_ip = None
    for addr in addrs:
        ip = addr[4][0]
        if is_safe_ip(ip):
            safe_ip = ip
            break
            
    if not safe_ip:
        raise SSRFSecurityError("URL resolves to an unsafe or private IP address")
        
    # 2. Connect and fetch
    try:
        conn = SafeHTTPSConnection(hostname, safe_ip, timeout=timeout_sec)
        with closing(conn):
            path_query = parsed.path or "/"
            if parsed.query:
                path_query += f"?{parsed.query}"
            
            conn.request("GET", path_query, headers={"Host": hostname, "Connection": "close"})
            res = conn.getresponse()
            
            if res.status != 200:
                raise HTTPClientError(f"HTTP request failed with status {res.status}")
                
            # Content-Length check
            content_length = res.getheader('Content-Length')
            if content_length and int(content_length) > max_size_bytes:
                raise HTTPClientError("Response content length exceeds bounds")
                
            # Stream body
            chunks = []
            bytes_read = 0
            while True:
                chunk = res.read(8192)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > max_size_bytes:
                    raise HTTPClientError("Response body exceeded maximum allowed size")
                chunks.append(chunk)
                
            return b"".join(chunks)
    except SSRFSecurityError:
        raise
    except HTTPClientError:
        raise
    except Exception as e:
        raise HTTPClientError("HTTP request failed") from e

def fetch_json_artifact(url: str, max_size_bytes: int = 1048576, timeout_sec: float = 5.0) -> bytes:
    """
    Fetches an external JSON artifact (e.g. did.json) with strict SSRF and size bounds.
    Returns the raw bytes of the response body.
    """
    # Simply reuse the existing SSRF-safe implementation, adjusting max size to 1MB default
    return fetch_status_list_artifact(url, max_size_bytes=max_size_bytes, timeout_sec=timeout_sec)
