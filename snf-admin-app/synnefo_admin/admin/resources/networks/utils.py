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


from django.core.exceptions import ObjectDoesNotExist

from astakos.im.models import AstakosUser
from synnefo.db.models import Network

from synnefo_admin.admin.exceptions import AdminHttp404
from synnefo_admin.admin.utils import create_details_href


def get_network_or_404(query, for_update=False):
    network_obj = Network.objects.select_for_update() if for_update\
        else Network.objects
    try:
        return network_obj.get(pk=int(query))
    except (ObjectDoesNotExist, ValueError):
        raise AdminHttp404(
            "No Network was found that matches this query: %s\n" % query)


def get_contact_email(inst):
    if inst.userid:
        return AstakosUser.objects.get(uuid=inst.userid).email
    else:
        return "-"


def get_contact_name(inst):
    if inst.userid:
        return AstakosUser.objects.get(uuid=inst.userid).realname
    else:
        return "-"


def get_user_details_href(inst):
    if inst.userid:
        user = AstakosUser.objects.get(uuid=inst.userid)
        return create_details_href('user', user.realname, user.email, user.uuid)
    else:
        return "-"
