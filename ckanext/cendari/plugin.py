import os
import json
import pylons.config as config
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
            try:
                apiresponse = requests.post(apiurl, data=json.dumps(apijson), headers=headers, timeout=1)
                log.info('Data API response status_code: '+ str(apiresponse.status_code))
                if apiresponse.status_code == 200:
                    response_json = json.loads(apiresponse.content)
                    api_username = str(response_json['username'])
                    log.info('API returned username: ' + api_username + '.')
                    # check sysadmin status
                    verify_sysadmin_status(self,api_username)
                    log.info('Logging in ' + api_username + '.')

                    # create a usersession
                    pylons.session['cendari-auth-user'] = api_username
                    pylons.session.save()
                    # redirect to dashboard
                    toolkit.redirect_to(controller='user', action='dashboard')
            # should the API not respond (in time), lets try logging in directly
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                log.warning('Data API did not respond!')
                user = ckan.model.User.by_openid(userdict['eppn'])
                if user:
                    ckan_user_dict = toolkit.get_action('user_show')(data_dict={'id': user.id})
                    log.info('logging in existing user with eppn: '+ userdict['eppn'])
                    # save user to pylons session
                    pylons.session['cendari-auth-user'] = ckan_user_dict['name']
                    pylons.session.save()
                    # redirect to dashboard
                    toolkit.redirect_to(controller='user', action='dashboard')
                else:
                    pass
        else:
                pass

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

def verify_sysadmin_status(self,api_username):
    '''
    Checks the shibboleth data for sysadmin privileges and grants or revokes them in CKAN accordingly.
    '''
    # get user's groups and list of groups to be made sysadmin
    isMemberOf_groups = toolkit.request.environ.get('isMemberOf','').split(';')
    shibboleth_sysadmin_groups = config.get('shibboleth_sysadmin_groups', '').split(' ')
    user = ckan.model.User.by_name(api_username)
    # if the two lists intersect, the user should be sysadmin
    groups_intersection = set.intersection(set(shibboleth_sysadmin_groups),set(isMemberOf_groups))
    if groups_intersection:
        if not user.sysadmin:
            user.sysadmin = True
            ckan.model.Session.add(user)
            ckan.model.repo.commit_and_remove()
            log.info('User ' + api_username + ' promoted to sysadmin.')
    # otherwise he should not be
    else:
        if user.sysadmin:
            user.sysadmin = False
            ckan.model.Session.add(user)
            ckan.model.repo.commit_and_remove()
            log.info('User ' + api_username + ' demoted from sysadmin.')
    return True

def get_shib_data(self):
    '''
    Extracts full name, email address and ePPN from Shibboleth data.

    :returns: user_dict containing the data or ``None`` if no Shibboleth data is found.
    '''
    # take the data from the environment, default to blank
    mail = toolkit.request.environ.get('mail','')
    eppn = toolkit.request.environ.get('eppn','')
    sn = toolkit.request.environ.get('sn','')
    givenName = toolkit.request.environ.get('givenName','')
    cn = toolkit.request.environ.get('cn',givenName+' '+sn)
    # return something only if there is a mail address
    if mail == '':
        return None
    else:
        userdict={'mail': mail,
            'eppn': eppn,
            'cn': cn}
        return userdict

