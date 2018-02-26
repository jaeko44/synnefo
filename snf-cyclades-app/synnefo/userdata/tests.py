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
#

from django import http
from django.test import TransactionTestCase
from django.conf import settings
from django.test.client import Client
import json
from django.core.urlresolvers import reverse
from django.core.validators import MaxLengthValidator

from mock import patch

from synnefo.userdata.models import PublicKeyPair, SSH_KEY_MAX_CONTENT_LENGTH


def get_user_mock(request, *args, **kwargs):
    if request.META.get('HTTP_X_AUTH_TOKEN', None) == '0000':
        request.user_uniq = 'test'
        request.user = {"access": {
                        "token": {
                            "expires": "2013-06-19T15:23:59.975572+00:00",
                            "id": "token",
                            "tenant": {
                                "id": "test",
                                "name": "Firstname Lastname"
                                }
                            },
                        "serviceCatalog": [],
                        "user": {
                            "roles_links": [],
                            "id": "test",
                            "roles": [{"id": 1, "name": "default"}],
                            "name": "Firstname Lastname"}}
                        }


class AaiClient(Client):

    def request(self, **request):
        # mock the astakos authentication function
        with patch("synnefo.userdata.rest.get_user",
                   new=get_user_mock):
            with patch("synnefo.userdata.views.get_user",
                       new=get_user_mock):
                request['HTTP_X_AUTH_TOKEN'] = '0000'
                return super(AaiClient, self).request(**request)


