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

from bitarray import bitarray
from base64 import b64encode, b64decode
import ipaddr

AVAILABLE = True
UNAVAILABLE = False


class PoolManager(object):
    """PoolManager for DB PoolTable models.

    This class implements a persistent Pool mechanism based on rows of
    PoolTable objects. Values that are pooled by this class, are mapped to an
    index on a bitarray, which is the one that is stored on the DB.

    The object that will be used in order to initialize this pool, must have
    two string attributes (available_map and reserved_map) and the size of the
    pool.

    Subclasses of PoolManager must implement value_to_index and index_to_value
    method's in order to denote how the value will be mapped to the index in
    the bitarray.

    Important!!: Updates on a PoolManager object are not reflected to the DB,
    until save() method is called.

    """
    def __init__(self, pool_table):
        self.pool_table = pool_table
        self.pool_size = pool_table.size
        if pool_table.available_map:
            self.available = _bitarray_from_string(pool_table.available_map)
            self.reserved = _bitarray_from_string(pool_table.reserved_map)
        else:
            self.available = self._create_empty_pool(self.pool_size)
            self.reserved = self._create_empty_pool(self.pool_size)
            self.add_padding(self.pool_size)

    def _create_empty_pool(self, size):
        ba = bitarray(size)
        ba.setall(AVAILABLE)
        return ba

    def add_padding(self, pool_size):
        bits = find_padding(pool_size)
        self.available.extend([UNAVAILABLE] * bits)
        self.reserved.extend([UNAVAILABLE] * bits)

    def cut_padding(self, pool_size):
        bits = find_padding(pool_size)
        self.available = self.available[:-bits]
        self.reserved = self.reserved[:-bits]

    @property
    def pool(self):
        return (self.available & self.reserved)

    def get(self, value=None):
        """Get a value from the pool."""
        if value is None:
            if self.empty():
                raise EmptyPool
            # Get the first available index
            index = int(self.pool.index(AVAILABLE))
            assert(index < self.pool_size)
            self._reserve(index)
            return self.index_to_value(index)
        else:
            if not self.contains(value):
                raise InvalidValue("Value %s does not belong to pool." % value)
            if self.is_available(value):
                self.reserve(value)
                return value
            else:
                raise ValueNotAvailable("Value %s is not available" % value)

    def put(self, value, external=False):
        """Return a value to the pool."""
        if value is None:
            raise ValueError
        if not self.contains(value):
            raise InvalidValue("%s does not belong to pool." % value)
        index = self.value_to_index(value)
        self._release(index, external)

    def reserve(self, value, external=False):
        """Reserve a value."""
        if not self.contains(value):
            raise InvalidValue("%s does not belong to pool." % value)
        index = self.value_to_index(value)
        self._reserve(index, external)
        return True

    def save(self, db=True):
        """Save changes to the DB."""
        self.pool_table.available_map = _bitarray_to_string(self.available)
        self.pool_table.reserved_map = _bitarray_to_string(self.reserved)
        if db:
            self.pool_table.save()

    def empty(self):
        """Return True when pool is empty."""
        return not self.pool.any()

    def size(self):
        """Return the size of the bitarray(original size + padding)."""
        return self.pool.length()

    def _reserve(self, index, external=False):
        if external:
            self.reserved[index] = UNAVAILABLE
        else:
            self.available[index] = UNAVAILABLE

    def _release(self, index, external=False):
        if external:
            self.reserved[index] = AVAILABLE
        else:
            self.available[index] = AVAILABLE

    def contains(self, value, index=False):
        if index is False:
            index = self.value_to_index(value)
        return index >= 0 and index < self.pool_size

    def count_available(self):
        return self.pool.count(AVAILABLE)

    def count_unavailable(self):
        return self.pool_size - self.count_available()

    def count_reserved(self):
        return self.reserved[:self.pool_size].count(UNAVAILABLE)

    def count_unreserved(self):
        return self.pool_size - self.count_reserved()

    def is_available(self, value, index=False):
        if not self.contains(value, index=index):
            raise InvalidValue("%s does not belong to pool." % value)
        if not index:
            idx = self.value_to_index(value)
        else:
            idx = value
        return self.pool[idx] == AVAILABLE

    def is_reserved(self, value, index=False):
        if not self.contains(value, index=index):
            raise InvalidValue("%s does not belong to pool." % value)
        if not index:
            idx = self.value_to_index(value)
        else:
            idx = value
        return self.reserved[idx] == UNAVAILABLE

    def to_01(self):
        return self.pool[:self.pool_size].to01()

    def to_map(self):
        return self.to_01().replace("0", "X").replace("1", ".")

    def extend(self, bits_num):
        assert(bits_num >= 0)
        self.resize(bits_num)

    def shrink(self, bits_num):
        assert(bits_num >= 0)
        size = self.pool_size
        tmp = self.available[(size - bits_num): size]
        if tmp.count(UNAVAILABLE):
            raise Exception("Cannot shrink. In use")
        self.resize(-bits_num)

    def resize(self, bits_num):
        if bits_num == 0:
            return
        # Cut old padding
        self.cut_padding(self.pool_size)
        # Do the resize
        if bits_num > 0:
            self.available.extend([AVAILABLE] * bits_num)
            self.reserved.extend([AVAILABLE] * bits_num)
        else:
            self.available = self.available[:bits_num]
            self.reserved = self.reserved[:bits_num]
        # Add new padding
        self.pool_size = self.pool_size + bits_num
        self.add_padding(self.pool_size)
        self.pool_table.size = self.pool_size

    def index_to_value(self, index):
        raise NotImplementedError

    def value_to_index(self, value):
        raise NotImplementedError

    def __repr__(self):
        return repr(self.pool_table)


