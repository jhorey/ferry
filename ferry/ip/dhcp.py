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
import requests
from flask import Flask, request
from pymongo import MongoClient

class DHCPClient(object):
    def __init__(self, cidr_block):
        payload = { 'cidr' : cidr_block }
        res = requests.post(DHCP_SERVER + '/cidr', data=payload)

    def assign_ip(self, container):
        payload = { 'container' : json.dumps(container) }
        res = requests.get(DHCP_SERVER + '/ip', params=payload)
        j = json.loads(res.text)
        return j['ip']

    def set_owner(self, ip, container):
        payload = { 'args' : json.dumps({ 'ip' : ip,
                                          'container' : container}) }
        requests.post(DHCP_SERVER + '/node', data=payload)

    def stop_ip(self, ip):
        payload = { 'ip' : ip }
        requests.post(DHCP_SERVER + '/ip', data=payload)

    def free_ip(self, ip):
        payload = { 'ip' : ip }
        requests.delete(DHCP_SERVER + '/ip', data=payload)

class DHCP(object):
    def __init__(self):
        self.ips = {}
        self.num_addrs = 0
        self._init_state_db()

    def assign_cidr(self, cidr_block):
        if self.num_addrs == 0:
            self.latest_ip, self.prefix = self._parse_cidr(cidr_block)
            s = map(int, self.latest_ip.split("."))
            self.num_ips = s[3]
            self.num_addrs = 2**(32 - self.prefix)

    def _init_state_db(self):
        self.mongo = MongoClient(os.environ['MONGODB'], 27017, connectTimeoutMS=6000)
        self.dhcp_collection = self.mongo['network']['dhcp']

    def _parse_cidr(self, block):
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

            self.num_ips += 1
            self.latest_ip = "%d.%d.%d.%d" % (s[0], s[1], s[2], s[3])
            return self.latest_ip

    def stop_ip(self, ip):
        """
        Store the container's IP for future use. 
        """
        self.ips[ip]['status'] = 'stopped'
        self.dhcp_collection.update( { 'ip' : ip },
                                     { '$set' : self.ips[ip] } )

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
                    logging.warning("REASSIGNING IP: " + k)
                    return k
            
        new_ip = self._increment_ip()
        self.ips[new_ip] = { 'status': 'active',
                             'container': None }
        self.dhcp_collection.update( { 'ip' : new_ip },
                                     { '$set' : self.ips[new_ip]} )

        logging.warning("ASSIGNING IP: " + new_ip)
        return new_ip

    def free_ip(self, ip):
        """
        Container is being removed and the IP address should be freed. 
        """
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

DHCP_SERVER = 'http://localhost:5000'
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
