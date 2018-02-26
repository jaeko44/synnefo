# Copyright (C) 2010-2016 GRNET S.A.
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


import logging
from collections import OrderedDict

from astakos.im import user_logic as users

from synnefo_admin.admin.actions import AdminAction
from synnefo_admin.admin.utils import update_actions_rbac, send_admin_email
from astakos.im.user_utils import change_user_email


class UserAction(AdminAction):

    """Class for actions on users. Derived from AdminAction.

    Pre-determined Attributes:
        target:        user
    """

    def __init__(self, name, f, **kwargs):
        """Initialize the class with provided values."""
        AdminAction.__init__(self, name=name, target='user', f=f, **kwargs)


def check_user_action(action):
    def check(u, action):
        res, _ = users.validate_user_action(
            u, action, verification_code=u.verification_code)
        return res

    return lambda u: check(u, action)


def verify(user):
    return users.verify(user, verification_code=user.verification_code)


def generate_actions():
    """Create a list of actions on users.

    The actions are: activate/deactivate, accept/reject, verify, contact.
    """
    actions = OrderedDict()

    actions['activate'] = UserAction(name='Activate', f=users.activate,
                                     c=check_user_action("ACTIVATE"),
                                     karma='good',)

    actions['deactivate'] = UserAction(name='Deactivate', f=users.deactivate,
                                       c=check_user_action("DEACTIVATE"),
                                       karma='bad', caution_level='warning',)

    actions['accept'] = UserAction(name='Accept', f=users.accept,
                                   c=check_user_action("ACCEPT"),
                                   karma='good',)

    actions['reject'] = UserAction(name='Reject', f=users.reject,
                                   c=check_user_action("REJECT"),
                                   karma='bad', caution_level='dangerous',)

    actions['verify'] = UserAction(name='Verify', f=verify,
                                   c=check_user_action("VERIFY"),
                                   karma='good',)

    actions['resend_verification'] = UserAction(
        name='Resend verification', f=users.send_verification_mail,
        karma='good', c=check_user_action("SEND_VERIFICATION_MAIL"),)

    actions['contact'] = UserAction(name='Send e&#8209;mail', f=send_admin_email,)

    actions['modify_email'] = UserAction(name='Change e&#8209;mail',
                                         f=change_user_email, karma='bad',
                                         caution_level='warning',
                                         data_keys=['new_email'],)

    update_actions_rbac(actions)

    return actions
cached_actions = generate_actions()
