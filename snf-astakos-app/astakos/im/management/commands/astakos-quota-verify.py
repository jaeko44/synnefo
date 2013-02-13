# Copyright 2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from astakos.im.models import sync_all_users, sync_projects
from astakos.im.functions import get_user_by_uuid

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Inspect quotaholder status"

    option_list = BaseCommand.option_list + (
        make_option('--check',
                    action='store_true',
                    dest='check',
                    default=True,
                    help="Check if quotaholder is in sync with astakos (default)"),
        make_option('--sync',
                    action='store_true',
                    dest='sync',
                    default=False,
                    help="Sync quotaholder"),
    )

    @transaction.commit_on_success
    def handle(self, *args, **options):
        sync = options['sync']

        try:
            log = sync_all_users(sync=sync)
            existing, nonexisting, registered_quotas, astakos_quotas = log

            if nonexisting:
                self.stdout.write("Users not registered in quotaholder:\n")
                for user in nonexisting:
                    self.stdout.write("%s\n" % (user))
                self.stdout.write("\n")

            diffs = 0
            for holder, local in astakos_quotas.iteritems():
                registered = registered_quotas.pop(holder, None)
                if registered is None:
                    diffs += 1
                    self.stdout.write("No quotas for %s in quotaholder.\n\n" %
                                      (get_user_by_uuid(holder)))
                elif local != registered:
                    diffs += 1
                    self.stdout.write("Quotas differ for %s:\n" % (get_user_by_uuid(holder)))
                    self.stdout.write("Quotas according to quotaholder:\n")
                    self.stdout.write("%s\n" % (registered))
                    self.stdout.write("Quotas according to astakos:\n")
                    self.stdout.write("%s\n\n" % (local))

            if diffs:
                self.stdout.write("Quotas differ for %d users.\n" % (diffs))
        except BaseException, e:
            logger.exception(e)
            raise CommandError("Syncing failed.")