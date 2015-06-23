CENDARI CKAN extension
======================

This CKAN plugin enables authentication based on Shibboleth and the CENDARI Data API.

Features
----------------------
- authentication via Shibboleth
- login to account provided by CENDARI Data API
- without Data API response, fall back to log in existing user
- designate sysadmins through Shibboleth

To define shibboleth groups that will be promoted to sysadmin, add the groups in this way to the `[app:main]` section of the ckan config file:
```
shibboleth_sysadmin_groups = shib-admins shib-ckan-admins
```

TODO
----------------------
- error handling

