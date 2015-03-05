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


"""
HUID login


URLS:
 * Proxied url example: http://www.nature.com.ezp-prod1.hul.harvard.edu/nature/journal/vaop/ncurrent/full/nature14131.html
 * Login page: https://www.pin1.harvard.edu/cas/login?service=https%3A%2F%2Fwww.pin1.harvard.edu%2Fpin%2Fauthenticate%3F__authen_application(...)



Login page form:
<form id="fm1" action="/cas/login?service=https%3A%2F%2Fwww.pin1.harvard.edu%2Fpin%2Fauthenticate%3F__authen_application%3DHUL_ACC_MGMT_SVC(...)" method="post">
    <fieldset class="inner" id="multi-choice">
        <input id="compositeAuthenticationSourceType1" type="radio" name="compositeAuthenticationSourceType" value="PIN" checked tabindex="1"/>
        <input id="compositeAuthenticationSourceType2" type="radio" name="compositeAuthenticationSourceType" value="HMS ECOMMONS" tabindex="2"/>
        <input id="compositeAuthenticationSourceType3" type="radio" name="compositeAuthenticationSourceType" value="ADID" tabindex="3"/>
    </fieldset>
    <fieldset class="outer">
        <fieldset class="inner" id="form-field">
            <input id="username" name="username" class="required" tabindex="11" accesskey="u" type="text" value="" size="40" maxlength="71" autocomplete="off"/>
        </fieldset>
        <fieldset class="inner" id="form-field">
            <input id="password" name="password" class="required" tabindex="12" accesskey="p" type="password" value="" size="40" maxlength="40" autocomplete="off"/>
        </fieldset>
        <input type="submit" class="login-button" name="_eventId_submit" value="Login" tabindex="13"/>
        <input type="hidden" name="lt" value="LT-8650210-Tqw3elvHjAZOs12jDIMUPQ4NGCnHBV" />
        <input type="hidden" name="execution" value="e2s1" />
        <input type="hidden" name="casPageDisplayType" value="DEFAULT" />
        <input type="hidden" name="nonMobileOptionOnMobile" value="" />
    </fieldset>
</form>

Login page notes:
 *  I wonder if all the hidden input fields are constant or if they change.
    (I would imagine that the "lt" field is unique...)

"""

import re
import requests
from urllib.parse import urlparse, urljoin, parse_qsl
from getpass import getpass
import logging
import pdb
logger = logging.getLogger(__name__)


from .adaptor_utils import print_history



def get_huid_credentials(inputfields=None, header="HUID login:", defaults=None):
    if defaults is None:
        defaults = {}
    if inputfields is None:
        inputfields = (('username',
                        'HUID login   [%s]' % defaults.get('username', ''),
                        input),
                       ('password',
                        'PIN/Password [%s]' % defaults.get('password', ''),
                        getpass))
    formdata = {}
    print(header)
    for field, description, prompt_func in inputfields:
        formdata[field] = prompt_func("Please enter %s:  " % description) \
                            or defaults.get(field, '')
    if not all(formdata.values()):
        header = "\nUsername or password is empty, please re-enter credentials"
        return get_huid_credentials(inputfields, header=header, defaults=formdata)
    return formdata


def get_form_inputfields(html):
    """
    Get all input fields of the first form in html.
    That is:
        "(...)
        <input type="hidden" name="lt" value="LT-8650210-Tqw3elvHjAZOs12jDIMUPQ4NGCnHBV" />
        <input type="hidden" name="execution" value="e2s1" />
        (...)"
    will produce:
        {"lt": "LT-8650210-Tqw3elvHjAZOs12jDIMUPQ4NGCnHBV",
         "execution": "e2s1"}
    The usual result has this form:
        {'execution': 'e1s1',
         'lt': 'LT-8651386-hcIWCrFC6aJpXwyXOgum6e7LwadCGs',
         'password': '',
         'username': '',
         'casPageDisplayType': 'DEFAULT',
         '_eventId_submit': 'Login',
         'compositeAuthenticationSourceType': 'ADID',
         'nonMobileOptionOnMobile': ''}
    """
    form_regex = re.compile(r"<form.*?</form>", flags=re.DOTALL)
    form_html = form_regex.search(html).group()
    input_regex = re.compile(r'<input[^<>]*?name="(?P<name>[^"]*)"[^<>]*?value="(?P<value>[^"]*)"[^<>]*?/>',
                             flags=re.DOTALL+re.MULTILINE)
    matches = input_regex.findall(form_html)
    matches = dict(matches)
    return matches


def submit_lib_credentials(s, url, html, credentials=None):
    # HUID action url is the same as the login-page url:
    # However, I prefer to assemble the query part of the action url
    action_url = url.split('?')[0]
    action_query_params = dict(parse_qsl(urlparse(url).query))
    if not action_query_params:
        print("URL for AU credentials submission does not contain any query params")
        print("-- Complete url:", url)
        pdb.set_trace()
    #
    formdata = get_form_inputfields(html)
    # Use HUID PIN login:
    formdata["compositeAuthenticationSourceType"] = "PIN"
    # pop the "submit button" field: NO, DO NOT POP THE SUBMIT BUTTON FIELD!
    # formdata.pop('_eventId_submit') # KEEP _eventId_submit. It should have value 'Login'.
    if credentials is None or credentials.get("prompt") != "never":
        credentials = get_huid_credentials(defaults=credentials)
    elif credentials.get("prompt") == "never":
        credentials.pop("prompt")
        print("Skipping login prompt; using credentials:",
              ", ".join("%s: %s" % kv for kv in credentials.items()))
    formdata.update(credentials)
    # <form name="loginform" id="loginform" action="?" method="post">
    print("action_query_params:", action_query_params)
    print("formdata:", formdata)
    print("action_url:", action_url)
    r_login = s.post(action_url, params=action_query_params, data=formdata)
    print_history(r_login, "r_login")
    return r_login


def HUID_login(s, url, url_is_loginpage=None, html=None, r=None, config=None):
    """
    A very nice way to figure out what to do here is to use Firefox's "Network" monitor
    in the developer panel to monitor requests.
    """
    if url is None:
        url = "http://ezp-prod1.hul.harvard.edu"
    if s is None:
        s = requests.Session()

    # Make sure to set session User-Agent, or it will apparently not login:
    if "python-requests" in s.headers['User-Agent']:
        s.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:35.0) Gecko/20100101 Firefox/35.0'
    if r:
        url = r.url
        html = r.text
    if html is None or not url_is_loginpage:
        #raise ValueError("HUID_login requires a HTML body to start of from.")
        r = s.get(url)
        url = r.url
        html = r.text

    # Submit credentials on login page
    r = submit_lib_credentials(s, url, html, credentials=config)

    # Harvard's login system directly provides the correct final response via redirects :-)
    return r


