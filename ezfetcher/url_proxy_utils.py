#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2015 Rasmus Sorensen, rasmusscholer@gmail.com <scholer.github.io>

##    This program is free software: you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation, either version 3 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License

# pylint: disable=C0103,W0142


import re
from urllib.parse import urlparse



def proxy_url_rewrite(url, proxy_url_fmt):
    """
    Apply proxy rewrite format to url using proxy_url_format.
    Rewritten with:
    proxy_url_fmt.format(**parsed._asdict())
    """
    print("(proxy_url_rewrite) url:", url)
    if url_is_proxied(url, proxy_url_fmt):
        print("Url is already proxied...")
        return url
    parsed = urlparse(url)
    if not parsed.netloc:
        url = "http://"+url
        parsed = urlparse(url)
    print("Parsed url:", parsed._asdict())
    rewritten = proxy_url_fmt.format(**parsed._asdict())
    print("Rewritten URL: ", rewritten)
    return rewritten


def url_is_proxied(url, proxy_url_fmt):
    """
    Returns true if url includes the ezproxy part.
    General structure of a URL: scheme://netloc/path;params?query#fragment
    <scheme>://<netloc><path>
    Format rewrite might look like:
        http://{netloc}.ez.statsbiblioteket.dk:2048/{path}?{query}
    E.g.
        http://www.nature.com/nature/journal/v440/n7082/full/nature04586.html
     => http://www.nature.com.ez.statsbiblioteket.dk:2048/nature/journal/v440/n7082/full/nature04586.html?

    """
    # We only consider the scheme://netloc/path part:
    url = url.split(";")[0].split("#")[0]
    proxy_url_fmt = proxy_url_fmt.split(";")[0].split("#")[0]
    wildcards = dict.fromkeys('scheme netloc path params query fragment'.split(), '.*')
    regex = proxy_url_fmt.format(**wildcards)
    if re.match(regex, url):
        return True
    else:
        return False
