import os
import json
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import ckan.lib.helpers as helpers
import ckan.model
import requests
import pylons

import uuid
import logging
import pprint
from hashlib import md5

log = logging.getLogger("ckanext.cendari")

class CendariAuthPlugin(plugins.SingletonPlugin):
    """ 
    Main plugin class implemeting ``IConfigurer`` and ``IAuthenticator``.
    """

    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IAuthenticator)

    def update_config(self, config):
        """
        Add our extended login form template with Shibboleth link to CKAN's toolkit.
        """
        toolkit.add_template_directory(config, 'templates')

    def get_auth_functions(self):
        """ Pass. """
        return {}

    def login(self):
        """
        Performs the actual login:
        takes Shibboleth data found by :py:func:`get_shib_data`
        and sends it to the CENDARI Data API.

        Finally, a pylons session is created for session management.
        """
        # try getting user data from Shibboleth
        userdict = get_shib_data(self)
        if userdict:
            # prepare to send it to Data API
            apiurl  = 'http://localhost:42042/v1/session'
            apijson = {'eppn': userdict['eppn'], 'mail': userdict['mail'], 'cn': userdict['cn']}
            headers = {'content-type': 'application/json'}
            
            # retrieve username from Data API
            apiresponse = requests.post(apiurl, data=json.dumps(apijson), headers=headers)
            response_json = json.loads(apiresponse.content)
            api_username = str(response_json['username'])
            log.info('API returned username: ' + api_username + ' ... logging in.')

            # create a usersession
            pylons.session['cendari-auth-user'] = api_username
            pylons.session.save()
            # redirect to dashboard
            toolkit.redirect_to(controller='user', action='dashboard')

    def identify(self):
        """
        Extracts the logged in user from the pylons session.
        """
        # try getting user from pylons session
        pylons_user_name = pylons.session.get('cendari-auth-user')
        if pylons_user_name:
            toolkit.c.user = pylons_user_name

    def logout(self):
        """
        Log out the user by destroying the pylons session and redirecting to Shibboleth logout.
        """
        # destroy pylons session (ckan)
        if 'cendari-auth-user' in pylons.session:
            del pylons.session['cendari-auth-user']
            pylons.session.save()
        # redirect to shibboleth logout
        toolkit.redirect_to(controller='util',action='redirect',url='/Shibboleth.sso/Logout')

    def abort(self, status_code, detail, headers, comment):
        """ Simply passes through an abort. """
        return status_code, detail, headers, comment


def get_shib_data(self):
    '''
    Extracts full name, email address and ePPN from Shibboleth data.

    :returns: user_dict containing the data or ``None`` if no Shibboleth data is found.
    '''
    # take the data from the environment, default to blank
    mail = toolkit.request.environ.get('mail','')
    eppn = toolkit.request.environ.get('eppn','')
    cn = toolkit.request.environ.get('cn','')
    # return something only if there is a mail address
    if mail == '':
        return None
    else:
        userdict={'mail': mail,
            'eppn': eppn,
            'cn': cn}
        return userdict