class EmptyPool(Exception):
    pass


class ValueNotAvailable(Exception):
    pass


class InvalidValue(Exception):
    pass


def find_padding(size):
    extra = size % 8
    return extra and (8 - extra) or 0


def bitarray_to_01(bitarray_):
    return bitarray_.to01()


def bitarray_to_map(bitarray_):
    return bitarray_to_01(bitarray_).replace("0", "X").replace("1", ".")


def _bitarray_from_string(bitarray_):
    ba = bitarray()
    ba.frombytes(b64decode(bitarray_))
    return ba


def _bitarray_to_string(bitarray_):
    return b64encode(bitarray_.tobytes())

##
## Custom pools
##


class BridgePool(PoolManager):
    def index_to_value(self, index):
        # Bridge indexes should start from 1
        return self.pool_table.base + str(index + 1)

    def value_to_index(self, value):
        return int(value.replace(self.pool_table.base, "")) - 1


class MacPrefixPool(PoolManager):
    def __init__(self, pool_table):
        do_init = False if pool_table.available_map else True
        super(MacPrefixPool, self).__init__(pool_table)
        if do_init:
            for i in xrange(1, self.pool_size):
                if not self.validate_mac(self.index_to_value(i)):
                    self._reserve(i, external=True)
            # Reserve the first mac-prefix for public-networks
            self._reserve(0, external=True)

    def index_to_value(self, index):
        """Convert index to mac_prefix"""
        base = self.pool_table.base
        a = hex(int(base.replace(":", ""), 16) + index).replace("0x", '')
        mac_prefix = ":".join([a[x:x + 2] for x in xrange(0, len(a), 2)])
        return mac_prefix

    def value_to_index(self, value):
        base = self.pool_table.base
        return int(value.replace(":", ""), 16) - int(base.replace(":", ""), 16)

    @staticmethod
    def validate_mac(value):
        # We require that the mac is locally administered (second least
        # significant bit of the first octed == 1) and that the mac is meant
        # for unicast transmission (the least significant bit of the first
        # octet of an address is set to == 0)
        #
        # Note that this also affects the actual usable size of the
        # MacPrefixPool as it marks as externally reserved the calculated MAC
        # addresses that do not adhere to this restriction.
        hex_ = value.replace(":", "")
        bin_ = bin(int(hex_, 16))[2:].zfill(8)
        return bin_[6] == '1' and bin_[7] == '0'


class IPPool(PoolManager):
    def __init__(self, pool_table):
        subnet = pool_table.subnet
        self.net = ipaddr.IPNetwork(subnet.cidr)
        self.offset = pool_table.offset
        self.base = pool_table.base
        if pool_table.available_map:
            initialized_pool = True
        else:
            initialized_pool = False
        super(IPPool, self).__init__(pool_table)
        if not initialized_pool:
            self.check_pool_integrity()

    def check_pool_integrity(self):
        """Check the integrity of the IP pool

        This check is required only for old IP pools(one IP pool per network
        that contained the whole subnet cidr) that had not been initialized
        before the migration. This checks that the network, gateway and
        broadcast IP addresses are externally reserved, and if not reserves
        them.

        """
        subnet = self.pool_table.subnet
        check_ips = [str(self.net.network), str(self.net.broadcast)]
        if subnet.gateway is not None:
            check_ips.append(subnet.gateway)
        for ip in check_ips:
            if self.contains(ip):
                self.reserve(ip, external=True)

    def value_to_index(self, value):
        addr = ipaddr.IPAddress(value)
        return int(addr) - int(self.net.network) - int(self.offset)

    def index_to_value(self, index):
        return str(self.net[index + int(self.offset)])

    def contains(self, address, index=False):
        if index is False:
            try:
                addr = ipaddr.IPAddress(address)
            except ValueError:
                raise InvalidValue("Invalid IP address")

            if addr not in self.net:
                return False
        return super(IPPool, self).contains(address, index=False)

    def return_start(self):
        return str(ipaddr.IPAddress(ipaddr.IPNetwork(self.base).network) +
                   self.offset)

    def return_end(self):
        return str(ipaddr.IPAddress(ipaddr.IPNetwork(self.base).network) +
                   self.offset + self.pool_size - 1)
