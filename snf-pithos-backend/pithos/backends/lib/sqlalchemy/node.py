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

from time import time
from operator import itemgetter
from itertools import groupby
from collections import defaultdict

from sqlalchemy import (Table, Integer, BigInteger, DECIMAL, Boolean,
                        Column, String, MetaData, ForeignKey)
from sqlalchemy.schema import Index, Sequence
from sqlalchemy.sql import (func, and_, or_, not_, select, bindparam, exists,
                            functions)
from sqlalchemy.sql.expression import true, literal, type_coerce
from sqlalchemy.exc import NoSuchTableError, IntegrityError

from dbworker import DBWorker, ESCAPE_CHAR

from pithos.backends.modular import MAP_AVAILABLE
from pithos.backends.filter import parse_filters

DEFAULT_DISKSPACE_RESOURCE = 'pithos.diskspace'
ROOTNODE = 0

(MATCH_PREFIX, MATCH_EXACT) = range(2)

inf = float('inf')


def strnextling(prefix):
    """Return the first unicode string
       greater than but not starting with given prefix.
       strnextling('hello') -> 'hellp'
    """
    if not prefix:
        ## all strings start with the null string,
        ## therefore we have to approximate strnextling('')
        ## with the last unicode character supported by python
        ## 0x10ffff for wide (32-bit unicode) python builds
        ## 0x00ffff for narrow (16-bit unicode) python builds
        ## We will not autodetect. 0xffff is safe enough.
        return unichr(0xffff)
    s = prefix[:-1]
    c = ord(prefix[-1])
    if c >= 0xffff:
        raise RuntimeError
    s += unichr(c + 1)
    return s


def strprevling(prefix):
    """Return an approximation of the last unicode string
       less than but not starting with given prefix.
       strprevling(u'hello') -> u'helln\\xffff'
    """
    if not prefix:
        ## There is no prevling for the null string
        return prefix
    s = prefix[:-1]
    c = ord(prefix[-1])
    if c > 0:
        s += unichr(c - 1) + unichr(0xffff)
    return s


def safe_long(v):
    """ Cast to long if value is not None """
    return long(v) if v is not None else v


def create_tables(engine):
    metadata = MetaData()

    #create nodes table
    columns = []
    columns.append(Column('node', Integer, primary_key=True))
    columns.append(Column('parent', Integer,
                          ForeignKey('nodes.node',
                                     ondelete='CASCADE',
                                     onupdate='CASCADE'),
                          autoincrement=False))
    columns.append(Column('latest_version', Integer))
    columns.append(Column('path', String(2048), default='', nullable=False))
    nodes = Table('nodes', metadata, *columns, mysql_engine='InnoDB')
    Index('idx_nodes_path', nodes.c.path, unique=True)
    Index('idx_nodes_parent', nodes.c.parent)
    Index('idx_latest_version', nodes.c.latest_version)
    Index('idx_nodes_parent0', nodes.c.parent,
          postgresql_where=nodes.c.parent == 0)
    Index('idx_nodes_parent0_path', nodes.c.parent, nodes.c.path,
          postgresql_where=nodes.c.parent == 0)

    #create policy table
    columns = []
    columns.append(Column('node', Integer,
                          ForeignKey('nodes.node',
                                     ondelete='CASCADE',
                                     onupdate='CASCADE'),
                          primary_key=True))
    columns.append(Column('key', String(128), primary_key=True))
    columns.append(Column('value', String(256)))
    Table('policy', metadata, *columns, mysql_engine='InnoDB')

    #create statistics table
    columns = []
    columns.append(Column('node', Integer,
                          ForeignKey('nodes.node',
                                     ondelete='CASCADE',
                                     onupdate='CASCADE'),
                          primary_key=True))
    columns.append(Column('population', Integer, nullable=False, default=0))
    columns.append(Column('size', BigInteger, nullable=False, default=0))
    columns.append(Column('mtime', DECIMAL(precision=16, scale=6)))
    columns.append(Column('cluster', Integer, nullable=False, default=0,
                          primary_key=True, autoincrement=False))
    Table('statistics', metadata, *columns, mysql_engine='InnoDB')

    #create versions table
    columns = []
    columns.append(Column('serial', Integer, primary_key=True))
    columns.append(Column('node', Integer,
                          ForeignKey('nodes.node',
                                     ondelete='CASCADE',
                                     onupdate='CASCADE')))
    columns.append(Column('hash', String(256)))
    columns.append(Column('size', BigInteger, nullable=False, default=0))
    columns.append(Column('type', String(256), nullable=False, default=''))
    columns.append(Column('source', Integer))
    columns.append(Column('mtime', DECIMAL(precision=16, scale=6)))
    columns.append(Column('muser', String(256), nullable=False, default=''))
    columns.append(Column('uuid', String(64), nullable=False, default=''))
    columns.append(Column('checksum', String(256), nullable=False, default=''))
    columns.append(Column('cluster', Integer, nullable=False, default=0))
    columns.append(Column('available', Integer, nullable=False, default=1))
    columns.append(Column('map_check_timestamp', DECIMAL(precision=16,
                                                         scale=6)))
    columns.append(Column('mapfile', String(256)))
    columns.append(Column('is_snapshot', Boolean, nullable=False,
                          default=False))

    versions = Table('versions', metadata, *columns, mysql_engine='InnoDB')
    Index('idx_versions_node_mtime', versions.c.node, versions.c.mtime)
    Index('idx_versions_node', versions.c.node)
    Index('idx_versions_node_uuid', versions.c.uuid)
    Index('idx_versions_serial_cluster_n2', versions.c.serial,
          versions.c.cluster, postgresql_where=versions.c.cluster != 2)
    Index('idx_versions_node_cluster0', versions.c.node,
          versions.c.cluster, postgresql_where=versions.c.cluster == 0)
    Index('idx_versions_node_cluster1', versions.c.node,
          versions.c.cluster, postgresql_where=versions.c.cluster == 1)
    Index('idx_versions_node_cluster2', versions.c.node,
          versions.c.cluster, postgresql_where=versions.c.cluster == 2)
    Index('idx_versions_serial_cluster0', versions.c.serial,
          versions.c.cluster, postgresql_where=versions.c.cluster == 0)
    Index('idx_versions_serial_cluster1', versions.c.serial,
          versions.c.cluster, postgresql_where=versions.c.cluster == 1)
    Index('idx_versions_serial_cluster2', versions.c.serial,
          versions.c.cluster, postgresql_where=versions.c.cluster == 2)

    #create attributes table
    columns = []
    columns.append(Column('serial', Integer,
                          ForeignKey('versions.serial',
                                     ondelete='CASCADE',
                                     onupdate='CASCADE'),
                          primary_key=True))
    columns.append(Column('domain', String(256), primary_key=True))
    columns.append(Column('key', String(128), primary_key=True))
    columns.append(Column('value', String(256)))
    columns.append(Column('node', Integer, nullable=False, default=0))
    columns.append(Column('is_latest', Boolean, nullable=False, default=True))
    attributes = Table('attributes', metadata, *columns, mysql_engine='InnoDB')
    Index('idx_attributes_domain', attributes.c.domain)
    Index('idx_attributes_serial_node', attributes.c.serial, attributes.c.node)
    Index('idx_attributes_node', attributes.c.node)
    Index('idx_attributes_islatest_domain_plankton', attributes.c.is_latest,
          attributes.c.domain, postgresql_where=and_(
              attributes.c.is_latest == true(),
              attributes.c.domain == "plankton"))
    Index('idx_attributes_key_domain_plankton', attributes.c.key,
          attributes.c.domain,
          postgresql_where=attributes.c.domain == "plankton")
    Index('idx_attributes_key_domain_pithos', attributes.c.key,
          attributes.c.domain,
          postgresql_where=attributes.c.domain == "pithos")
    Index('idx_attributes_serial_domain_pithos', attributes.c.serial,
          attributes.c.domain,
          postgresql_where=attributes.c.domain == "pithos")
    Index('idx_attributes_serial_domain_plankton', attributes.c.serial,
          attributes.c.domain,
          postgresql_where=attributes.c.domain == "plankton")

    # TODO: handle backends not supporting sequences
    mapfile_seq = Sequence('mapfile_seq', metadata=metadata)

    metadata.create_all(engine)
    return metadata.sorted_tables + [mapfile_seq]


