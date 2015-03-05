
from .AU_lib import AU_lib_login
from .HUID_lib import HUID_login
from . import adaptor_utils

login_adaptors = {'AU_lib': AU_lib_login,
                  'HUID': HUID_login}

# These are hard-coded domains. If you get a redirect to one of these,
# it is because you need to (re-)login.
login_domains = {'AU_lib': 'bibliotekssystem-saml.statsbiblioteket.dk',
                 'HUID': 'www.pin1.harvard.edu'}
