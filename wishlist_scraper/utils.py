import os.path
import re
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


def qualified_url(response, url):
    response_url = urlparse(response.url)

    if re.search('^[a-z]+://', url):
        return url
    elif url.startswith('/'):
        return '{}://{}/{}'.format(
            response_url.scheme, response_url.netloc, url)
    else:
        return '{}://{}{}/{}'.format(
            response_url.scheme, response_url.netloc,
            os.path.dirname(response_url.path), url)
