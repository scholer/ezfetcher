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

import os
from requests import Session
from urllib.parse import urlparse
import yaml
import pickle
#from six import string_types
import logging
logger = logging.getLogger(__name__)

from .login_adaptors import login_adaptors, login_domains
from .url_proxy_utils import url_is_proxied, proxy_url_rewrite
from .utils import save_config, load_config

try:
    from .lib.cookiesnatcher.chrome_extract import get_chrome_cookies
except ImportError as e:
    logger.warning("ezfetcher.ezclient: %s - cookie_snatch_from will not function.", e)

__version__ = 0.1



def save_cookies(fd, cookiejar):
    """ Save cookiejar to file. """
    pickle.dump(cookiejar, fd)

def load_cookies(fd):
    """ Load cookies from file. """
    return pickle.load(fd)


class EzClient(object):
    """
    A special session object able to route requests through a configured ezproxy.

    """

    def __init__(self, config=None, headers=None, cookies=None, config_filepath=None):
        """
        Args headers and cookies overrides ezclient_headers/cookies
        found in config.
        """
        self.session = Session()
        # Init config:
        self.config = config if config is not None else {}
        self.config_filepath = config_filepath
        if self.config_filepath:
            self.load_config()
        # Inject headers in session:
        if self.config.get('ezclient_headers'):
            self.session.headers.update(self.config['ezclient_headers'])
        if headers:
            self.session.headers.update(headers)
        # Inject cookies in session: Note that cookies is a RequestsCookieJar, not dict.
        #self.cookies_filename = cookies_filepath or config.get('cookies_filepath')
        # cookies_filepath is now *only* present in config.
        if self.cookies_filepath:
            self.load_cookies()
        if self.config.get('ezclient_cookies'):
            self.session.cookies.update(self.config['ezclient_cookies'])
        if cookies:
            self.session.cookies.update(cookies)
        # EzProxy Login adaptor:
        login_adaptor_name = config.get('ezclient_login_adaptor')
        if login_adaptor_name:
            self.login_adaptor = login_adaptors[login_adaptor_name]
            self.login_hostname = login_domains[login_adaptor_name]
        else:
            self.login_adaptor = None
            self.login_hostname = []
        if config.get('ezclient_useragent'):
            self.session.headers['User-Agent'] = config['ezclient_useragent']

    @property
    def headers(self):
        """ Return session headers. """
        return self.session.headers
    @property
    def cookies(self):
        """ Return session cookies. """
        return self.session.cookies
    @property
    def cookies_filepath(self):
        """ Returns cookie_filepath entry from config. """
        path = self.config.get('cookies_filepath')
        if path:
            return os.path.expanduser(os.path.normpath(path))
    @cookies_filepath.setter
    def cookies_filepath(self, cookies_filepath):
        """ Sets cookie_filepath entry in config. (ONLY if cookies_filepath has a non-null value). """
        if cookies_filepath:
            self.config['cookies_filepath'] = cookies_filepath

    def save_config(self, filepath=None):
        """ Save config to file. """
        if filepath is None:
            filepath = self.config_filepath
        try:
            save_config(self.config, filepath)
        except FileNotFoundError:
            logger.error("Could not save config to file: %s", filepath)
        self.config_filepath = filepath

    def load_config(self, filepath=None):
        """ Load config from file. """
        if filepath is None:
            filepath = self.config_filepath
        try:
            config = load_config(filepath)
        except FileNotFoundError:
            logger.error("Could not load config from file: %s", filepath)
        self.config.update(config)
        self.config_filepath = filepath
        return config


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
        if cookie_keys and cookies_domain:
            filter_fun = lambda key: key in cookie_keys
            browser_cookies = get_chrome_cookies(cookies_domain, filter_fun)
            if browser_cookies:
                self.session.cookies.update(browser_cookies)
                logger.info("%s cookies snatched from browser and added to EzClient.", len(browser_cookies))
                if self.config.get('cookies_persist_after_login', True):
                    self.save_cookies()
            return browser_cookies
        else:
            logger.warning("cookies_key and cookies_domain must be specified, either as method args or in the config.")


    def simulate_login_post(self, login_url=None):
        """ Actively simulate a login. """
        r = self.login_adaptor(self.session, login_url)
        if r and self.config.get('cookies_persist_after_login', True):
            self.save_cookies()
        return r


    def login_after_redirect(self, response, url_is_loginpage=True):
        """
        If you've received a response that requires login.
        If url_is_loginpage is set to False, then the URL will
        be used to request the first login. Otherwise, it is assumed
        that you have already been forwarded to the login page
        (entry point where adaptor takes over).
        """
        r = self.login_adaptor(self.session, response.url, url_is_loginpage)
        if r and self.config.get('cookies_persist_after_login', True):
            self.save_cookies()
        return r

    def ensure_proxy(self, url):
        """ Determine if proxy needs to be applied to url. """
        if self.use_proxy(url) and not url_is_proxied(url, self.config['proxy_url_fmt']):
            url = proxy_url_rewrite(url, self.config['proxy_url_fmt'])
        return url

    def get(self, url):
        """ Get url """
        url = self.ensure_proxy(url)
        logger.info("Getting %s", url)
        r = self.session.get(url)
        logger.debug("- %s bytes obtained from %s", len(r.content), url)
        parsed = urlparse(r.url)
        if parsed.netloc in self.login_hostname:
            print("Redirect to login page detected, attempting login...")
            r = self.login_after_redirect(r)
        return r

    def get_session_state(self):
        """
        Returns a dict that should be usable to persist/recreate session state.
        A few refs/discussions:
        * http://sharats.me/serializing-python-requests-session-objects-for-fun-and-profit.html
        * http://stackoverflow.com/questions/13030095/how-to-save-requests-python-cookies-to-a-file
        * https://github.com/kennethreitz/requests/issues/1488
        How to persist and load session (attributes)?

        Session.cookies is a RequestsCookieJar object. The dict representation is not complete,
        so it is better to save it either as an independent file, e.g. with
        cookielib.

        """
        pass


    def save_cookies(self, filepath=None):
        """ Saves session cookies """
        filepath = filepath or self.cookies_filepath
        if not filepath:
            logger.error("Could not save cookies, filepath/<type> is %s/%s", filepath, type(filepath))
            return
        filepath = os.path.expanduser(filepath)
        logger.info("Saving cookies to file: %s", filepath)
        try:
            with open(filepath, 'wb') as fd:
                save_cookies(fd, self.cookies)
            self.cookies_filepath = filepath
        except FileNotFoundError:
            logger.error("Could not save cookies to file: %s", filepath)

    def load_cookies(self, filepath=None):
        """ Saves session cookies """
        filepath = filepath or self.cookies_filepath
        if not filepath:
            logger.warning("Could not save cookies, filepath/<type> is %s/%s", filepath, type(filepath))
            return
        filepath = os.path.expanduser(filepath)
        logger.info("Loading cookies from file: %s", filepath)
        try:
            with open(filepath, 'rb') as fd:
                cookiejar = load_cookies(fd)
                try:
                    self.cookies.update(cookiejar)
                except AttributeError:
                    # self.cookie does not support update, it might be a http.cookiejar.CookieJar object
                    self.cookies = cookiejar
            self.cookies_filepath = filepath
        except FileNotFoundError:
            logger.error("Could not load cookies from file: %s", filepath)


def test():
    cfg = """
proxy_login_adaptor: AU_lib
proxy_url_fmt: https://{netloc}.ez.statsbiblioteket.dk:2048/{path}
ezclient_useragent: Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36
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
