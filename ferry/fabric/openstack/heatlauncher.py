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
from heatclient.exc import HTTPUnauthorized
from neutronclient.neutron import client as neutron_client
import json
import logging
import math
import os
import sys
import time
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
        self.stacks = {}
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
            self.default_security = args['security']
            self.manage_network = args['network']
            self.external_network = args['extnet']
            self.manage_router = args['router']
            self.ssh_key = args['ssh']
            self.keystone_server = args['keystone']
            self.neutron_server = args['neutron']
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
            'include_pass' : True,
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant_name,
            'token': self.auth_tok
        }
        self.heat = heat_client.Client(heat_api_version, 
                                       self.heat_server, 
                                       **kwargs)

        neutron_api_version = "2.0"
        kwargs = {
            'username' : self.openstack_user,
            'password' : self.openstack_pass,
            'include_pass' : True,
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant_name,
            'token': self.auth_tok,
            'endpoint_url' : self.neutron_server,
            'auth_url' : self.keystone_server
        }
        self.neutron = neutron_client.Client(neutron_api_version, 
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
                           "Properties": { "floating_network_id": self.external_network }},
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
                                                 "description" : "Ferry firewall rules", 
                                                 "rules" : [ { "protocol" : "icmp",
                                                               "remote_ip_prefix": "0.0.0.0/0" },
                                                             { "protocol" : "tcp",
                                                               "remote_ip_prefix": "0.0.0.0/0",
                                                               "port_range_min" : 22,
                                                               "port_range_max" : 22 }]}}}
        # Additional ports for the security group. 
        for p in ports:
            min_port = p[0]
            max_port = p[1]
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

    def _create_port(self, name, network, sec_group, ref=True):
        desc = { name : { "Type" : "OS::Neutron::Port",
                          "Properties" : { "name" : name,
                                           "security_groups" : [{ "Ref" : sec_group }]}}}
        if ref:
            desc[name]["Properties"]["network"] = { "Ref" : network }
        else:
            desc[name]["Properties"]["network"] = network 

        return desc

    def _create_server_init(self, instance_name, network_name):
        user_data = {
            "Fn::Base64": {
              "Fn::Join": [
                "",
                  [
                    "#!/bin/bash -v\n",
                    "echo hello > /tmp/foo.txt\n"
                  ]
              ]
          }}
        return user_data

    def _create_instance(self, name, image, size, manage_network, data_networks, sec_group):
        """
        Create a new instance
        """
        plan = { name : { "Type" : "OS::Nova::Server",
                          "Properties" : { "name" : name, 
                                           "image" : image,
                                           "key_name" : self.ssh_key, 
                                           "flavor" : size,
                                           "availability_zone" : self.default_zone, 
                                           "networks" : []}}} 
        desc = { 'name' : name,
                 'OS::Neutron::Port' : [] }

        # Create a port in each data network. 
        port_descs = []
        for n in data_networks:
            port_name = "ferry-port-%s-%s" % (name, n)
            port_descs.append(self._create_port(port_name, n, sec_group, ref=True))
            plan[name]["Properties"]["networks"].append({ "port" : { "Ref" : port_name }})
            desc['OS::Neutron::Port'].append( { 'name' : port_name } )

        # Create a port for the manage network.
        port_name = "ferry-port-%s-manage" % name
        port_descs.append(self._create_port(port_name, manage_network, sec_group, ref=False))
        plan[name]["Properties"]["networks"].append({ "port" : { "Ref" : port_name }}) 
        desc['OS::Neutron::Port'].append( { 'name' : port_name } )

        # Combine all the port descriptions. 
        for d in port_descs:
            plan = dict(plan.items() + d.items())

        # Now add the user script.
        user_data = self._create_server_init(name, data_networks[0])
        plan[name]["Properties"]["user_data"] = user_data

        return plan, desc

    def _create_router_interface(self, iface_name, router, subnet):
        desc = { iface_name: { "Type": "OS::Neutron::RouterInterface",
                               "Properties": { "router_id": router,
                                               "subnet_id": { "Ref" : subnet }}}}
        return desc

    def _output_instance_info(self, info_name, server_name):
        desc = {info_name : { "Value" : { "Fn::GetAtt" : [server_name, "PrivateIp"]}}}
        return desc

    def _update_floating_ips(self, ifaces):
        """
        Assign floating IPs to the supplied interfaces/ports. 
        """
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }
        desc = { "OS::Neutron::FloatingIP" : [] }

        for i in ifaces:
            ip_name = "ferry-ip-%s" % str(i)
            ip_plan = self._create_floating_ip(ip_name, i)
            plan["Resources"] = dict(plan["Resources"].items() + ip_plan.items())
            desc["OS::Neutron::FloatingIP"].append( { "name" : ip_name } )

        return plan, desc

    def _update_security_plan(self, group_name, ports):
        """
        Update the security group. 
        """
        return { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : self._create_security_group(group_name, ports) }

    def _create_heat_plan(self, num_instances, image, size): 
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {},
                 "Outputs" : {} }

        network_name = "ferry-network-%d" % len(self.networks)
        network = self._create_network(network_name)

        subnet_name = "ferry-subnet-%d" % len(self.networks)
        public_subnet = self._create_subnet(subnet_name, network_name)

        # Creating an interface between the public router and
        # the new subnet will make this network public. 
        iface_name = "ferry-iface-%d" %  len(self.networks)
        router = self._create_router_interface(iface_name, self.manage_router, subnet_name)

        plan["Resources"] = dict(plan["Resources"].items() + network.items())
        plan["Resources"] = dict(plan["Resources"].items() + public_subnet.items())
        plan["Resources"] = dict(plan["Resources"].items() + router.items())

        # Create an empty security group for this application.
        # We'll update the rules later. 
        sec_group_name = "ferry-secgroup-%d" % len(self.networks)
        sec_group = self._create_security_group(sec_group_name, [])
        plan["Resources"] = dict(plan["Resources"].items() + sec_group.items())

        desc = { "OS::Neutron::Network" : { "name" : network_name },
                 "OS::Neutron::Subnet" : { "name" : subnet_name } ,
                 "OS::Neutron::RouterInterface" : { "name" : iface_name },
                 "OS::Neutron::SecurityGroup" : { "name" : sec_group_name },
                 "OS::Nova::Server" : []
        }
        for i in range(0, num_instances):
            instance_name = "ferry-instance-%d" % i
            info_name = "info-" + instance_name
            instance_plan, instance_desc = self._create_instance(instance_name, image, size, self.manage_network, [network_name], sec_group_name)
            plan["Resources"] = dict(plan["Resources"].items() + instance_plan.items())
            desc["OS::Nova::Server"].append(instance_desc)

        return plan, desc

    def launch_heat_plan(self, stack_name, heat_plan):
        """
        Launch the cluster plan.  
        """
        resp = self.heat.stacks.create(stack_name=stack_name, template=heat_plan)
        return resp

    def update_heat_plan(self, stack_id, stack_plan, updated_resources):
        """
        Update the cluster plan. 
        """
        if updated_resources:
            resources_plan = dict(stack_plan["Resources"].items() + updated_resources.items())
            heat_plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                          "Description" : "Ferry generated Heat plan",
                          "Resources" : resources_plan,
                          "Outputs" : {} }
        else:
            heat_plan = stack_plan

        print json.dumps(heat_plan,
                         sort_keys = True,
                         indent = 2,
                         separators=(',',':'))
        self.heat.stacks.update(stack_id, template=heat_plan)

    def release_ip_plan(self, ips):
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }

        for i in ips:
            plan["Resources"] = {
                i["name"] : { "Type": "OS::Neutron::FloatingIPAssociation",
                              "Properties": {} }}

        return plan

    def _wait_for_stack(self, stack_id):
        """
        Wait for stack completion.
        """
        while(True):
            try:
                stack = self.heat.stacks.get(stack_id)
                if stack.status == "COMPLETE":
                    return True
                elif stack.status == "FAILED":
                    return False
                else:
                    time.sleep(2)
            except HTTPUnauthorized as e:
                logging.warning(e)

    def _collect_resources(self, stack_id):
        """
        Collect all the stack resources so that we can create
        additional plans and use IDs. 
        """
        resources = self.heat.resources.list(stack_id)
        descs = [r.to_dict() for r in resources]
        return descs

    def _create_stack(self, num_instances):
        print "Creating stack"
        stack_plan, stack_desc = self._create_heat_plan(1, self.default_image, self.default_personality)
        resp = self.launch_heat_plan("test_stack", stack_plan)
        if not self._wait_for_stack(resp["stack"]["id"]):
            logging.warning("Stack %s CREATE_FAILED" % resp["stack"]["id"])

        # Now collect all the resource IDs. 
        print "Collecting resources"
        resources = self._collect_resources(resp["stack"]["id"])
        resource_description = {}
        for r in resources:
            resource_description[r["logical_resource_id"]] = r["physical_resource_id"]
    
        # Update the security groups and floating IPs.
        print "Updating security group and floating IPs"
        pid = []
        for s in stack_desc["OS::Nova::Server"]:
            for p in s["OS::Neutron::Port"]:
                pid.append(resource_description[p["name"]])
        ip_plan, ip_desc = self._update_floating_ips(pid)
        secgroup_plan = self._update_security_plan(stack_desc["OS::Neutron::SecurityGroup"]["name"], [(8000, 8001),(5000,5014)])
        updated_resources = dict(secgroup_plan["Resources"].items() + ip_plan["Resources"].items())
        stack_desc = dict(stack_desc.items() + ip_desc.items())

        self.update_heat_plan(resp["stack"]["id"], stack_plan, updated_resources)
        self._wait_for_stack(resp["stack"]["id"])
        if not self._wait_for_stack(resp["stack"]["id"]):
            logging.warning("Stack %s UPDATE_FAILED" % resp["stack"]["id"])

        self.stacks[resp["stack"]["id"]] = { "desc" : stack_desc,
                                             "resources" : resource_description }
        return resp["stack"]["id"]

    def _delete_stack(self, stack_id):
        # To delete the stack properly, we first need to disassociate
        # the floating IPs. 
        ips = []
        resources = self._collect_resources(stack_id)
        for r in resources:
            if r["resource_type"] == "OS::Neutron::FloatingIP":
                self.neutron.update_floatingip(r["physical_resource_id"], {'floatingip': {'port_id': None}})

        # Now delete the stack. 
        self.heat.stacks.delete(stack_id)

def main():
    fabric = OpenStackLauncherHeat(sys.argv[2])
    if sys.argv[1] == "create":
        stack_id = fabric._create_stack(1)
        logging.info("Stack %s complete" % stack_id)
    else:
        fabric._delete_stack(sys.argv[3])

if __name__ == "__main__":
    main()
