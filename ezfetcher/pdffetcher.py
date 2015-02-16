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
#import yaml
#import requests
import argparse
#import urllib
from urllib.parse import urlparse, urljoin
#from six import string_types
import logging
logger = logging.getLogger(__name__)



# Function to extract cookies from chrome:
#try:
#    from .lib.cookiesnatcher.chrome_extract import get_chrome_cookies
#except ImportError as e:
#    logger.warning("ezfetcher.pdffetcher: %s - cookie_snatch_from will not function.", e)
from .utils import get_config, init_logging
#from .url_proxy_utils import proxy_url_rewrite
#from .errors import LoginRedirectException
from .ezclient import EzClient


def default_selector_prompt(cands):
    """
    Default user prompt function to select a candidate from a list of choices,
    e.g. select the correct PDF link from a list of possible pdf files.
    """
    prompt = "\nMultiple PDF href candidates found. Please select one:\n"
    prompt += "\n".join("    {}:  {}".format(i, cand) for i, cand in enumerate(cands)) + "\n   "
    idx = input(prompt)
    return idx



#def request(url):
#    """
#    Get request object, doing url rewrite and passing in cookies.
#    """
#    config = get_config()
#    url = proxy_url_rewrite(url, config['proxy_url_fmt'])
#    return requests.get(url, cookies=config.get('cookies'))



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
    # Cast to set to make unique:
    cands = set(get_pdf_candidates(html, pdf_href_regex))
    cands = sorted(cands)
    if not cands:
        return None
    if len(cands) == 1:
        index = 0
    else:
        index = int(selector_callback(cands))
    #logger.info("Returning cand # %s: %s", index, cands[index])
    print("Returning cand # %s: %s" % (index, cands[index]))
    return cands[index]


def resolve_pdf_href(html_url, pdf_href):
    """ Reference function, follows pdf_href from a html_url. """
    # Note: Needs to be updated if pages make use of the BASE element.
    return urljoin(html_url, pdf_href)



def save_file(response, filepath, ensure_unique=True):
    """
    Save the content from <response> to <filepath>.
    If filepath is a directory, save to a file in filepath,
    using the basename from the response URL.
    If <ensure_unique> is True, existing files will not be overwritten.
    Instead, a new, unique, filename is generated. If this fails,

    """
    if os.path.isdir(filepath):
        fname = urlparse(response.url).path.rsplit('/', 1)[-1]
        filepath = os.path.join(filepath, fname)
    elif not os.path.isdir(os.path.dirname(filepath)):
        raise ValueError("filepath in non-existing directory: %s " % filepath)
    if ensure_unique:
        filepath = get_unique_filename(filepath)
    print("Saving %s to file %s" % (response.url, filepath))
    with open(filepath, 'wb') as fd:
        fd.write(response.content) # maybe iter_content() ?
    return filepath

def get_unique_filename(filename, max_iterations=1000, unique_fmt="{fnroot} ({i}){ext}"):
    """ Returns a unique filename based on <filename> and unique_fmt. """
    if not os.path.exists(filename):
        return filename
    fnroot, ext = os.path.splitext(filename)
    logging.debug("%s already exists; Making new using fnroot=%s, ext=%s, unique_fmt=%s",
                  filename, fnroot, ext, unique_fmt)
    for i in range(1, max_iterations):
        fpath = unique_fmt.format(fnroot=fnroot, i=i, ext=ext)
        if not os.path.exists(fpath):
            return fpath
    raise FileExistsError("%s already exists (an so does %s similarly-named files)" % (filename, max_iterations))



def get_pdf_response(url, session, pdf_href_regex, recursions=4, r=None):
    """
    Traverse url and responses recursively to get a PDF.
    """
    if recursions < 1:
        print("Recursions maxed out, aborting... - ", recursions)
        return None
    if r is None:
        r = session.get(url)  # response object
    # There might be redirects, even for pdf requests, e.g. if the cookies has expired.
    # You can usually check this from the history..
    # r.history
    #if urlparse(r.url).netloc != urlparse(url).netloc:
    #    # We've shifted domain. Should only happen if login is invalid
    #    # Edit: No; ezclient is in charge of proxy driven url rewriting.
    #    raise LoginRedirectException("Redirected to %s" % urlparse(r.url).netloc)
    if 'html' in r.headers['Content-Type']:
        print("Response is html, trying to extract pdf url...")
        pdf_href = get_pdf_href(html=r.text, pdf_href_regex=pdf_href_regex)
        if not pdf_href:
            print("No pdf href found in html.")
            return None
        url = resolve_pdf_href(url, pdf_href)
        print("New PDF URL:", url)
        # Recurse:
        return get_pdf_response(url, session, pdf_href_regex, recursions=recursions-1)
    else:
        # Assume we have a pdf:
        return r



