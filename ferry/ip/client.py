# Copyright 2014 OpenCore LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import json
import logging
import requests

DHCP_SERVER = 'http://localhost:5000'
class DHCPClient(object):
    def __init__(self, cidr_block=None):
        if cidr_block:
            payload = { 'cidr' : cidr_block }
            res = requests.post(DHCP_SERVER + '/cidr', data=payload)

    def assign_ip(self, container):
        payload = { 'container' : json.dumps(container) }
        res = requests.get(DHCP_SERVER + '/ip', params=payload)
        j = json.loads(res.text)
        return j['ip']

    def reserve_ip(self, ip):
        payload = { 'ip' : ip }
        res = requests.put(DHCP_SERVER + '/ip', data=payload)

    def set_owner(self, ip, container):
        payload = { 'args' : json.dumps({ 'ip' : ip,
                                          'container' : container}) }
        requests.post(DHCP_SERVER + '/node', data=payload)

    def random_port(self):
        res = requests.get(DHCP_SERVER + '/port')
        return res.text

    def forward_rule(self, source_ip, source_port, dest_ip, dest_port):
        payload = { 'src_ip' : source_ip,
                    'src_port' : source_port,
                    'dest_ip' : dest_ip,
                    'dest_port' : dest_port }
        requests.post(DHCP_SERVER + '/port', data={'args': json.dumps(payload)})

    def delete_rule(self, dest_ip, dest_port):
        payload = { 'dest_ip' : dest_ip,
                    'dest_port' : dest_port }
        requests.delete(DHCP_SERVER + '/port', data={'args': json.dumps(payload)})

    def clean_rules(self):
        requests.delete(DHCP_SERVER + '/ports')

    def stop_ip(self, ip):
        payload = { 'ip' : ip }
        requests.post(DHCP_SERVER + '/ip', data=payload)

    def free_ip(self, ip):
        payload = { 'ip' : ip }
        requests.delete(DHCP_SERVER + '/ip', data=payload)
