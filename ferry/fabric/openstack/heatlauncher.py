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

from heatclient import client as heat_client
import json
import logging
import math
import os
import sys
import yaml

class OpenStackLauncherHeat(object):
    """
    Launches new instances/networks on an OpenStack
    cluster and initializes the instances to run Ferry processes. 
    """
    def __init__(self, conf_file):
        self.docker_registry = None
        self.docker_user = None
        self.heat_server = None
        self.openstack_key = None

        self.networks = {}
        self.stacks = []
        self.num_network_hosts = 128
        self.num_subnet_hosts = 32

        self._init_open_stack(conf_file)

    def _init_open_stack(self, conf_file):
        with open(conf_file, 'r') as f:
            args = yaml.load(f)
            args = args['hp']
            self.default_image = args['image']
            self.default_personality = args['personality']
            self.default_storage = None
            self.default_zone = "az3"
            self.manage_network = args['network']
            self.manage_router = args['router']
            self.ssh_key = args['ssh']
            self.heat_server = os.environ['HEAT_URL']
            self.openstack_user = os.environ['OS_USERNAME']
            self.openstack_pass = os.environ['OS_PASSWORD']
            self.tenant_id = os.environ['OS_TENANT_ID']
            self.tenant_name = os.environ['OS_TENANT_NAME']
            self.auth_tok = os.environ['OS_AUTH_TOKEN']

            self._init_heat_server()

    def _init_heat_server(self):
        # Instantiate the OpenStack clients. 
        if 'HEAT_API_VERSION' in os.environ:
            heat_api_version = os.environ['HEAT_API_VERSION']
        else:
            heat_api_version = '1'
        kwargs = {
            'username' : self.openstack_user,
            'password' : self.openstack_pass,
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant_name,
            'token': self.auth_tok
        }
        print self.auth_tok
        self.heat = heat_client.Client(heat_api_version, 
                                       self.heat_server, 
                                       **kwargs)

    def _define_address_range(self, num_hosts):
        """
        Choose a private address range. 
        """

        # First determine the cidr block. 
        exp = 32 - math.log(num_hosts, 2)

        # Now figure out where to start counting. 
        addr = [10, 0, 0, 0]
        if num_hosts < 256:
            slot = 1
        elif num_hosts < 65536:
            slot = 2
        addr[slot] = len(self.networks)

        # Now set the gateway IP and address.
        gw = "%d.%d.%d.%d" % (addr[0], addr[1], addr[2], 1)
        cidr = "%d.%d.%d.%d/%d" % (addr[0], addr[1], addr[2], addr[3], exp)

        # Define the allocation pool. 
        start_pool = "%d.%d.%d.%d" % (addr[0], addr[1], addr[2], 2)
        end_pool = "%d.%d.%d.%d" % (addr[0], addr[1], addr[2], num_hosts - 2)

        return cidr, gw, start_pool, end_pool

    def _create_network(self, name):
        """
        Create a network (equivalent to VPC). 
        """
        cidr, _, _, _ = self._define_address_range(self.num_network_hosts)
        self.networks[name] = { 'cidr' : cidr,
                                'subnets' : [] }
        desc = { name : { "Type" : "OS::Neutron::Net",
                          "Properties" : { "name" : name }}}
        return desc

    def _create_subnet(self, name, network):
        """
        Create a subnet. The subnet is attached to a network, but
        doesn't have a router associated with it. 
        """

        # Define the subnet range and store the information. 
        cidr, gateway, pool_start, pool_end = self._define_address_range(self.num_subnet_hosts)
        self.networks[network]['subnets'].append( { name : { 'cidr' : cidr,
                                                             'gw' : gateway }} )

        # Create the HEAT description. 
        desc = { name : { "Type" : "OS::Neutron::Subnet",
                          "Properties" : { "name" : name,
                                           "cidr" : cidr,
                                           "gateway_ip" : gateway,
                                           "enable_dhcp" : "True",
                                           "ip_version" : 4,
                                           "dns_nameservers" : ["8.8.8.7", "8.8.8.8"],
                                           "allocation_pools" : [{ "start" : pool_start,
                                                                   "end" : pool_end }],
                                           "network_id" : { "Ref" : network}}}}
        return desc

    def _create_floating_ip(self, name, port):
        """
        Create and attach a floating IP to the supplied port. 
        """
        desc =  { name : { "Type": "OS::Neutron::FloatingIP",
                           "Properties": { "floating_network_id": { "Ref" : self.manage_network }}},
                  name + "_assoc" : { "Type": "OS::Neutron::FloatingIPAssociation",
                                      "Properties": { "floatingip_id": { "Ref" : name },
                                                      "port_id": port }}}
        return desc

    def _create_security_group(self, group_name, ports):
        """
        Create and assign a security group to the supplied server. 
        """

        # Create the basic security group. 
        # This only includes SSH. We can later update the group
        # to include additional ports. 
        desc = { group_name : { "Type" : "OS::Neutron::SecurityGroup",
                                "Properties" : { "name" : group_name,
                                                 "rules" : [ { "protocol" : "icmp" },
                                                             { "protocol" : "tcp",
                                                               "port_range_min" : 22,
                                                               "port_range_max" : 22 }]}}}
        # Additional ports for the security group. 
        for p in ports:
            min_port = p[0]
            max_port = p[0]
            desc[group_name]["Properties"]["rules"].append({ "protocol" : "tcp",
                                                             "port_range_min" : min_port,
                                                             "port_range_max" : max_port })
        return desc
        
    def _create_storage_volume(self, volume_name, server_name, size_gb):
        """
        Create and attach a storage volume to the supplied server. 
        """
        desc = { volume_name : { "Type" : "OS::Cinder::Volume",
                                 "Properties": { "size" : size_db,
                                                 "availability_zone": self.default_zone
                                 }},
                 volume_name + "_attachment" : { "Type" : "OS::Cinder::VolumeAttachment",
                                                 "Properties": { "volume_id" : { "Ref" : volume_name },
                                                                 "instance_uuid": { "Ref" : server_name },
                                                                 "mount_point": "/dev/vdc"
                                                             }}}
        return desc

    def _create_port(self, name, network):
        desc = { name : { "Type" : "OS::Neutron::Port",
                          "Properties" : { "name" : name, 
                                           "network" : { "Ref" : network }}}}
        return desc

    def _create_instance(self, name, image, size, networks):
        """
        Create a new instance
        """

        desc = { name : { "Type" : "OS::Nova::Server",
                          "Properties" : { "name" : name, 
                                           "image" : image,
                                           "key_name" : self.ssh_key, 
                                           "flavor" : size,
                                           "availability_zone" : self.default_zone, 
                                           "networks" : []}}} 

        # Create a port in each network. 
        port_descs = []
        for n in networks:
            port_name = "ferry-port-%s-%s" % (name, n)
            port_descs.append(self._create_port(port_name, n))
            desc[name]["Properties"]["networks"].append({ "port" : { "Ref" : port_name }})

        for d in port_descs:
            desc = dict(desc.items() + d.items())
        return desc

    def _create_router_interface(self, router, subnet):
        desc = { "RouterInterface": {
            "Type": "OS::Neutron::RouterInterface",
            "Properties": {
                "router_id": router,
                "subnet_id": { "Ref" : subnet }
            }
        }}
        return desc

    def _create_heat_network(self, num_instances, image, size): 
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }

        network_name = "ferry-network-%d" % len(self.networks)
        network = self._create_network(network_name)

        subnet_name = "ferry-subnet-%d" % len(self.networks[network_name]["subnets"])
        public_subnet = self._create_subnet(subnet_name, network_name)

        # Creating an interface between the public router and
        # the new subnet will make this network public. 
        router = self._create_router_interface(self.manage_router, subnet_name)

        plan["Resources"] = dict(plan["Resources"].items() + network.items())
        plan["Resources"] = dict(plan["Resources"].items() + public_subnet.items())
        plan["Resources"] = dict(plan["Resources"].items() + router.items())

        return plan

    def _create_heat_plan(self, num_instances, image, size): 
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }

        network_name = "ferry-network-%d" % len(self.networks)
        network = self._create_network(network_name)

        subnet_name = "ferry-subnet-%d" % len(self.networks[network_name]["subnets"])
        public_subnet = self._create_subnet(subnet_name, network_name)

        # Creating an interface between the public router and
        # the new subnet will make this network public. 
        router = self._create_router_interface(self.manage_router, subnet_name)

        plan["Resources"] = dict(plan["Resources"].items() + network.items())
        plan["Resources"] = dict(plan["Resources"].items() + public_subnet.items())
        plan["Resources"] = dict(plan["Resources"].items() + router.items())

        # Create an empty security group for this application.
        # We'll update the rules later. 
        sec_group = self._create_security_group("ferry-secgroup-%d" % len(self.networks), [])
        plan["Resources"] = dict(plan["Resources"].items() + sec_group.items())

        for i in range(0, num_instances):
            instance_name = "instance-%d" % i
            instance = self._create_instance(instance_name, image, size, [self.manage_network, network_name])
            plan["Resources"] = dict(plan["Resources"].items() + instance.items())

        return plan

    def launch_heat_plan(self, stack_name, heat_plan):
        """
        Launch the cluster plan.  
        """
        logging.info("launching HEAT plan: " + str(heat_plan)) 
        resp = self.heat.stacks.create(stack_name=stack_name, template=heat_plan)
        print resp
        # self.stacks.append(json.load(resp))

def main():
    fabric = OpenStackLauncherHeat(sys.argv[1])
    plan = fabric._create_heat_network(1, fabric.default_image, fabric.default_personality)
    fabric.launch_heat_plan("test_stack", plan)
    print json.dumps(plan,
                     sort_keys = True,
                     indent = 2,
                     separators=(',',':'))

if __name__ == "__main__":
    main()