def fetch_pdf(url, config, ezclient=None, headers=None, cookies=None, r=None):
    """
    Fetch pdf from url.
    You can provide *either* a client to use, OR headers/cookies OR neither.
    But headers/cookies will not be used if client is given.
    """
    print("(fetch_pdf) url:", url)
    # When using ezclient, proxy_url_rewrite is automatically applied:
    #url = proxy_url_rewrite(url, config['proxy_url_fmt'])
    #cookies = cookies or {}
    #if config.get('cookies_snatch_from'):
    #    cookies_domain = config.get('cookie_snatch_domain')
    #    cookie_keys = config.get('cookie_snatch_keys')
    #    if cookie_keys and cookies_domain:
    #        filter_fun = lambda key: key in cookie_keys
    #        browser_cookies = get_chrome_cookies(cookies_domain, filter_fun)
    #        print("Browser cookies:", browser_cookies)
    #        cookies.update(browser_cookies)

    if ezclient is None:
        ezclient = EzClient(config, headers=headers, cookies=cookies)
        if config.get('cookies_snatch_from'):
            ezclient.snatch_chrome_cookie()

    pdf_href_regex = config.get('pdf_href_regex')
    # Pass in existing response if you already have it:
    response = get_pdf_response(url, ezclient, pdf_href_regex, r=r)

    print("Response with content type:", response.headers['Content-Type'])
    # We have a pdf in our response:
    if response and response.content:
        logger.info("Response with %s bytes obtained from %s", len(response.content), response.url)
        logger.info("config.get('pdf_download_dir'): %s", config.get('pdf_download_dir'))
        savedir = os.path.expanduser(config.get('pdf_download_dir', os.path.join('~', 'Downloads')))
        savedir = os.path.normpath(savedir)
        filepath = save_file(response, savedir) # This may overwrite file if already exist..
        if config.get('pdf_open_after_download'):
            webbrowser.open(filepath)
        return filepath
    logger.info("Response from %s is: %s", response.url, response)




def get_argparser():
    """ Get argument parser. """
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help="The URL to download pdf from.")
    parser.add_argument('--pdf_download_dir', help="Download pdf to this directory.")
    parser.add_argument('--proxy_url_fmt',
                        help="How to proxy rewrite the url. E.g. 'http://{netloc}.lib.university.edu/{path}")
    parser.add_argument('--open_pdf', dest='pdf_open_after_download', action="store_true", default=None,
                        help="Open pdf after download.")
    parser.add_argument('--no-open_pdf', action="store_false", dest="pdf_open_after_download",
                        help="Do not open pdf after download.")
    parser.add_argument('--cookies_snatch_from', help="Snatch cookies from this browser (only Chrome supported).")
    parser.add_argument('--cookie_snatch_keys', nargs='*', metavar="KEY", help="Download pdf to this directory.")
    parser.add_argument('--cookie_snatch_domain', help="Domain to extract browser cookies for.")

    parser.add_argument('--configfile', help="Load this config file.")

    # testing and logging config:
    parser.add_argument('--loglevel', help="Logging level.")
    parser.add_argument('--testing', action="store_true", help="Enable testing mode.")

    return parser


def get_args(parser=None, argv=None):
    """ Get args from command line. """
    if parser is None:
        parser = get_argparser()
    return parser.parse_args(argv)


def main(argv=None, extras=None):
    """ Invoked from command line or tests... """
    argns = get_args(None, argv) # get_args(parser, argv)
    print("argns.__dict__:", argns.__dict__)
    kwargs = {k: v for k, v in argns.__dict__.items() if v is not None}
    if extras:
        kwargs.update(extras)
    url = kwargs.pop('url')
    print("kwargs: ", kwargs)
    config = get_config(kwargs, kwargs.pop('configfile', None))
    print("config: ", config)
    init_logging(kwargs)

    if url == 'test':
        test(kwargs)
        return

    fetch_pdf(url, config)




def test(args=None):
    """ Simple test. """
    if args is None:
        #configfile = os.path.join(os.path.realpath(__file__), 'cfg', 'config_example.yaml')
        #args = {'configfile': configfile}
        #config =
        args = {}
    url = "http://www.nature.com/nature/journal/v440/n7082/full/nature04586.html"
    fetch_pdf(url, args)


if __name__ == '__main__':
    # This will never work when you use relative imports.
    # Python 3 doesn't allow implicit relative imports.
    main()
