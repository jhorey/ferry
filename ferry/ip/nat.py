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
        self._current_port = 999
        self.reserved_ports = [4000, 5000]
        self._init_state_db()
        self._clear_nat()
        self._init_nat()
        self._repop_nat()
        
    def _init_state_db(self):
        self.mongo = MongoClient(os.environ['MONGODB'], 27017, connectTimeoutMS=6000)
        self.nat_collection = self.mongo['network']['nat']


    def _clear_nat(self):
        logging.warning("clearing nat")
        
        cmds = ['iptables -t nat -D PREROUTING -m addrtype --dst-type LOCAL -j FERRY_CHAIN',
                'iptables -t nat -D OUTPUT -m addrtype --dst-type LOCAL ! --dst 127.0.0.0/8 -j FERRY_CHAIN',
                'iptables -t nat -D OUTPUT -m addrtype --dst-type LOCAL -j FERRY_CHAIN',
                'iptables -t nat -D OUTPUT -j FERRY_CHAIN',
                'iptables -t nat -F FERRY_CHAIN',
                'iptables -t nat -D PREROUTING -j FERRY_CHAIN',
                'iptables -t nat -X FERRY_CHAIN']
        for c in cmds:
            logging.warning(c)
            Popen(c, shell=True)

    def _init_nat(self):
        logging.warning("init nat")
        cmds = ['iptables -t nat -N FERRY_CHAIN',
                'iptables -t nat -A OUTPUT -m addrtype --dst-type LOCAL ! --dst 127.0.0.0/8 -j FERRY_CHAIN',
                'iptables -t nat -A PREROUTING  -m addrtype --dst-type LOCAL -j FERRY_CHAIN']
        for c in cmds:
            logging.warning(c)
            Popen(c, shell=True)

    def _repop_nat(self):
        rules = self.nat_collection.find()
        for r in rules:
            self._save_nat(r['src_ip'], r['src_port'],r['ip'], r['port'])
                              
    def _save_nat(self, source_ip, source_port, dest_ip, dest_port):
        cmds = ['iptables -I FORWARD 1 ! -i drydock0 -o drydock0  -p tcp --dport %s -d %s -j ACCEPT' % (str(dest_port), dest_ip),
                'iptables -t nat -A FERRY_CHAIN -d %s -p tcp --dport %s -j DNAT --to-destination %s:%s' % (source_ip, str(source_port), dest_ip, str(dest_port))]
        for c in cmds:
            logging.warning(c)
            Popen(c, shell=True)

    def _delete_nat(self, source_ip, source_port, dest_ip, dest_port):
        cmds = ['iptables -D FORWARD ! -i drydock0 -o drydock0  -p tcp --dport %s -d %s -j ACCEPT' % (str(dest_port), dest_ip),
                'iptables -t nat -D FERRY_CHAIN -d %s -p tcp --dport %s -j DNAT --to-destination %s:%s' % (source_ip, str(source_port), dest_ip, str(dest_port))]
                
        for c in cmds:
            logging.warning(c)
            Popen(c, shell=True)

    def _save_forwarding_rule(self, source_ip, source_port, dest_ip, dest_port):
        self.nat_collection.insert({ 'ip' : dest_ip,
                                     'port' : dest_port,
                                     'src_ip' : source_ip,
                                     'src_port' : source_port })

    def _delete_forwarding_rule(self, dest_ip, dest_port):
        self.nat_collection.remove( { 'ip' : dest_ip,
                                      'port' : dest_port } )

    def random_port(self):
        while True:
            port = self._current_port
            self._current_port += 1
            if not port in self.reserved_ports:
                return str(port)

    def has_rule(self, dest_ip, dest_port):
        rule = self.nat_collection.find_one( { 'ip' : dest_ip,
                                               'port' : dest_port } )
        if rule:
            return rule['src_ip'], rule['src_port']
        else:
            return None, None

    def delete_rule(self, dest_ip, dest_port):
        """
        Delete the forwarding rule. 
        """
        src_ip, src_port = self.has_rule(dest_ip, dest_port)
        if src_ip:
            self._delete_forwarding_rule(dest_ip, dest_port)
            self._delete_nat(src_ip, src_port, dest_ip, dest_port)
        else:
            logging.warning("no such dest %s:%s" % (dest_ip, dest_port))

    def forward_rule(self, source_ip, source_port, dest_ip, dest_port):
        """
        Add a new forwarding rule. 
        """
        if source_port in self.reserved_ports:
            logging.warning("cannot use reserved port " + source_port)
            return False

        src_ip, src_port = self.has_rule(dest_ip, dest_port)
        if not src_ip:
            self._save_forwarding_rule(source_ip, source_port, dest_ip, dest_port)
            self._save_nat(source_ip, source_port, dest_ip, dest_port)
            return True
        else:
            logging.warning("port " + source_port + " already reserved")
            return False
