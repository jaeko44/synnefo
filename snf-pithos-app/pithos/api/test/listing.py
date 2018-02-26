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

from pithos.api.test import PithosAPITest

from synnefo.lib import join_urls

import json


class ListSharing(PithosAPITest):
    def _build_structure(self, user=None):
        user = user or self.user
        for i in range(2):
            cname = 'c%d' % i
            self.create_container(cname, user=user)
            self.upload_object(cname, 'obj', user=user)
            self.create_folder(cname, 'f1', user=user)
            self.create_folder(cname, 'f1/f2', user=user)
            self.create_folder(cname, 'f1/f2/f3', user=user)
            self.upload_object(cname, 'f1/f2/f3/obj', user=user)

        # share /c0/f1 path for read
        url = join_urls(self.pithos_path, user, 'c0', 'f1')
        r = self.post(url, user=user, content_type='',
                      HTTP_CONTENT_RANGE='bytes */*',
                      HTTP_X_OBJECT_SHARING='read=*')
        self.assertEqual(r.status_code, 202)

        # share /c0/f1/f2 path for write
        url = join_urls(self.pithos_path, user, 'c0', 'f1/f2')
        r = self.post(url, user=user, content_type='',
                      HTTP_CONTENT_RANGE='bytes */*',
                      HTTP_X_OBJECT_SHARING='write=*')
        self.assertEqual(r.status_code, 202)

    def test_list_share_with_me(self):
        self._build_structure('alice')
        url = join_urls(self.pithos_path, '/')
        r = self.get(url)
        self.assertEqual(r.status_code, 200)
        allowed_accounts = r.content.split('\n')
        if '' in allowed_accounts:
            allowed_accounts.remove('')
        self.assertEqual(allowed_accounts, ['alice'])

        r = self.get('%s?format=json' % url)
        self.assertEqual(r.status_code, 200)
        allowed_accounts = json.loads(r.content)
        self.assertEqual([i['name'] for i in allowed_accounts], ['alice'])

        url = join_urls(url, 'alice')
        r = self.get(url)
        self.assertEqual(r.status_code, 200)
        allowed_containers = r.content.split('\n')
        if '' in allowed_containers:
            allowed_containers.remove('')
        self.assertEqual(allowed_containers, ['c0'])

        r = self.get('%s?format=json' % url)
        self.assertEqual(r.status_code, 200)
        allowed_containers = json.loads(r.content)
        self.assertEqual([i['name'] for i in allowed_containers], ['c0'])

        url = join_urls(url, 'c0')
        r = self.get('%s?delimiter=/&shared=&' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = r.content.split('\n')
        if '' in shared_objects:
            shared_objects.remove('')
        self.assertEqual(shared_objects, ['f1', 'f1/'])

        r = self.get('%s?delimiter=/&shared=&format=json' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = json.loads(r.content)
        self.assertEqual([o.get('name', o.get('subdir')) for
                          o in shared_objects],
                         ['f1', 'f1/'])
        folder = (o for o in shared_objects if o['name'] == 'f1').next()
        self.assertTrue('x_object_sharing' in folder)
        self.assertTrue(folder['x_object_sharing'] == 'read=*')

        r = self.get('%s?delimiter=/&prefix=f1&shared=&' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = r.content.split('\n')
        if '' in shared_objects:
            shared_objects.remove('')
        self.assertEqual(shared_objects, ['f1/f2', 'f1/f2/'])

        r = self.get('%s?delimiter=/&prefix=f1&shared=&format=json' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = json.loads(r.content)
        self.assertEqual([o.get('name', o.get('subdir')) for
                          o in shared_objects],
                         ['f1/f2', 'f1/f2/'])
        folder = (o for o in shared_objects if o['name'] == 'f1/f2').next()
        self.assertTrue('x_object_sharing' in folder)
        self.assertTrue(folder['x_object_sharing'] == 'write=*')

        r = self.get('%s?delimiter=/&prefix=f1/f2&shared=&' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = r.content.split('\n')
        if '' in shared_objects:
            shared_objects.remove('')
        self.assertEqual(shared_objects, ['f1/f2/f3', 'f1/f2/f3/'])

        r = self.get('%s?delimiter=/&prefix=f1/f2&shared=&format=json' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = [i.get('name', i.get('subdir')) for i in
                          json.loads(r.content)]
        self.assertEqual(shared_objects, ['f1/f2/f3', 'f1/f2/f3/'])

        r = self.get('%s?delimiter=/&prefix=f1/f2/f3&shared=&' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = r.content.split('\n')
        if '' in shared_objects:
            shared_objects.remove('')
        self.assertEqual(shared_objects, ['f1/f2/f3/obj'])

        r = self.get('%s?delimiter=/&prefix=f1/f2/f3&shared=&format=json' %
                     url)
        self.assertEqual(r.status_code, 200)
        shared_objects = [i.get('name', i.get('subdir')) for i in
                          json.loads(r.content)]
        self.assertEqual(shared_objects, ['f1/f2/f3/obj'])

    def test_list_shared_by_me(self):
        self._build_structure()
        url = join_urls(self.pithos_path, self.user)
        r = self.get('%s?shared=' % url)
        self.assertEqual(r.status_code, 200)
        shared_containers = r.content.split('\n')
        if '' in shared_containers:
            shared_containers.remove('')
        self.assertEqual(shared_containers, ['c0'])

        r = self.get('%s?shared=&format=json' % url)
        self.assertEqual(r.status_code, 200)
        shared_containers = json.loads(r.content)
        self.assertEqual([i['name'] for i in shared_containers], ['c0'])

        url = join_urls(url, 'c0')
        r = self.get('%s?delimiter=/&shared=&' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = r.content.split('\n')
        if '' in shared_objects:
            shared_objects.remove('')
        self.assertEqual(shared_objects, ['f1', 'f1/'])

        r = self.get('%s?delimiter=/&shared=&format=json' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = json.loads(r.content)
        self.assertEqual([o.get('name', o.get('subdir')) for
                          o in shared_objects],
                         ['f1', 'f1/'])
        folder = (o for o in shared_objects if o['name'] == 'f1').next()
        self.assertTrue('x_object_sharing' in folder)
        self.assertTrue(folder['x_object_sharing'] == 'read=*')

        r = self.get('%s?delimiter=/&prefix=f1&shared=&' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = r.content.split('\n')
        if '' in shared_objects:
            shared_objects.remove('')
        self.assertEqual(shared_objects, ['f1/f2', 'f1/f2/'])

        r = self.get('%s?delimiter=/&prefix=f1&shared=&format=json' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = json.loads(r.content)
        self.assertEqual([o.get('name', o.get('subdir')) for
                          o in shared_objects],
                         ['f1/f2', 'f1/f2/'])
        folder = (o for o in shared_objects if o['name'] == 'f1/f2').next()
        self.assertTrue('x_object_sharing' in folder)
        self.assertTrue(folder['x_object_sharing'] == 'write=*')

        r = self.get('%s?delimiter=/&prefix=f1/f2&shared=&' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = r.content.split('\n')
        if '' in shared_objects:
            shared_objects.remove('')
        self.assertEqual(shared_objects, ['f1/f2/f3', 'f1/f2/f3/'])

        r = self.get('%s?delimiter=/&prefix=f1/f2&shared=&format=json' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = [i.get('name', i.get('subdir')) for i in
                          json.loads(r.content)]
        self.assertEqual(shared_objects, ['f1/f2/f3', 'f1/f2/f3/'])

        r = self.get('%s?delimiter=/&prefix=f1/f2/f3&shared=&' % url)
        self.assertEqual(r.status_code, 200)
        shared_objects = r.content.split('\n')
        if '' in shared_objects:
            shared_objects.remove('')
        self.assertEqual(shared_objects, ['f1/f2/f3/obj'])

        r = self.get('%s?delimiter=/&prefix=f1/f2/f3&shared=&format=json' %
                     url)
        self.assertEqual(r.status_code, 200)
        shared_objects = [i.get('name', i.get('subdir')) for i in
                          json.loads(r.content)]
        self.assertEqual(shared_objects, ['f1/f2/f3/obj'])
