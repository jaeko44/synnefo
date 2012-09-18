# Copyright 2011-2012 GRNET S.A. All rights reserved.
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

from django import template
import calendar
import datetime

register = template.Library()

@register.filter
def monthssince(joined_date):
    now = datetime.datetime.now()
    date = datetime.datetime(year=joined_date.year, month=joined_date.month, day=1)
    months = []
    
    month = date.month
    year = date.year
    timestamp=calendar.timegm( date.utctimetuple() )
    
    while date < now:
        months.append((year, month, timestamp))
        
        if date.month < 12:
            month = date.month + 1
            year = date.year
        else:
            month = 1
            year = date.year + 1
            
        date = datetime.datetime(year=year, month=month, day=1)
        timestamp=calendar.timegm( date.utctimetuple() )
        
    return months
    
@register.filter
def lookup(d, key):
    return d.get(key)


@register.filter
def dkeys(d):
    return d.keys()


@register.filter
def enabled(object_list, is_search):
    if not is_search:
        return object_list
    return [g for g in object_list if g.is_enabled]


@register.filter
def split(object_list, user):
    try:
        d = {}
        d['own'] = [g for g in object_list if user in g.owner.all()]
        d['other'] = list(set(object_list) - set(d['own']))
        return d
    except:
        return {'own': object_list, 'other': ()}


@register.filter
def month_name(month_number):
    return calendar.month_name[month_number]
    

@register.filter
def todate(value, arg = ''):
    secs = int(value) / 1000
    return datetime.datetime.fromtimestamp(secs)
