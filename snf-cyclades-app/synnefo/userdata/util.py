#
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


import binascii
import base64

from synnefo.userdata.asn1 import DerObject, DerSequence

from django.conf import settings

SUPPORT_GENERATE_KEYS = True
try:
    from paramiko import rsakey
    from paramiko.message import Message
except ImportError as e:
    SUPPORT_GENERATE_KEYS = False

SSH_KEY_LENGTH = getattr(settings, 'USERDATA_SSH_KEY_LENGTH', 2048)


def exportKey(keyobj, format='PEM'):
    """Export the RSA key. A string is returned
    with the encoded public or the private half
    under the selected format.

    format: 'DER' (PKCS#1) or 'PEM' (RFC1421)
    """
    der = DerSequence()
    if keyobj.has_private():
        keyType = "RSA PRIVATE"
        der[:] = [0, keyobj.n, keyobj.e, keyobj.d, keyobj.p, keyobj.q,
                  keyobj.d % (keyobj.p-1), keyobj.d % (keyobj.q-1),
                  keyobj.u]
    else:
        keyType = "PUBLIC"
        der.append('\x30\x0D\x06\x09\x2A\x86\x48\x86\xF7\x0D\x01'
                   '\x01\x01\x05\x00')
        bitmap = DerObject('BIT STRING')
        derPK = DerSequence()
        derPK[:] = [keyobj.n, keyobj.e]
        bitmap.payload = '\x00' + derPK.encode()
        der.append(bitmap.encode())
    if format == 'DER':
        return der.encode()
    if format == 'PEM':
        pem = "-----BEGIN %s KEY-----\n" % keyType
        binaryKey = der.encode()
        # Each BASE64 line can take up to 64 characters (=48 bytes of data)
        chunks = [binascii.b2a_base64(binaryKey[i:i+48])
                  for i in range(0, len(binaryKey), 48)]
        pem += ''.join(chunks)
        pem += "-----END %s KEY-----" % keyType
        return pem
    return ValueError("")


def generate_keypair():
    # generate RSA key
    from Crypto import Random
    Random.atfork()

    key = rsakey.RSA.generate(SSH_KEY_LENGTH)

    # get PEM string
    pem = exportKey(key, 'PEM')

    public_data = Message()
    public_data.add_string('ssh-rsa')
    public_data.add_mpint(key.key.e)
    public_data.add_mpint(key.key.n)

    # generate public content
    public = str("ssh-rsa %s" % base64.b64encode(str(public_data)))

    data = {'private': pem, 'public': public}
    return data