class TestRestViews(TransactionTestCase):
    reset_sequences = True
    fixtures = ['users']

    def setUp(self):
        settings.USERDATA_MAX_SSH_KEYS_PER_USER = 10

        settings.SKIP_SSH_VALIDATION = True
        self.client = AaiClient()
        self.user = 'test'
        self.keys_url = reverse('ui_keys_collection')

    def test_key_content_length_limit(self):
        # patch validator
        PublicKeyPair._meta.fields[3].validators = [MaxLengthValidator(10)]
        resp = self.client.post(self.keys_url,
                                json.dumps({'name': 'key pair 2',
                                            'content': """0123456789+"""}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 422)
        resp = json.loads(resp.content)
        assert 'errors' in resp
        assert 'content' in resp['errors']
        self.assertEqual(PublicKeyPair.objects.count(), 0)
        PublicKeyPair._meta.fields[3].validators = \
            [MaxLengthValidator(SSH_KEY_MAX_CONTENT_LENGTH)]

    def test_keys_collection_get(self):
        resp = self.client.get(self.keys_url)
        self.assertEqual(resp.content, "[]")

        PublicKeyPair.objects.create(user=self.user, name="key pair 1",
                                     content="content1")

        resp = self.client.get(self.keys_url)
        resp_list = json.loads(resp.content)
        exp_list = [{"content": "content1", "id": 1,
                     "uri": self.keys_url + "/1", "name": "key pair 1",
                     "fingerprint": "unknown fingerprint"}]
        self.assertEqual(resp_list, exp_list)

        PublicKeyPair.objects.create(user=self.user, name="key pair 2",
                                     content="content2")

        resp = self.client.get(self.keys_url)
        resp_list = json.loads(resp.content)
        exp_list = [{"content": "content1", "id": 1,
                     "uri": self.keys_url + "/1", "name": "key pair 1",
                     "fingerprint": "unknown fingerprint"},
                    {"content": "content2", "id": 2,
                     "uri": self.keys_url + "/2",
                     "name": "key pair 2",
                     "fingerprint": "unknown fingerprint"}]

        self.assertEqual(resp_list, exp_list)

    def test_keys_resourse_get(self):
        resp = self.client.get(self.keys_url + "/1")
        self.assertEqual(resp.status_code, 404)

        # create a public key
        PublicKeyPair.objects.create(user=self.user, name="key pair 1",
                                     content="content1")
        resp = self.client.get(self.keys_url + "/1")
        resp_dict = json.loads(resp.content)
        exp_dict = {"content": "content1", "id": 1,
                    "uri": self.keys_url + "/1", "name": "key pair 1",
                    "fingerprint": "unknown fingerprint"}
        self.assertEqual(resp_dict, exp_dict)

        # update
        resp = self.client.put(self.keys_url + "/1",
                               json.dumps({'name': 'key pair 1 new name'}),
                               content_type='application/json')

        pk = PublicKeyPair.objects.get(pk=1)
        self.assertEqual(pk.name, "key pair 1 new name")

        # delete
        resp = self.client.delete(self.keys_url + "/1")
        self.assertEqual(PublicKeyPair.objects.count(), 0)

        resp = self.client.get(self.keys_url + "/1")
        self.assertEqual(resp.status_code, 404)

        resp = self.client.get(self.keys_url)
        self.assertEqual(resp.content, "[]")

        # test rest create
        resp = self.client.post(self.keys_url,
                                json.dumps({'name': 'key pair 2',
                                            'content': """key 2 content"""}),
                                content_type='application/json')
        self.assertEqual(PublicKeyPair.objects.count(), 1)
        pk = PublicKeyPair.objects.get()
        self.assertEqual(pk.name, "key pair 2")
        self.assertEqual(pk.content, "key 2 content")

    def test_generate_views(self):
        import base64

        # just test that
        resp = self.client.post(self.keys_url + "/generate")
        self.assertNotEqual(resp, "")

        data = json.loads(resp.content)
        self.assertEqual('private' in data, True)
        self.assertEqual('private' in data, True)

        # public key is base64 encoded
        base64.b64decode(data['public'].replace("ssh-rsa ", ""))

        # remove header/footer
        private = "".join(data['private'].split("\n")[1:-1])

        # private key is base64 encoded
        base64.b64decode(private)

        new_key = PublicKeyPair()
        new_key.content = data['public']
        new_key.name = "new key"
        new_key.user = 'test'
        new_key.full_clean()
        new_key.save()

    def test_generate_limit(self):
        settings.USERDATA_MAX_SSH_KEYS_PER_USER = 1
        self.client.post(self.keys_url,
                         json.dumps({'name': 'key1',
                                     'content': """key 1 content"""}),
                         content_type='application/json')
        genpath = self.keys_url + "/generate"
        r = self.client.post(genpath)
        assert isinstance(r, http.HttpResponseServerError)

    def test_invalid_data(self):
        resp = self.client.post(self.keys_url,
                                json.dumps({'content': """key 2 content"""}),
                                content_type='application/json')

        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.content,
                         """{"non_field_key": "__all__", "errors": """
                         """{"name": ["This field cannot be blank."]}}""")

        settings.USERDATA_MAX_SSH_KEYS_PER_USER = 2

        # test ssh limit
        resp = self.client.post(self.keys_url,
                                json.dumps({'name': 'key1',
                                            'content': """key 1 content"""}),
                                content_type='application/json')
        resp = self.client.post(self.keys_url,
                                json.dumps({'name': 'key2',
                                            'content': """key 1 content"""}),
                                content_type='application/json')
        resp = self.client.post(self.keys_url,
                                json.dumps({'name': 'key3',
                                            'content': """key 1 content"""}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.content,
                         """{"non_field_key": "__all__", "errors": """
                         """{"__all__": ["SSH keys limit exceeded."]}}""")

    def test_existing_name(self):
        # test existing key name
        resp = self.client.post(self.keys_url,
                                json.dumps({'name': 'original_key',
                                            'content': """key 1 content"""}),
                                content_type='application/json')
        resp = self.client.post(self.keys_url,
                                json.dumps({'name': 'original_key',
                                            'content': """key 2 content"""}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.content,
                         """{"non_field_key": "__all__", "errors": """
                         """{"__all__": ["Public key pair with this User and Name already exists."]}}""")
