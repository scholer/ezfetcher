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


# pylint: disable=C0103,W0142,W0611,C0111


from urllib.parse import urlparse, urljoin, parse_qsl


def print_history(response, name):
    print("\n")
    print(name+".history + ["+name+"]:", response.history + [response])
    for i, res in enumerate(response.history + [response]):
        parsed = urlparse(res.url)
        print("- Hit %s: %s" % (i, "".join((parsed.netloc, parsed.path))))
