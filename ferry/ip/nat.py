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

import logging
import os
from pymongo import MongoClient
from subprocess import Popen, PIPE

class NAT(object):
    def __init__(self):
        self.reserved_ports = []
        self._init_state_db()
        self._clear_nat()
        self._init_nat()
        self._repop_nat()
        
    def _init_state_db(self):
        self.mongo = MongoClient(os.environ['MONGODB'], 27017, connectTimeoutMS=6000)
        self.nat_collection = self.mongo['network']['nat']

    def _clear_nat(self):
        Popen('iptables -t nat -F FERRY_CHAIN', shell=True)
        Popen('iptables -t nat -D PREROUTING -j FERRY_CHAIN', shell=True)
        Popen('iptables -t nat -X FERRY_CHAIN', shell=True)

    def _init_nat(self):
        Popen('iptables -t nat -N FERRY_CHAIN', shell=True)
        Popen('iptables -t nat -A PREROUTING -j FERRY_CHAIN', shell=True)

    def _repop_nat(self):
        rules = self.nat_collection.find()
        for r in rules:
            self._save_nat(r['src_ip'], r['src_port'],r['ip'], r['port'])
                              
    def _save_nat(self, source_ip, source_port, dest_ip, dest_port):
        Popen('iptables -t nat -A FERRY_CHAIN -d %s -p tcp --dport %s -j DNAT --to %s:%s' % (source_ip, source_port, dest_ip, dest_port), shell=True)

    def _delete_nat(self, dest_ip, dest_port):
        Popen('iptables -t nat -D FERRY_CHAIN -d %s -p tcp --dport %s -j DNAT --to %s:%s' % (source_ip, source_port, dest_ip, dest_port), shell=True)

    def _save_forwarding_rule(self, source_ip, source_port, dest_ip, dest_port):
        self.nat_collection.update( { 'ip' : dest_ip },
                                    { '$set' : { 'port': dest_port,
                                                 'src_ip' : source_ip,
                                                 'src_port' : source_port }},
                                     upsert = True )

    def _delete_forwarding_rule(self, dest_ip, dest_port):
        self.nat_collection.remove( { 'ip' : dest_ip,
                                      'port' : dest_port } )

    def has_rule(self, dest_ip, dest_port):
        rule = self.nat_collection.find_one( { 'ip' : dest_ip,
                                               'port' : dest_port } )
        return rule != None

    def delete_rule(self, dest_ip, dest_port):
        """
        Delete the forwarding rule. 
        """
        if self.has_rule(dest_ip, dest_port):
            self._delete_forwarding_rule(dest_ip, dest_port)
            self._delete_nat(dest_ip, dest_port)

    def forward_rule(self, source_ip, source_port, dest_ip, dest_port):
        """
        Add a new forwarding rule. 
        """
        if source_port in self.reserved_ports:
            return False

        if not self.has_rule(dest_ip, dest_port):
            self._save_forwarding_rule(source_ip, source_port, dest_ip, dest_port)
            self._save_nat(source_ip, source_port, dest_ip, dest_port)
            return True
        else:
            return False
