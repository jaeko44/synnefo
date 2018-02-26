# Copyright (C) 2010-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import logging
from requests_oauthlib import OAuth2Session

from django.utils.translation import ugettext as _
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.conf import settings as django_settings

from astakos.im.models import AstakosUser
from astakos.im import settings
from astakos.im.views.target import get_pending_key, \
    handle_third_party_signup, handle_third_party_login, \
    init_third_party_session
from astakos.im.views.decorators import cookie_fix, requires_auth_provider

logger = logging.getLogger(__name__)

OAUTH_CONSUMER_KEY = settings.GOOGLE_CLIENT_ID
OAUTH_CONSUMER_SECRET = settings.GOOGLE_SECRET


def django_setting(key, default):
    return getattr(django_settings, 'GOOGLE_%s' % key.upper, default)

default_token_scopes = ['https://www.googleapis.com/auth/userinfo.profile',
                        'https://www.googleapis.com/auth/userinfo.email']

token_scope = django_setting('token_scope', u' '.join(default_token_scopes))
authenticate_url = django_setting(
    'authenticate_url',
    'https://accounts.google.com/o/oauth2/auth')
access_token_url = django_setting(
    'access_token_url',
    'https://www.googleapis.com/oauth2/v1/tokeninfo')
request_token_url = django_setting(
    'request_token_url',
    'https://accounts.google.com/o/oauth2/token')


def get_redirect_uri():
    return "%s%s" % (settings.BASE_HOST,
                     reverse('astakos.im.views.target.google.authenticated'))


@requires_auth_provider('google')
@require_http_methods(["GET", "POST"])
def login(request):
    init_third_party_session(request)
    oauth = OAuth2Session(settings.GOOGLE_CLIENT_ID,
                          redirect_uri=get_redirect_uri(), scope=token_scope)

    params = {}
    force_login = request.GET.get('force_login', request.GET.get('from_login',
                                                                 True))
    if force_login:
        params['approval_prompt'] = 'force'

    if request.GET.get('key', None):
        request.session['pending_key'] = request.GET.get('key')

    if request.GET.get('next', None):
        request.session['next_url'] = request.GET.get('next')

    auth_url, state = oauth.authorization_url(authenticate_url, **params)
    return HttpResponseRedirect(auth_url)


@requires_auth_provider('google')
@require_http_methods(["GET", "POST"])
@cookie_fix
def authenticated(
    request,
    template='im/third_party_check_local.html',
    extra_context=None
):

    if extra_context is None:
        extra_context = {}

    if request.GET.get('error', None):
        return HttpResponseRedirect(reverse('edit_profile'))

    # TODO: Handle errors, e.g. error=access_denied
    try:
        oauth = OAuth2Session(settings.GOOGLE_CLIENT_ID,
                              redirect_uri=get_redirect_uri(),
                              scope=token_scope)

        code = request.GET.get('code', None)
        token = oauth.fetch_token(request_token_url, code=code,
                                  client_secret=settings.GOOGLE_SECRET)
        access_token = token.get('access_token', None)

        # Simply validating the token should return user_id
        # This probably does not need to be performed via the oauth.request
        # method
        resp = oauth.request(url="%s?access_token=%s" %
                             (access_token_url, access_token), method="GET")
        access_token_data = json.loads(resp.content)
    except Exception as e:
        logger.exception(e)
        messages.error(request, _('Invalid Google response. Please '
                                  'contact support'))
        return HttpResponseRedirect(reverse('edit_profile'))

    if not access_token_data.get('user_id', None):
        messages.error(request, _('Invalid Google response. Please contact '
                                  ' support'))
        return HttpResponseRedirect(reverse('edit_profile'))

    userid = access_token_data['user_id']
    provider_info = access_token_data
    affiliation = 'Google.com'
    user_info = {'affiliation': affiliation}

    try:
        return handle_third_party_login(request, 'google', userid,
                                        provider_info, affiliation,
                                        user_info=user_info)
    except AstakosUser.DoesNotExist:
        third_party_key = get_pending_key(request)
        return handle_third_party_signup(request, userid, 'google',
                                         third_party_key,
                                         provider_info,
                                         user_info,
                                         template,
                                         extra_context)
