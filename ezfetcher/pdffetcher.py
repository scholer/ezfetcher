#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##  Copyright (c) 2015 Rasmus Sorensen <scholer.github.io> rasmusscholer@gmail.com

##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU General Public License as published by
##  the Free Software Foundation, either version 3 of the License, or
##  (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##  GNU General Public License for more details.
##
##  You should have received a copy of the GNU General Public License

# pylint: disable=W0142,W0212,C0103

"""

Fetch PDF from web page using ezproxy.

"""


import os
#import tempfile
import webbrowser
import re
import yaml
import requests
import argparse
#import urllib
from urllib.parse import urlparse, urljoin

# Function to extract cookies from chrome:
from .lib.cookiesnatcher.chrome_extract import get_chrome_cookies
from .utils import credentials_prompt, get_config, load_config, save_config
from .url_proxy_utils import url_is_proxied, proxy_url_rewrite
from .errors import LoginRedirectException


def default_selector_prompt(cands):
    """
    Default user prompt function to select a candidate from a list of choices,
    e.g. select the correct PDF link from a list of possible pdf files.
    """
    prompt = "Multiple PDF href candidates found. Please select one:"
    prompt += "\n".join("{}.\t{}".format(i, cand) for i, cand in enumerate(cands))
    idx = input(prompt)
    return idx



def request(url):
    """
    Get request object, doing url rewrite and passing in cookies.
    """
    config = get_config()
    url = proxy_url_rewrite(url, config['proxy_url_fmt'])
    return requests.get(url, cookies=config.get('cookies'))



def get_pdf_candidates(html, regex=None):
    """
    Get pdf hrefs from a html document.
    """
    if regex is None:
        regex = r'<a .*?href="([^\s]+\.pdf)"'
    prog = re.compile(regex)
    return prog.findall(html)

def get_pdf_href(html, pdf_href_regex, selector_callback=None):
    """
    Extracts pdf url from html text.
    The ''selector_callback'' is a callback function to select which
    pdf link to use in case there is multiple candidates.
    """
    if selector_callback is None:
        selector_callback = default_selector_prompt
    cands = get_pdf_candidates(html, pdf_href_regex)
    if not cands:
        return None
    if len(cands) == 1:
        index = 0
    else:
        index = selector_callback(cands)
    print("Returning ", cands[index])
    return cands[index]


def resolve_pdf_href(html_url, pdf_href):
    """ Reference function, follows pdf_href from a html_url. """
    # Note: Needs to be updated if pages make use of the BASE element.
    return urljoin(html_url, pdf_href)



def save_file(response, filepath):
    """
    Save the content from a response to filepath.
    If filepath is a directory, save to a file in filepath,
    using the basename from the response URL.
    """
    if os.path.isdir(filepath):
        fname = urlparse(response.url).path.rsplit('/', 1)[-1]
        filepath = os.path.join(filepath, fname)
    elif not os.path.isdir(os.path.dirname(filepath)):
        raise ValueError("filepath in non-existing directory: %s " % filepath)
    print("Saving %s to file %s" % (response.url, filepath))
    with open(filepath, 'wb') as fd:
        fd.write(response.content) # maybe iter_content() ?
    return filepath


def get_pdf_response(url, session, pdf_href_regex, recursions=4):
    """
    Traverse url to get a PDF.
    """
    if recursions < 1:
        print("Recursions maxed out, aborting... - ", recursions)
        return None
    r = session.get(url)  # response object
    # There might be redirects, even for pdf requests, e.g. if the cookies has expired.
    # You can usually check this from the history..
    # r.history
    if urlparse(r.url).netloc != urlparse(url).netloc:
        # We've shifted domain. Should only happen if login is invalid
        raise LoginRedirectException("Redirected to %s" % urlparse(r.url).netloc)
    if 'html' in r.headers['Content-Type']:
        print("Response is html, trying to extract pdf url...")
        pdf_href = get_pdf_href(html=r.text, pdf_href_regex=pdf_href_regex)
        if not pdf_href:
            print("No pdf href found in html.")
            return None
        url = resolve_pdf_href(url, pdf_href)
        print("New PDF URL:", url)
        return get_pdf_response(url, session, pdf_href_regex, recursions=recursions-1)
    else:
        return r



def fetch_pdf(url, **kwargs):
    """
    Fetch pdf from url.
    """
    print("(fetch_pdf) url:", url)
    print("kwargs: ", kwargs)
    config = get_config()
    print("config:", config)
    config.update(kwargs)
    print("config:", config)
    url = proxy_url_rewrite(url, config['proxy_url_fmt'])
    cookies = config.get('cookies', {})
    cookies_domain = config.get('cookie_domain')
    if 'cookie_keys' in config and cookies_domain:
        cookie_keys = config['cookie_keys']
        filter_fun = lambda key: key in cookie_keys
        browser_cookies = get_chrome_cookies(cookies_domain, filter_fun)
        print("Browser cookies:", browser_cookies)
        cookies.update(browser_cookies)
    session = requests.Session()
    session.cookies.update(cookies)
    #r = request.get(url, cookies=config.get('cookies'))
    pdf_href_regex = config.get('pdf_href_regex')
    response = get_pdf_response(url, session, pdf_href_regex)
    print("Response with content type:", response.headers['Content-Type'])
    # Uh, maybe some recursion here?
    # We have a pdf in our response:
    savedir = os.path.expanduser(config.get('download_dir', os.path.join('~', 'Downloads')))
    filepath = save_file(response, savedir) # This may overwrite file if already exist..
    if config.get('open_pdf'):
        webbrowser.open(filepath)
    return filepath





def get_argparser():
    """ Get argument parser. """
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help="The URL to download pdf from.")
    parser.add_argument('--download_dir', help="Download pdf to this directory.")
    parser.add_argument('--proxy_url_fmt',
                        help="How to proxy rewrite the url. E.g. 'http://{netloc}.lib.university.edu/{path}")
    parser.add_argument('--open_pdf', action="store_true", default=None, help="Open pdf after download.")
    parser.add_argument('--no-open_pdf', action="store_false", dest="open_pdf", help="Do not open pdf after download.")
    parser.add_argument('--cookie_keys', nargs='*', metavar="KEY", help="Download pdf to this directory.")
    parser.add_argument('--cookie_domain', help="Domain to extract browser cookies for.")
    return parser


def get_args(parser=None):
    """ Get args from command line. """
    if parser is None:
        parser = get_argparser()
    return parser.parse_args()


def main():
    """ Invoked from command line or tests... """
    argns = get_args()
    print("argns.__dict__:", argns.__dict__)
    kwargs = {k: v for k, v in argns.__dict__.items() if v is not None}
    url = kwargs.pop('url')
    fetch_pdf(url, **kwargs)



def test():
    """ Simple test. """
    url = "http://www.nature.com.ez.statsbiblioteket.dk:2048/nature/journal/v440/n7082/full/nature04586.html"
    pdfhref = "/nature/journal/v440/n7082/pdf/nature04586.pdf"
    urljoin(url, pdfhref)
    urlparse(url)


if __name__ == '__main__':
    main()
