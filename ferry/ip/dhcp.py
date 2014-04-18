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
import os
from flask import Flask, request
from pymongo import MongoClient
from ferry.ip.nat import NAT

class DHCP(object):
    def __init__(self):
        self.free_ips = []
        self.reserved_ips = []
        self.ips = {}
        self.num_ips = 1
        self.num_addrs = 0
        self.nat = NAT()
        self._init_state_db()

    def assign_cidr(self, cidr_block):
        if self.num_addrs == 0:
            self.cidr_collection.insert( { 'cidr' : cidr_block } )
            self._parse_cidr(cidr_block)

    def _parse_cidr(self, cidr_block):
        self.gw_ip, self.prefix = self._parse_cidr_address(cidr_block)
        addr = map(int, self.gw_ip.split("."))
        if self.prefix == 24:
            self.latest_ip = "%d.%d.%d.0" % (addr[0], addr[1], addr[2])
        elif self.prefix == 16:
            self.latest_ip = "%d.%d.0.0" % (addr[0], addr[1])
        self.num_addrs = 2**(32 - self.prefix)

    def _init_state_db(self):
        self.mongo = MongoClient(os.environ['MONGODB'], 27017, connectTimeoutMS=6000)
        self.dhcp_collection = self.mongo['network']['dhcp']
        self.cidr_collection = self.mongo['network']['cidr']

        cidr = self.cidr_collection.find_one()
        if cidr:
            logging.warning("recovering network gateway: " + str(cidr['cidr']))
            self._parse_cidr(cidr['cidr'])

        all_ips = self.dhcp_collection.find()
        if all_ips:
            logging.warning("recovering assigned IP addresses")
            for ip_status in all_ips:
                ip = ip_status['ip']
                status = ip_status['status']
                self.num_ips += 1
                self.ips[ip] = { 'status' : status }

                if status == 'free':
                    self.free_ips.append(ip)
                else:
                    self.ips[ip]['container'] = ip_status['container']

                self._recover_latest_ip(ip)

    def _recover_latest_ip(self, ip):
        l = map(int, self.latest_ip.split("."))
        s = map(int, ip.split("."))

        for i in [0, 1, 2, 3]:
            if s[i] > l[i]:
                self.latest_ip = ip
                break
            elif l[i] > s[i]:
                break
                
    def _parse_cidr_address(self, block):
        s = block.split("/")
        return s[0], int(s[1])

    def _increment_ip(self):
        if self.num_ips < self.num_addrs:
            s = map(int, self.latest_ip.split("."))
            for i in [3, 2, 1, 0]:
                if s[i] < 255:
                    s[i] += 1
                    break
                else:
                    s[i] = 0

            # Make sure we skip over the gateway IP. 
            self.latest_ip = "%d.%d.%d.%d" % (s[0], s[1], s[2], s[3])
            if self.latest_ip == self.gw_ip:
                return self._increment_ip()
            elif self.latest_ip in self.reserved_ips:
                return self._increment_ip()
            else:
                self.num_ips += 1
                return self.latest_ip

    def _get_new_ip(self):
        if len(self.free_ips) > 0:
            return self.free_ips.pop(0)
        else:
            return self._increment_ip()

    def random_port(self):
        """
        Get a random port
        """
        return self.nat.random_port()

    def clean_rules(self):
        """
        Clean all rules
        """
        self.nat._clear_nat()

    def delete_rule(self, dest_ip, dest_port):
        """
        Delete port forwarding
        """
        self.nat.delete_rule(dest_ip, dest_port)

    def forward_rule(self, source_ip, source_port, dest_ip, dest_port):
        """
        Port forwarding
        """
        self.nat.forward_rule(source_ip, source_port, dest_ip, dest_port)

    def stop_ip(self, ip):
        """
        Store the container's IP for future use. 
        """
        self.ips[ip]['status'] = 'stopped'
        self.dhcp_collection.update( { 'ip' : ip },
                                     { '$set' : self.ips[ip] },
                                     upsert = True )

    def reserve_ip(self, ip):
        """
        Reserve an IP. This basically takes this IP out of commission. 
        """
        self.reserved_ips.append(ip)

    def assign_ip(self, container):
        """
        Assign a new IP address. If the container is on the stopped list
        then re-assign the same IP address. 
        """
        if 'container' in container:
            for k in self.ips.keys():
                v = self.ips[k]
                if v['container'] == container['container']:
                    self.ips[k]['status'] = 'active'
                    self.dhcp_collection.update( { 'ip' : k },
                                                 { '$set' : { 'status' : 'active' }} )
                                                 
                    return k
            
        new_ip = self._get_new_ip()
        self.ips[new_ip] = { 'status': 'active',
                             'container': None }
        self.dhcp_collection.update( { 'ip' : new_ip },
                                     { '$set' : self.ips[new_ip]},
                                     upsert = True )
        return new_ip

    def free_ip(self, ip):
        """
        Container is being removed and the IP address should be freed. 
        """
        self.free_ips.append(ip)
        self.ips[ip] = { 'status': 'free' }
        self.dhcp_collection.update( { 'ip' : ip },
                                     { '$set' : self.ips[ip] } )

    def set_owner(self, ip, container):
        """
        Set the owner of this IP address. 
        """
        self.ips[ip]['container'] = container
        self.dhcp_collection.update( { 'ip' : ip },
                                     { '$set' : { 'container' : container}} )

dhcp = DHCP()
app = Flask(__name__)

@app.route('/cidr', methods=['POST'])
def assign_cidr():
    cidr = request.form['cidr']
    dhcp.assign_cidr(cidr)
    return ""

@app.route('/ip', methods=['GET'])
def assign_ip():
    container = json.loads(request.args['container'])
    ip = dhcp.assign_ip(container)
    return json.dumps( { 'ip' : ip } )

@app.route('/ip', methods=['POST'])
def stop_ip():
    ip = request.form['ip']
    dhcp.stop_ip(ip)
    return ""

@app.route('/ip', methods=['PUT'])
def reserve_ip():
    ip = request.form['ip']
    dhcp.reserve_ip(ip)
    return ""

@app.route('/port', methods=['GET'])
def random_port():
    return dhcp.random_port()

@app.route('/port', methods=['POST'])
def forward_rule():
    args = json.loads(request.form['args'])
    dhcp.forward_rule(args['src_ip'], args['src_port'], args['dest_ip'], args['dest_port'])
    return ""

@app.route('/port', methods=['DELETE'])
def delete_rule():
    args = json.loads(request.form['args'])
    dhcp.delete_rule(args['dest_ip'], args['dest_port'])
    return ""

@app.route('/ports', methods=['DELETE'])
def clean_rules():
    dhcp.clean_rules()
    return ""

@app.route('/ip', methods=['DELETE'])
def free_ip():
    ip = request.form['ip']
    dhcp.free_ip(ip)
    return ""

@app.route('/node', methods=['POST'])
def set_owner():
    args = json.loads(request.form['args'])
    dhcp.set_owner(args['ip'], args['container'])
    return ""
