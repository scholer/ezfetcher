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


# pylint: disable=C0103,W0142,W0611,C0111,C0301

import re
import requests
from urllib.parse import urlparse, urljoin, parse_qsl
from getpass import getpass
import logging
import pdb
logger = logging.getLogger(__name__)


from .adaptor_utils import print_history



def select_login_page(s, url, url_is_loginpage=True):
    """ Returns 'AU Library' login page response. """

    if not url_is_loginpage:
        #url = "http://www.nature.com.ez.statsbiblioteket.dk:2048/nature/journal/v440/n7082/full/nature04586.html"
        r1 = s.get(url)
        print_history(r1, "r1")
        url = r1.url

    params = dict(parse_qsl(urlparse(url).query))

    actionurl = "https://bibliotekssystem-saml.statsbiblioteket.dk/module.php/saml/disco.php"
    formdata = {"idp_https://userregistry-idp-saml.statsbiblioteket.dk": "Log ind via Statsbiblioteket / AU Library"}
    params.update(formdata)
    r2 = s.get(actionurl, params=params)
    print_history(r2, "r2")
    return r2


## IT WORKS, bitches!

def get_credentials(inputfields=None, header="AU Library login:", defaults=None):
    if defaults is None:
        defaults = {}
    if inputfields is None:
        inputfields = (('username', 'CPR nummer [%s]' % defaults.get('username', ''), getpass),
                       ('password', 'PIN        [%s]' % defaults.get('password', ''), getpass))
    formdata = {}
    print(header)
    for field, description, prompt_func in inputfields:
        formdata[field] = prompt_func("Please enter %s:  " % description) \
                            or defaults.get(field, '')
    if not all(formdata.values()):
        header = "\nUsername or password is empty, please re-enter credentials"
        return get_credentials(inputfields, header=header, defaults=formdata)
    return formdata


def submit_lib_credentials(s, url, html=None, credentials=None):
    # AuthState is same as the AuthState you get from url,
    # so the initial formdata can be obtained simply with:
    formdata = dict(parse_qsl(urlparse(url).query))
    action_url = url.split('?')[0]
    if not formdata:
        print("URL for AU credentials submission does not contain any query params")
        print("-- Complete url:", url)
        pdb.set_trace()

    # Obtain credentials and add it to the formdata:
    if credentials is None or credentials.get("prompt") != "never":
        credentials = get_credentials(defaults=credentials)
    elif credentials.get("prompt") == "never":
        credentials.pop("prompt")
        print("Skipping login prompt; using credentials:",
              ", ".join("%s: %s" % kv for kv in credentials.items()))
    formdata.update(credentials)
    # <form name="loginform" id="loginform" action="?" method="post">
    r3 = s.post(action_url, data=formdata)
    print_history(r3, "r3")
    return r3


def parse_saml_response(s, html):
    #regex = re.compile(r'name="SAMLResponse" value="(\w*)"', flags=re.DOTALL)
    # <input type="hidden" name="SAMLResponse" value="PHN
    m = re.search(r'name="SAMLResponse" value="([\w\+]*)"', html)
    formdata = {'SAMLResponse': m.group(1)}
    # <form method="post" action="https://bibliotekssystem-saml.statsbiblioteket.dk/module.php/saml/sp/saml2-acs.php/casserver">
    action_url = "https://bibliotekssystem-saml.statsbiblioteket.dk/module.php/saml/sp/saml2-acs.php/casserver"
    r4 = s.post(action_url, data=formdata)
    print_history(r4, "r4")
    return r4

def parse_saml_2(s, html):
    #<form method="post" action="https://login.ez.statsbiblioteket.dk:12048/Shibboleth.sso/SAML2/POST">
    # <input type="hidden" name="SAMLResponse" value="PHNhbWxwOlJl(...)
    # <input type="hidden" name="RelayState" value="ezp.2aHR0cDovL3d3dy5u(...)
    # <input type="submit" value="Submit" />
    action = "https://login.ez.statsbiblioteket.dk:12048/Shibboleth.sso/SAML2/POST"
    m = re.search(r'name="SAMLResponse" value="([\w\+=]*)".*name="RelayState" value="([^\s^"]*)"', html)
    formdata = {"SAMLResponse": m.group(1),
                "RelayState" : m.group(2)}
    r = s.post(action, data=formdata)
    print_history(r, "r5")
    return r


def AU_lib_login(s, url, url_is_loginpage=None, html=None, r=None, config=None):

    if url is None:
        url = "http://ez.statsbiblioteket.dk:2048"
    if s is None:
        s = requests.Session()

    if r:
        url = r.url
        html = r.text
    if html is None or not url_is_loginpage:
        #raise ValueError("HUID_login requires a HTML body to start of from.")
        r = s.get(url)
        url = r.url
        html = r.text


    # Select login method:
    r = select_login_page(s, url, url_is_loginpage)

    # Submit library credentials: , html=None, credentials=None
    r = submit_lib_credentials(s, r.url, html=r.text, credentials=config)

    # After AU lib login, you have to transfer SAMLResponses. (Usually done by javascript in browser...)
    try:
        r = parse_saml_response(s, r.text)
    except AttributeError as e:
        print("Error while trying to parse SAML response:", e)
        print("Starting pdb...")
        pdb.set_trace()
        parse_saml_response(s, r.text)
    r = parse_saml_2(s, r.text)
    # YEAH, r now has text from nature url !!
    # Andersen DNA box:
    #url2 = "http://www.nature.com.ez.statsbiblioteket.dk:2048/nature/journal/v459/n7243/full/nature07971.html"
    #r2 = s.get(url2)
    # And yes, I can now use my session to download other stuff via ez.statsbiblioteket.dk:2048 :)
    return r


def test():
    pass
    #s = requests.Session()
