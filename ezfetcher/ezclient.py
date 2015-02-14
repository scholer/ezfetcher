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


"""

Module to download content through an Ez proxy.


How to hook this up?
-

How to do auth/login with the ezproxy?
* Snatch cookie from existing ezproxy session, e.g. from Google Chrome.
* Simulate form submission?
* OAuth (if that is supported)?

How does ezproxy auth work? (Examples)
 *  The ezproxy server has just one cookie with a token.
    The key may vary, e.g. 'sbez' for ez.statsbiblioteket.dk or 'ezproxyezpprod1' (for hul.harvard.edu).
 *  Some login servers use the simplesaml php module, which always yield the same cookie:
    SimpleSAMLAuthToken
 *


Simulating form submission:
This should actually be quite easy, just post a request to the login URL with correct input,
and you should be able to get a token from that.
The input fields are usually simply "username" and "password".

Not sure if I have to spoof the user-agent?
* User-agent strings:
    Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36
* Update with:
    headers = {'User-Agent': 'Mozilla/5.0'}

Refs:

SimpleSAML PHP (SSP) and EzProxy:
* http://www.oclc.org/support/documentation/ezproxy/usr/shibboleth.htm
* http://www.wayf.dk/en/services/connection-technology-for-services/161



"""

from requests import Session
from urllib.parse import urlparse
import yaml

from .login_adaptors import login_adaptors, login_domains
from .url_proxy_utils import url_is_proxied, proxy_url_rewrite
try:
    from .lib.cookiesnatcher.chrome_extract import get_chrome_cookies
except ImportError as e:
    print("ImportError:", e)



class EzClient(object):
    """
    A special session object able to route requests through a configured ezproxy.

    """

    def __init__(self, config=None, headers=None):
        self.session = Session()
        self.config = config or {}
        if headers:
            self.session.headers.update(headers)
        login_adaptor_name = config.get('proxy_login_adaptor')
        if login_adaptor_name:
            self.login_adaptor = login_adaptors[login_adaptor_name]
            self.login_hostname = login_domains[login_adaptor_name]
        else:
            self.login_adaptor = None
            self.login_hostname = []
        if config.get('user-agent'):
            self.session.headers['User-Agent'] = config['user-agent']

    def use_proxy(self, url):
        """ Whether to use proxy. """
        parsed = urlparse(url)
        if self.config.get('proxy_enabled_domains') \
            and parsed.netloc in self.config.get('proxy_enabled_domains'):
            # If you have a list of enabled proxy domains, and it is in that list:
            return 'proxy_url_fmt' in self.config
        if self.config.get('proxy_ignore_domains') \
            and parsed.netloc in self.config.get('proxy_ignore_domains'):
            # Specifically return False in this case:
            return False
        return 'proxy_url_fmt' in self.config


    def snatch_chrome_cookie(self, cookie_keys=None, cookies_domain=None):
        """ Update cookies from Chrome's cookie database. """
        cookie_keys = cookie_keys or self.config['cookie_keys']
        cookies_domain = cookies_domain or self.config['cookies_domain']
        filter_fun = lambda key: key in cookie_keys
        browser_cookies = get_chrome_cookies(cookies_domain, filter_fun)
        self.session.cookies.update(browser_cookies)
        return browser_cookies


    def simulate_login_post(self, login_url=None):
        """ Actively simulate a login. """
        return self.login_adaptor(self.session, login_url)


    def login_after_redirect(self, response, url_is_loginpage=True):
        """
        If you've received a response that requires login.
        If url_is_loginpage is set to False, then the URL will
        be used to request the first login. Otherwise, it is assumed
        that you have already been forwarded to the login page
        (entry point where adaptor takes over).
        """
        r = self.login_adaptor(self.session, response.url, url_is_loginpage)
        return r

    def ensure_proxy(self, url):
        """ Determine if proxy needs to be applied to url. """
        if self.use_proxy(url) and not url_is_proxied(url, self.config['proxy_url_fmt']):
            url = proxy_url_rewrite(url, self.config['proxy_url_fmt'])
        return url

    def get(self, url):
        """ Get url """
        url = self.ensure_proxy(url)
        r = self.session.get(url)
        parsed = urlparse(r.url)
        if parsed.netloc in self.login_hostname:
            print("Redirect to login page detected, attempting login...")
            r = self.login_after_redirect(r)
        return r




def test():
    cfg = """
proxy_login_adaptor: AU_lib
proxy_url_fmt: http://{netloc}.ez.statsbiblioteket.dk:2048/{path}
user-agent: Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36
"""
    config = yaml.load(cfg)
    client = EzClient(config)

    # test_url = "http://www.nature.com.ez.statsbiblioteket.dk:2048/nature/journal/v440/n7082/full/nature04586.html"
    # .ez.statsbiblioteket.dk:2048
    test_url = "http://www.nature.com/nature/journal/v440/n7082/full/nature04586.html"

    res = client.get(test_url)
    return res


if __name__ == '__main__':
    test()