class Node(DBWorker):
    """Nodes store path organization and have multiple versions.
       Versions store object history and have multiple attributes.
       Attributes store metadata.
    """

    # TODO: Provide an interface for included and excluded clusters.

    def __init__(self, **params):
        self._props = params.pop('props')
        self.mapfile_prefix = params.pop('mapfile_prefix', 'snf_file_')
        DBWorker.__init__(self, **params)
        try:
            metadata = MetaData(self.engine)
            self.nodes = Table('nodes', metadata, autoload=True)
            self.policy = Table('policy', metadata, autoload=True)
            self.statistics = Table('statistics', metadata, autoload=True)
            self.versions = Table('versions', metadata, autoload=True)
            self.attributes = Table('attributes', metadata, autoload=True)
            self.mapfile_seq = Sequence('mapfile_seq', metadata)
        except NoSuchTableError:
            tables = create_tables(self.engine)
            map(lambda t: self.__setattr__(t.name, t), tables)

        s = self.nodes.select().where(and_(self.nodes.c.node == ROOTNODE,
                                           self.nodes.c.parent == ROOTNODE))
        wrapper = self.wrapper
        wrapper.execute()
        try:
            rp = self.conn.execute(s)
            r = rp.fetchone()
            rp.close()
            if not r:
                s = self.nodes.insert(
                ).values(node=ROOTNODE, parent=ROOTNODE, path='')
                self.conn.execute(s)
        finally:
            wrapper.commit()

    def node_create(self, parent, path):
        """Create a new node from the given properties.
           Return the node identifier of the new node.
        """
        t = self.conn.begin_nested()  # create savepoint
        s = self.nodes.insert().values(parent=parent, path=path)
        try:
            r = self.conn.execute(s)
        except IntegrityError:
            t.rollback()
            raise ValueError('Attempt to create a node which already exists.')
        else:
            t.commit()
            inserted_primary_key = r.inserted_primary_key[0]
            r.close()
            return inserted_primary_key

    def node_lookup(self, path, for_update=False):
        """Lookup the current node of the given path.
           Return None if the path is not found.
        """

        # Use LIKE for comparison to avoid MySQL problems with trailing spaces.
        s = select([self.nodes.c.node],
                   self.nodes.c.path.like(self.escape_like(path),
                                          escape=ESCAPE_CHAR),
                   for_update=for_update)
        r = self.conn.execute(s)
        row = r.fetchone()
        r.close()
        if row:
            return row[0]
        return None

    def node_lookup_bulk(self, paths):
        """Lookup the current nodes for the given paths.
           Return () if the path is not found.
        """

        if not paths:
            return ()
        # Use LIKE for comparison to avoid MySQL problems with trailing spaces.
        s = select([self.nodes.c.node], self.nodes.c.path.in_(paths))
        r = self.conn.execute(s)
        rows = r.fetchall()
        r.close()
        return [row[0] for row in rows]

    def node_get_properties(self, node):
        """Return the node's (parent, path).
           Return None if the node is not found.
        """

        s = select([self.nodes.c.parent, self.nodes.c.path])
        s = s.where(self.nodes.c.node == node)
        r = self.conn.execute(s)
        l = r.fetchone()
        r.close()
        return l

    def node_get_parent_path(self, node):
        """Return the node's parent path.
           Return None if the node is not found.
        """

        n1 = self.nodes.alias('n1')
        n2 = self.nodes.alias('n2')

        s = select([n2.c.path])
        s = s.where(n2.c.node == n1.c.parent)
        s = s.where(n1.c.node == node)
        r = self.conn.execute(s)
        l = r.fetchone()
        r.close()
        return l[0] if l is not None else None

    def node_get_versions(self, node, keys=(), props=None):
        """Return the properties of all versions at node.
           If keys is empty, return all properties in the order
           (serial, node, hash, size, type, source, mtime, muser, uuid,
            checksum, cluster, available, map_check_timestamp).
        """

        props = props or self._props
        s = select([self.versions.c.serial,
                    self.versions.c.node,
                    self.versions.c.hash,
                    self.versions.c.size,
                    self.versions.c.type,
                    self.versions.c.source,
                    self.versions.c.mtime,
                    self.versions.c.muser,
                    self.versions.c.uuid,
                    self.versions.c.checksum,
                    self.versions.c.cluster,
                    self.versions.c.available,
                    self.versions.c.map_check_timestamp,
                    self.versions.c.mapfile,
                    self.versions.c.is_snapshot],
                   self.versions.c.node == node)
        s = s.order_by(self.versions.c.serial)
        r = self.conn.execute(s)
        rows = r.fetchall()
        r.close()
        if not rows:
            return rows

        if not keys:
            return rows

        return [[p[props[k]] for k in keys if k in props] for
                p in rows]

    def node_count_children(self, node):
        """Return node's child count."""

        s = select([func.count(self.nodes.c.node)])
        s = s.where(and_(self.nodes.c.parent == node,
                         self.nodes.c.node != ROOTNODE))
        r = self.conn.execute(s)
        row = r.fetchone()
        r.close()
        return row[0]

    def node_purge_children(self, parent, before=inf, cluster=0,
                            update_statistics_ancestors_depth=None):
        """Delete all versions with the specified
           parent and cluster, and return
           the hashes, the total size and the serials of versions deleted.
           Clears out nodes with no remaining versions.
        """
        #update statistics
        c1 = select([self.nodes.c.node],
                    self.nodes.c.parent == parent)
        where_clause = and_(self.versions.c.node.in_(c1),
                            self.versions.c.cluster == cluster)
        if before != inf:
            where_clause = and_(where_clause,
                                self.versions.c.mtime <= before)
        s = select([func.count(self.versions.c.serial),
                    func.sum(self.versions.c.size)])
        s = s.where(where_clause)
        r = self.conn.execute(s)
        row = r.fetchone()
        r.close()
        if not row:
            return (), 0, ()
        nr, size = row[0], safe_long(row[1]) if row[1] else 0
        mtime = time()
        self.statistics_update(parent, -nr, -size, mtime, cluster)
        self.statistics_update_ancestors(parent, -nr, -size, mtime, cluster,
                                         update_statistics_ancestors_depth)

        s = select([self.versions.c.hash, self.versions.c.serial])
        s = s.where(where_clause)
        r = self.conn.execute(s)
        hashes = []
        serials = []
        for row in r.fetchall():
            hashes += [row[0]]
            serials += [row[1]]
        r.close()

        #delete versions
        s = self.versions.delete().where(where_clause)
        r = self.conn.execute(s)
        r.close()

        #delete nodes
        s = select([self.nodes.c.node],
                   and_(self.nodes.c.parent == parent,
                        select([func.count(self.versions.c.serial)],
                               self.versions.c.node == self.nodes.c.node).
                        as_scalar() == 0))
        rp = self.conn.execute(s)
        nodes = [row[0] for row in rp.fetchall()]
        rp.close()
        if nodes:
            s = self.nodes.delete().where(self.nodes.c.node.in_(nodes))
            self.conn.execute(s).close()

        return hashes, size, serials

    def node_purge(self, node, before=inf, cluster=0,
                   update_statistics_ancestors_depth=None):
        """Delete all versions with the specified
           node and cluster, and return
           the hashes and size of versions deleted.
           Clears out the node if it has no remaining versions.
        """

        #update statistics
        s = select([func.count(self.versions.c.serial),
                    func.sum(self.versions.c.size)])
        where_clause = and_(self.versions.c.node == node,
                            self.versions.c.cluster == cluster)
        if before != inf:
            where_clause = and_(where_clause,
                                self.versions.c.mtime <= before)
        s = s.where(where_clause)
        r = self.conn.execute(s)
        row = r.fetchone()
        nr, size = row[0], safe_long(row[1])
        r.close()
        if not nr:
            return (), 0, ()
        mtime = time()
        self.statistics_update_ancestors(node, -nr, -size, mtime, cluster,
                                         update_statistics_ancestors_depth)

        s = select([self.versions.c.hash, self.versions.c.serial])
        s = s.where(where_clause)
        r = self.conn.execute(s)
        hashes = []
        serials = []
        for row in r.fetchall():
            hashes += [row[0]]
            serials += [row[1]]
        r.close()

        #delete versions
        s = self.versions.delete().where(where_clause)
        r = self.conn.execute(s)
        r.close()

        #delete nodes
        s = select([self.nodes.c.node],
                   and_(self.nodes.c.node == node,
                        select([func.count(self.versions.c.serial)],
                               self.versions.c.node == self.nodes.c.node).
                        as_scalar() == 0))
        rp = self.conn.execute(s)
        nodes = [row[0] for row in rp.fetchall()]
        rp.close()
        if nodes:
            s = self.nodes.delete().where(self.nodes.c.node.in_(nodes))
            self.conn.execute(s).close()

        return hashes, size, serials

    def node_remove(self, node, update_statistics_ancestors_depth=None):
        """Remove the node specified.
           Return false if the node has children or is not found.
        """

        if self.node_count_children(node):
            return False

        mtime = time()
        s = select([func.count(self.versions.c.serial),
                    func.sum(self.versions.c.size),
                    self.versions.c.cluster])
        s = s.where(self.versions.c.node == node)
        s = s.group_by(self.versions.c.cluster)
        r = self.conn.execute(s)
        for population, size, cluster in r.fetchall():
            self.statistics_update_ancestors(
                node, -population, -safe_long(size), mtime, cluster,
                update_statistics_ancestors_depth)
        r.close()

        s = self.nodes.delete().where(self.nodes.c.node == node)
        self.conn.execute(s).close()
        return True

    def node_accounts(self, accounts=()):
        s = select([self.nodes.c.path, self.nodes.c.node])
        s = s.where(and_(self.nodes.c.node != 0,
                         self.nodes.c.parent == 0))
        if accounts:
            s = s.where(self.nodes.c.path.in_(accounts))
        r = self.conn.execute(s)
        rows = r.fetchall()
        r.close()
        return rows

    def node_account_quotas(self):
        s = select([self.nodes.c.path, self.policy.c.value])
        s = s.where(and_(self.nodes.c.node != 0,
                         self.nodes.c.parent == 0))
        s = s.where(self.nodes.c.node == self.policy.c.node)
        s = s.where(self.policy.c.key == 'quota')
        r = self.conn.execute(s)
        rows = r.fetchall()
        r.close()
        return dict(rows)

    def node_account_usage(self, account=None, project=None, cluster=0):
        """Return a dict of dicts with the project usage for a specific account

        Keyword arguments:
        account -- (default None: list usage for all accounts)
        project -- (default None: list usage for all projects)
        cluster -- list current, history or deleted usage (default 0: normal)
        """

        n1 = self.nodes.alias('n1')
        n2 = self.nodes.alias('n2')
        n3 = self.nodes.alias('n3')

        s = select([n3.c.path, self.policy.c.value,
                    func.sum(self.versions.c.size)])
        s = s.where(self.policy.c.key == 'project')
        s = s.where(self.policy.c.node == n2.c.node)
        s = s.where(n1.c.node == self.versions.c.node)
        s = s.where(self.versions.c.cluster == cluster)
        s = s.where(n1.c.parent == n2.c.node)
        s = s.where(n2.c.parent == n3.c.node)
        s = s.where(n3.c.parent == 0)
        s = s.where(n3.c.node != 0)
        s = s.group_by(n3.c.path, self.policy.c.value)
        if account:
            s = s.where(n3.c.path == account)
        if project:
            s = s.where(self.policy.c.value == project)
        r = self.conn.execute(s)
        rows = r.fetchall()
        r.close()
        d = defaultdict(lambda: defaultdict(dict))
        for account, project, usage in rows:
            d[account][project][DEFAULT_DISKSPACE_RESOURCE] = \
                    safe_long(usage)
        return d

    def node_project_usage(self, project=None, cluster=0):
        """Return a dict of dicts with the project usage for a specific account

        Keyword arguments:
        project -- (default None: list usage for all projects)
        cluster -- list current, history or deleted usage (default 0: normal)
        """

        n1 = self.nodes.alias('n1')
        n2 = self.nodes.alias('n2')
        n3 = self.nodes.alias('n3')

        s = select([self.policy.c.value,
                    func.sum(self.versions.c.size)])
        s = s.where(self.policy.c.key == 'project')
        s = s.where(self.policy.c.node == n2.c.node)
        s = s.where(n1.c.node == self.versions.c.node)
        s = s.where(self.versions.c.cluster == cluster)
        s = s.where(n1.c.parent == n2.c.node)
        s = s.where(n2.c.parent == n3.c.node)
        # s = s.where(n3.c.parent == 0)
        # s = s.where(n3.c.node != 0)
        s = s.group_by(self.policy.c.value)
        if project:
            s = s.where(self.policy.c.value == project)
        r = self.conn.execute(s)
        rows = r.fetchall()
        r.close()
        d = defaultdict(dict)
        for project, usage in rows:
            d[project][DEFAULT_DISKSPACE_RESOURCE] = safe_long(usage)
        return d

    def node_container_usage(self, path=None, cluster=0):
        """Return container usage"""

        n1 = self.nodes.alias('n1')
        n2 = self.nodes.alias('n2')
        p = self.policy.alias('p')
        v = self.versions.alias('v')

        s = select([func.sum(v.c.size)])
        s = s.where(p.c.key == 'project')
        s = s.where(p.c.node == n2.c.node)
        s = s.where(n1.c.node == v.c.node)
        s = s.where(n1.c.parent == n2.c.node)
        s = s.where(n2.c.path == path)
        s = s.where(v.c.cluster == cluster)

        r = self.conn.execute(s)
        row = r.fetchone()
        r.close()
        return safe_long((row[0]))

    def policy_get(self, node):
        s = select([self.policy.c.key, self.policy.c.value],
                   self.policy.c.node == node)
        r = self.conn.execute(s)
        d = dict(r.fetchall())
        r.close()
        return d

    def policy_set(self, node, policy):
        #insert or replace
        for k, v in policy.iteritems():
            s = self.policy.update().where(and_(self.policy.c.node == node,
                                                self.policy.c.key == k))
            s = s.values(value=v)
            rp = self.conn.execute(s)
            rp.close()
            if rp.rowcount == 0:
                s = self.policy.insert()
                values = {'node': node, 'key': k, 'value': v}
                r = self.conn.execute(s, values)
                r.close()

    def statistics_get(self, node, cluster=0):
        """Return population, total size and last mtime
           for all versions under node that belong to the cluster.
        """

        s = select([self.statistics.c.population,
                    self.statistics.c.size,
                    self.statistics.c.mtime])
        s = s.where(and_(self.statistics.c.node == node,
                         self.statistics.c.cluster == cluster))
        r = self.conn.execute(s)
        row = r.fetchone()
        r.close()
        return row

    def statistics_update(self, node, population, size, mtime, cluster=0):
        """Update the statistics of the given node.
           Statistics keep track the population, total
           size of objects and mtime in the node's namespace.
           May be zero or positive or negative numbers.
        """
        s = select([self.statistics.c.population, self.statistics.c.size],
                   and_(self.statistics.c.node == node,
                        self.statistics.c.cluster == cluster))
        rp = self.conn.execute(s)
        r = rp.fetchone()
        rp.close()
        if not r:
            prepopulation, presize = (0, 0)
        else:
            prepopulation, presize = r
        population += prepopulation
        population = max(population, 0)
        size += presize

        #insert or replace
        #TODO better upsert
        u = self.statistics.update().where(and_(
            self.statistics.c.node == node,
            self.statistics.c.cluster == cluster))
        u = u.values(population=population, size=size, mtime=mtime)
        rp = self.conn.execute(u)
        rp.close()
        if rp.rowcount == 0:
            ins = self.statistics.insert()
            ins = ins.values(node=node, population=population, size=size,
                             mtime=mtime, cluster=cluster)
            self.conn.execute(ins).close()

    def statistics_update_ancestors(self, node, population, size, mtime,
                                    cluster=0, recursion_depth=None):
        """Update the statistics of the given node's parent.
           Then recursively update all parents up to the root
           or up to the ``recursion_depth`` (if not None).
           Population is not recursive.
        """

        i = 0
        while True:
            if node == ROOTNODE:
                break
            if recursion_depth is not None and recursion_depth <= i:
                break
            props = self.node_get_properties(node)
            if props is None:
                break
            parent, path = props
            self.statistics_update(parent, population, size, mtime, cluster)
            node = parent
            population = 0  # Population isn't recursive
            i += 1

    def statistics_latest(self, node, before=inf, except_cluster=0):
        """Return population, total size and last mtime
           for all latest versions under node that
           do not belong to the cluster.
        """

        # The node.
        props = self.node_get_properties(node)
        if props is None:
            return None
        parent, path = props

        # The latest version.
        s = select([self.versions.c.serial,
                    self.versions.c.node,
                    self.versions.c.hash,
                    self.versions.c.size,
                    self.versions.c.type,
                    self.versions.c.source,
                    self.versions.c.mtime,
                    self.versions.c.muser,
                    self.versions.c.uuid,
                    self.versions.c.checksum,
                    self.versions.c.cluster,
                    self.versions.c.available,
                    self.versions.c.map_check_timestamp,
                    self.versions.c.mapfile,
                    self.versions.c.is_snapshot])
        if before != inf:
            filtered = select([func.max(self.versions.c.serial)],
                              self.versions.c.node == node)
            filtered = filtered.where(self.versions.c.mtime < before)
        else:
            filtered = select([self.nodes.c.latest_version],
                              self.nodes.c.node == node)
        s = s.where(and_(self.versions.c.cluster != except_cluster,
                         self.versions.c.serial == filtered))
        r = self.conn.execute(s)
        props = r.fetchone()
        r.close()
        if not props:
            return None
        mtime = props.mtime

        # First level, just under node (get population).
        v = self.versions.alias('v')
        s = select([func.count(v.c.serial),
                    func.sum(v.c.size),
                    func.max(v.c.mtime)])
        if before != inf:
            c1 = select([func.max(self.versions.c.serial)],
                        and_(self.versions.c.mtime < before,
                             self.versions.c.node == v.c.node))
        else:
            c1 = select([self.nodes.c.latest_version])
            c1 = c1.where(self.nodes.c.node == v.c.node)
        c2 = select([self.nodes.c.node], self.nodes.c.parent == node)
        s = s.where(and_(v.c.serial == c1,
                         v.c.cluster != except_cluster,
                         v.c.node.in_(c2)))
        rp = self.conn.execute(s)
        r = rp.fetchone()
        rp.close()
        if not r:
            return None
        count = r[0]
        mtime = max(mtime, r[2])
        if count == 0:
            return (0, 0, mtime)

        # All children (get size and mtime).
        # This is why the full path is stored.
        if before != inf:
            s = select([func.count(v.c.serial),
                       func.sum(v.c.size),
                       func.max(v.c.mtime)])
            c1 = select([func.max(self.versions.c.serial)],
                        and_(self.versions.c.mtime < before,
                             self.versions.c.node == v.c.node))
        else:
            d2 = select([self.nodes.c.node, self.nodes.c.latest_version],
                        self.nodes.c.path.like(self.escape_like(path) + '%',
                                               escape=ESCAPE_CHAR)).cte("d2")
            inner_join = \
                self.versions.join(d2,
                                   onclause=(self.versions.c.serial ==
                                             d2.c.latest_version))
            s = select([func.count(self.versions.c.serial),
                       func.sum(self.versions.c.size),
                       func.max(self.versions.c.mtime)],
                       from_obj=[inner_join])

        c2 = select([self.nodes.c.node],
                    self.nodes.c.path.like(self.escape_like(path) + '%',
                                           escape=ESCAPE_CHAR))
        if before != inf:
            s = s.where(and_(v.c.serial == c1,
                        v.c.cluster != except_cluster,
                        v.c.node.in_(c2)))
        else:
            s = s.where(and_(self.versions.c.cluster != except_cluster))

        rp = self.conn.execute(s)
        r = rp.fetchone()
        rp.close()
        if not r:
            return None
        size = safe_long(r[1]) - props.size
        mtime = max(mtime, r[2])
        return (count, size, mtime)

    def nodes_set_latest_version(self, node, serial):
        s = self.nodes.update().where(self.nodes.c.node == node)
        s = s.values(latest_version=serial)
        self.conn.execute(s).close()

    def version_create(self, node, hash, size, type, source, muser, uuid,
                       checksum, cluster=0,
                       update_statistics_ancestors_depth=None,
                       available=MAP_AVAILABLE, map_check_timestamp=None,
                       mapfile=None, is_snapshot=False):
        """Create a new version from the given properties.
           Return the (serial, mtime, mapfile) of the new version.

           If mapfile is not None, set mapfile to this value.
           Otherwise, assign to the mapfile a new unique identifier.

           :raises DatabaseError
        """

        mtime = time()
        if size == 0:
            mapfile = None
        elif mapfile is None:
            mapfile = literal(self.mapfile_prefix) + \
                type_coerce(functions.next_value(self.mapfile_seq), String)
        s = self.versions.insert().returning(self.versions.c.serial,
                                             self.versions.c.mtime,
                                             self.versions.c.mapfile)
        s = s.values(
            node=node, hash=hash, size=size, type=type, source=source,
            mtime=mtime, muser=muser, uuid=uuid, checksum=checksum,
            cluster=cluster, available=available,
            map_check_timestamp=map_check_timestamp,
            mapfile=mapfile,
            is_snapshot=is_snapshot)
        r = self.conn.execute(s)
        serial, mtime, mapfile = r.fetchone()
        r.close()
        self.statistics_update_ancestors(node, 1, size, mtime, cluster,
                                         update_statistics_ancestors_depth)

        self.nodes_set_latest_version(node, serial)

        return serial, mtime, mapfile

    def version_lookup(self, node, before=inf, cluster=0, all_props=True,
                       keys=()):
        """Lookup the current version of the given node.
           If the current version is not found in the given cluster,
           return None.
           If all_props is False, return the version's serial.
           Otherwise:
               If keys is not empty, return only the specific properties
               (by filtering out the invalid ones).

               If keys is empty, return all properties in the order
               (serial, node, hash, size, type, source, mtime, muser, uuid,
                checksum, cluster, available, map_check_timestamp)
               This is bad tactic, since it may have considerable
               impact on the performance.
        """

        v = self.versions.alias('v')
        if not all_props:
            s = select([v.c.serial])
        else:
            if keys:
                cols = [getattr(v.c, col) for col in keys if hasattr(v.c, col)]
            else:
                cols = [v.c.serial, v.c.node, v.c.hash,
                        v.c.size, v.c.type, v.c.source,
                        v.c.mtime, v.c.muser, v.c.uuid,
                        v.c.checksum, v.c.cluster,
                        v.c.available, v.c.map_check_timestamp,
                        v.c.mapfile, v.c.is_snapshot]
            s = select(cols)
        if before != inf:
            c = select([func.max(self.versions.c.serial)],
                       self.versions.c.node == node)
            c = c.where(self.versions.c.mtime < before)
        else:
            c = select([self.nodes.c.latest_version],
                       self.nodes.c.node == node)
        s = s.where(and_(v.c.serial == c,
                         v.c.cluster == cluster))
        r = self.conn.execute(s)
        props = r.fetchone()
        r.close()
        if props:
            return props
        return None

    def version_lookup_bulk(self, nodes, before=inf, cluster=0,
                            all_props=True, order_by_path=False,
                            keys=()):
        """Lookup the current versions of the given nodes.
           Return a list with their properties:
           (serial, node, hash, size, type, source, mtime, muser, uuid,
            checksum, cluster, available, map_check_timestamp).
        """
        if not nodes:
            return ()
        v = self.versions.alias('v')
        n = self.nodes.alias('n')
        if not all_props:
            s = select([v.c.serial])
        else:
            if keys:
                cols = [getattr(v.c, col) for col in keys if hasattr(v.c, col)]
            else:
                cols = [v.c.serial, v.c.node, v.c.hash,
                        v.c.size, v.c.type, v.c.source,
                        v.c.mtime, v.c.muser, v.c.uuid,
                        v.c.checksum, v.c.cluster,
                        v.c.available, v.c.map_check_timestamp,
                        v.c.mapfile, v.c.is_snapshot]
            s = select(cols)
        if before != inf:
            c = select([func.max(self.versions.c.serial)],
                       self.versions.c.node.in_(nodes))
            c = c.where(self.versions.c.mtime < before)
            c = c.group_by(self.versions.c.node)
        else:
            c = select([self.nodes.c.latest_version],
                       self.nodes.c.node.in_(nodes))
        s = s.where(and_(v.c.serial.in_(c),
                         v.c.cluster == cluster))
        if order_by_path:
            s = s.where(v.c.node == n.c.node)
            s = s.order_by(n.c.path)
        else:
            s = s.order_by(v.c.node)
        r = self.conn.execute(s)
        rproxy = r.fetchall()
        r.close()
        return (tuple(row.values()) for row in rproxy)

    def version_get_properties(self, serial, keys=(), props=None,
                               node=None):
        """Return a sequence of values for the properties of
           the version specified by serial and the keys, in the order given.
           If keys is empty, return all properties in the order
           (serial, node, hash, size, type, source, mtime, muser, uuid,
            checksum, cluster, available, map_check_timestamp).
        """

        props = props or self._props
        keys = keys or props.keys()
        v = self.versions.alias()
        cols = [getattr(v.c, p) for p in keys if hasattr(v.c, p)]
        s = select(cols, v.c.serial == serial)
        if node is not None:
            s = s.where(v.c.node == node)
        rp = self.conn.execute(s)
        r = rp.fetchone()
        rp.close()
        return r

    def version_put_property(self, serial, key, value, props=None):
        """Set value for the property of version specified by key."""

        props = props or self._props
        if key not in props:
            return
        s = self.versions.update()
        s = s.where(self.versions.c.serial == serial)
        s = s.values(**{key: value})
        self.conn.execute(s).close()

    def version_recluster(self, serial, cluster,
                          update_statistics_ancestors_depth=None):
        """Move the version into another cluster."""

        props = self.version_get_properties(serial)
        if not props:
            return
        node = props.node
        size = props.size
        oldcluster = props.cluster
        if cluster == oldcluster:
            return

        mtime = time()
        self.statistics_update_ancestors(node, -1, -size, mtime, oldcluster,
                                         update_statistics_ancestors_depth)
        self.statistics_update_ancestors(node, 1, size, mtime, cluster,
                                         update_statistics_ancestors_depth)

        s = self.versions.update()
        s = s.where(self.versions.c.serial == serial)
        s = s.values(cluster=cluster)
        self.conn.execute(s).close()

    def version_remove(self, serial, update_statistics_ancestors_depth=None):
        """Remove the serial specified."""

        props = self.version_get_properties(serial)
        if not props:
            return
        node = props.node
        hash = props.hash
        size = props.size
        cluster = props.cluster

        mtime = time()
        self.statistics_update_ancestors(node, -1, -size, mtime, cluster,
                                         update_statistics_ancestors_depth)

        s = self.versions.delete().where(self.versions.c.serial == serial)
        self.conn.execute(s).close()

        props = self.version_lookup(node, cluster=cluster, all_props=False)
        if props:
            self.nodes_set_latest_version(node, serial)

        return hash, size

    def attribute_get_domains(self, serial, node=None):
        node = node or select([self.versions.c.node],
                              self.versions.c.serial == serial)
        s = select([self.attributes.c.domain],
                   and_(self.attributes.c.serial == serial,
                        self.attributes.c.node == node)).distinct()
        r = self.conn.execute(s)
        l = r.fetchall()
        r.close()
        return [d[0] for d in l]

    def attribute_get(self, serial, domain, keys=()):
        """Return a list of (key, value) pairs of the specific version.

        If keys is empty, return all attributes.
        Othwerise, return only those specified.
        """

        if keys:
            attrs = self.attributes.alias()
            s = select([attrs.c.key, attrs.c.value])
            s = s.where(and_(attrs.c.key.in_(keys),
                             attrs.c.serial == serial,
                             attrs.c.domain == domain))
        else:
            attrs = self.attributes.alias()
            s = select([attrs.c.key, attrs.c.value])
            s = s.where(and_(attrs.c.serial == serial,
                             attrs.c.domain == domain))
        r = self.conn.execute(s)
        l = r.fetchall()
        r.close()
        return l

    def attribute_set(self, serial, domain, node, items, is_latest=True):
        """Set the attributes of the version specified by serial.
           Receive attributes as a mapping object.

           Raises: sqlalchemy.exc.IntegrityError
        """

        if not items:
            return
        s = self.attributes.insert()
        values = [{'serial': serial,
                   'domain': domain,
                   'node': node,
                   'is_latest': is_latest,
                   'key': k,
                   'value': v} for k, v in items.iteritems()]
        self.conn.execute(s, values).close()

    def attribute_del(self, serial, domain, keys=()):
        """Delete attributes of the version specified by serial.
           If keys is empty, delete all attributes.
           Otherwise delete those specified.
        """

        if keys:
            s = self.attributes.delete()
            s = s.where(and_(self.attributes.c.serial == serial,
                             self.attributes.c.domain == domain,
                             self.attributes.c.key.in_(keys)))
            self.conn.execute(s).close()
        else:
            s = self.attributes.delete()
            s = s.where(and_(self.attributes.c.serial == serial,
                             self.attributes.c.domain == domain))
            self.conn.execute(s).close()

    def attribute_copy(self, source, dest):
        s = select(
            [dest, self.attributes.c.domain, self.attributes.c.node,
             self.attributes.c.key, self.attributes.c.value],
            self.attributes.c.serial == source)
        rp = self.conn.execute(s)
        attributes = rp.fetchall()
        rp.close()
        for dest, domain, node, k, v in attributes:
            select_src_node = select(
                [self.versions.c.node],
                self.versions.c.serial == dest)
            # insert or replace
            s = self.attributes.update().where(and_(
                self.attributes.c.serial == dest,
                self.attributes.c.domain == domain,
                self.attributes.c.key == k))
            s = s.values(node=select_src_node, value=v)
            rp = self.conn.execute(s)
            rp.close()
            if rp.rowcount == 0:
                s = self.attributes.insert()
                s = s.values(serial=dest, domain=domain, node=select_src_node,
                             is_latest=True, key=k, value=v)
            self.conn.execute(s).close()

    def attribute_unset_is_latest(self, node, exclude):
        u = self.attributes.update().where(and_(
            self.attributes.c.node == node,
            self.attributes.c.serial != exclude)).values({'is_latest': False})
        self.conn.execute(u)

    def latest_attribute_keys(self, parent, domain, before=inf,
                              except_cluster=0, pathq=None):
        """Return a list with all keys pairs defined
           for all latest versions under parent that
           do not belong to the cluster.
        """

        pathq = pathq or []

        # TODO: Use another table to store before=inf results.
        v = self.versions.alias('v')
        s = select([self.attributes.c.key]).distinct()
        if before != inf:
            filtered = select([func.max(v.c.serial)],
                              and_(v.c.mtime < before,
                                   v.c.node == self.versions.c.node))
        else:
            filtered = select([self.nodes.c.latest_version])
            filtered = filtered.where(self.nodes.c.node ==
                                      self.versions.c.node
                                      ).correlate(self.versions)
        s = s.where(self.versions.c.serial == filtered)
        s = s.where(self.versions.c.cluster != except_cluster)
        s = s.where(self.versions.c.node.in_(select([self.nodes.c.node],
                                             self.nodes.c.parent == parent)))
        s = s.where(self.attributes.c.serial == self.versions.c.serial)
        s = s.where(self.attributes.c.domain == domain)
        s = s.where(self.nodes.c.node == self.versions.c.node)
        s = s.order_by(self.attributes.c.key)
        conja = []
        conjb = []
        for path, match in pathq:
            if match == MATCH_PREFIX:
                conja.append(self.nodes.c.path.like(self.escape_like(path) +
                                                    '%', escape=ESCAPE_CHAR))
            elif match == MATCH_EXACT:
                conjb.append(path)
        if conja or conjb:
            s = s.where(or_(self.nodes.c.path.in_(conjb), *conja))
        rp = self.conn.execute(s)
        rows = rp.fetchall()
        rp.close()
        return [r[0] for r in rows]

    def latest_version_list(self, parent, prefix='', delimiter=None,
                            start='', limit=10000, before=inf,
                            except_cluster=0, pathq=[], domain=None,
                            filterq=[], sizeq=None, all_props=False):
        """Return a (list of (path, serial) tuples, list of common prefixes)
           for the current versions of the paths with the given parent,
           matching the following criteria.

           The property tuple for a version is returned if all
           of these conditions are true:

                a. parent matches

                b. path > start

                c. path starts with prefix (and paths in pathq)

                d. version is the max up to before

                e. version is not in cluster

                f. the path does not have the delimiter occuring
                   after the prefix, or ends with the delimiter

                g. serial matches the attribute filter query.

                   A filter query is a comma-separated list of
                   terms in one of these three forms:

                   key
                       an attribute with this key must exist

                   !key
                       an attribute with this key must not exist

                   key ?op value
                       the attribute with this key satisfies the value
                       where ?op is one of ==, != <=, >=, <, >.

                h. the size is in the range set by sizeq

           The list of common prefixes includes the prefixes
           matching up to the first delimiter after prefix,
           and are reported only once, as "virtual directories".
           The delimiter is included in the prefixes.

           If arguments are None, then the corresponding matching rule
           will always match.

           Limit applies to the first list of tuples returned.

           If all_props is True, return all properties after path,
           not just serial.
        """

        if not start or start < prefix:
            start = strprevling(prefix)
        nextling = strnextling(prefix)

        v = self.versions.alias('v')
        if before != inf:
            d4_insub = select([self.nodes.c.node],
                              self.nodes.c.parent == parent)
            d4_insub = d4_insub.where(and_(
                self.nodes.c.path > bindparam('start'),
                self.nodes.c.path < nextling))

            d4 = select([func.max(v.c.serial).label("vmax"),
                         v.c.node,
                         self.nodes.c.path]).where(v.c.mtime < before)
            d4 = d4.where(v.c.node.in_(d4_insub))
            d4 = d4.where(v.c.node == self.nodes.c.node)
            d4 = d4.group_by(v.c.node, self.nodes.c.path).cte("d4")
            inner_join = \
                d4.join(self.versions,
                        onclause=self.versions.c.serial == d4.c.vmax)
        else:
            d4 = select([self.nodes.c.path,
                         self.nodes.c.node,
                         self.nodes.c.latest_version]).where(
                             self.nodes.c.parent == parent)
            d4 = d4.where(and_(self.nodes.c.path > bindparam('start'),
                               self.nodes.c.path < nextling)).cte("d4")

            inner_join = \
                d4.join(self.versions,
                        onclause=self.versions.c.serial == d4.c.latest_version)
        if not all_props:
            s = select([d4.c.path,
                       self.versions.c.serial],
                       from_obj=[inner_join]).distinct()
        else:
            s = select([d4.c.path,
                       self.versions.c.serial, self.versions.c.node,
                       self.versions.c.hash,
                       self.versions.c.size, self.versions.c.type,
                       self.versions.c.source,
                       self.versions.c.mtime, self.versions.c.muser,
                       self.versions.c.uuid,
                       self.versions.c.checksum,
                       self.versions.c.cluster,
                       self.versions.c.available,
                       self.versions.c.map_check_timestamp,
                       self.versions.c.mapfile,
                       self.versions.c.is_snapshot],
                       from_obj=[inner_join]).distinct()

        s = s.where(self.versions.c.cluster != except_cluster)
        s = s.where(self.versions.c.node == d4.c.node)
        conja = []
        conjb = []
        for path, match in pathq:
            if match == MATCH_PREFIX:
                conja.append(d4.c.path.like(self.escape_like(path) +
                             '%', escape=ESCAPE_CHAR))
            elif match == MATCH_EXACT:
                conjb.append(path)
        if conja or conjb:
            s = s.where(or_(d4.c.path.in_(conjb), *conja))

        if sizeq and len(sizeq) == 2:
            if sizeq[0]:
                s = s.where(self.versions.c.size >= sizeq[0])
            if sizeq[1]:
                s = s.where(self.versions.c.size < sizeq[1])

        if domain and filterq:
            included, excluded, opers = parse_filters(filterq)
            if included:
                subs = select([1])
                subs = subs.where(self.attributes.c.serial ==
                                  self.versions.c.serial
                                  ).correlate(self.versions)
                subs = subs.where(self.attributes.c.domain == domain)
                subs = subs.where(or_(*[self.attributes.c.key.op('=')(x)
                                  for x in included]))
                s = s.where(exists(subs))
            if excluded:
                subs = select([1])
                subs = subs.where(self.attributes.c.serial ==
                                  self.versions.c.serial
                                  ).correlate(self.versions)
                subs = subs.where(self.attributes.c.domain == domain)
                subs = subs.where(or_(*[self.attributes.c.key.op('=')(x)
                                  for x in excluded]))
                s = s.where(not_(exists(subs)))
            if opers:
                for k, o, val in opers:
                    subs = select([1])
                    subs = subs.where(self.attributes.c.serial ==
                                      self.versions.c.serial
                                      ).correlate(self.versions)
                    subs = subs.where(self.attributes.c.domain == domain)
                    subs = subs.where(
                        and_(self.attributes.c.key.op('=')(k),
                             self.attributes.c.value.op(o)(val)))
                    s = s.where(exists(subs))

        s = s.order_by(d4.c.path)

        if not delimiter:
            s = s.limit(limit)
            rp = self.conn.execute(s, start=start)
            r = rp.fetchall()
            rp.close()
            return r, ()

        pfz = len(prefix)
        dz = len(delimiter)
        count = 0
        prefixes = []
        pappend = prefixes.append
        matches = []
        mappend = matches.append
        skip_prefix = None
        one_more = False

        rp = self.conn.execute(s, start=start)

        while count < limit or one_more:
            props_many = rp.fetchmany(10000)
            if not props_many:
                break

            for props in props_many:
                path = props[0]

                if skip_prefix is not None:
                    if path.startswith(skip_prefix):
                        continue
                    skip_prefix = None

                idx = path.find(delimiter, pfz)

                if one_more:
                    one_more = False
                    if idx > 0 and idx + dz != len(path):
                        pf = path[:idx + dz]
                        pappend(pf)
                    break

                if idx > 0 and idx + dz != len(path):
                    pf = path[:idx + dz]
                    pappend(pf)
                    skip_prefix = pf
                    continue

                mappend(props)
                count += 1
                if count >= limit:
                    if idx + dz == len(path):
                        # Get one more, in case there is a path.
                        one_more = True
                    else:
                        break

        rp.close()

        return matches, prefixes

    def latest_uuid(self, uuid, cluster):
        """Return the latest version of the given uuid and cluster.

        Return a (path, serial) tuple.
        If cluster is None, all clusters are considered.

        """

        v = self.versions.alias('v')
        n = self.nodes.alias('n')
        s = select([n.c.path, v.c.serial])
        filtered = select([func.max(self.versions.c.serial)])
        filtered = filtered.where(self.versions.c.uuid == uuid)
        if cluster is not None:
            filtered = filtered.where(self.versions.c.cluster == cluster)
        s = s.where(v.c.serial == filtered)
        s = s.where(n.c.node == v.c.node)

        r = self.conn.execute(s)
        l = r.fetchone()
        r.close()
        return l

    def domain_object_list(self, domain, paths, cluster=None):
        """Return a list of (path, property list, attribute dictionary)
           for the objects in the specific domain and cluster.
        """

        v = self.versions.alias('v')
        n = self.nodes.alias('n')
        a = self.attributes.alias('a')

        props = [n.c.path, v.c.serial, v.c.node, v.c.hash, v.c.size, v.c.type,
                 v.c.source, v.c.mtime, v.c.muser, v.c.uuid, v.c.checksum,
                 v.c.cluster, v.c.available, v.c.map_check_timestamp,
                 v.c.mapfile, v.c.is_snapshot]
        cols = props + [a.c.key, a.c.value]

        s = select(cols)
        if cluster:
            s = s.where(v.c.cluster == cluster)
        s = s.where(v.c.serial == a.c.serial)
        s = s.where(a.c.domain == domain)
        s = s.where(a.c.node == n.c.node)
        s = s.where(a.c.is_latest == true())
        if paths:
            s = s.where(n.c.path.in_(paths))

        r = self.conn.execute(s)
        rows = r.fetchall()
        r.close()

        group_by = itemgetter(slice(len(props)))
        rows.sort(key=group_by)
        groups = groupby(rows, group_by)
        return [(k[0], k[1:], dict([i[len(props):] for i in data])) for
                (k, data) in groups]

    def get_props(self, paths):
        inner_join = \
            self.nodes.join(self.versions,
                            onclause=self.versions.c.serial ==
                            self.nodes.c.latest_version)
        cc = self.nodes.c.path.in_(paths)
        s = select([self.nodes.c.path, self.versions.c.type],
                   from_obj=[inner_join]).where(cc).distinct()
        r = self.conn.execute(s)
        rows = r.fetchall()
        r.close()
        if rows:
            return rows
        return None
