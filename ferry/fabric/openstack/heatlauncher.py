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
            self.ferry_volume = args['image-volume']
            self.default_personality = args['personality']
            self.default_storage = None
            self.default_zone = "az3"
            self.default_security = args['security']
            self.manage_network = args['network']
            self.external_network = args['extnet']
            self.manage_router = args['router']
            self.ssh_key = args['ssh']
            self.ssh_user = args['ssh-user']
            self.keystone_server = args['keystone']
            self.neutron_server = args['neutron']
            self.openstack_user = os.environ['OS_USERNAME']
            self.openstack_pass = os.environ['OS_PASSWORD']
            self.tenant_id = os.environ['OS_TENANT_ID']
            self.tenant_name = os.environ['OS_TENANT_NAME']
            self.auth_tok = os.environ['OS_AUTH_TOKEN']

            # Not all OpenStack providers include Heat yet,
            # so make it simple to pass in the Heat URL
            # via the environment. 
            if 'HEAT_URL' in os.environ:
                self.heat_server = os.environ['HEAT_URL']
            else:
                self.heat_server = args['heat']

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
            'token': self.auth_tok,
            'auth_url' : self.keystone_server
        }
        self.heat = heat_client.Client(heat_api_version, 
                                       self.heat_server, 
                                       **kwargs)

        neutron_api_version = "2.0"
        kwargs['endpoint_url'] = self.neutron_server
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
        plan = { name : { "Type" : "OS::Neutron::Subnet",
                          "Properties" : { "name" : name,
                                           "cidr" : cidr,
                                           "gateway_ip" : gateway,
                                           "enable_dhcp" : "True",
                                           "ip_version" : 4,
                                           "dns_nameservers" : ["8.8.8.7", "8.8.8.8"],
                                           "allocation_pools" : [{ "start" : pool_start,
                                                                   "end" : pool_end }],
                                           "network_id" : { "Ref" : network}}}}
        desc = { "type" : "OS::Neutron::Subnet",
                 "cidr" : cidr,
                 "gateway" : gateway }
        return plan, desc

    def _create_floating_ip(self, name, port):
        """
        Create and attach a floating IP to the supplied port. 
        """
        plan =  { name : { "Type": "OS::Neutron::FloatingIP",
                           "Properties": { "floating_network_id": self.external_network }},
                  name + "_assoc" : { "Type": "OS::Neutron::FloatingIPAssociation",
                                      "Properties": { "floatingip_id": { "Ref" : name },
                                                      "port_id": { "Ref" : port }}}}
        desc = { "type" : "OS::Neutron::FloatingIP" }
        return plan, desc

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

    def _create_server_init(self, instance_name, networks):
        """
        Create the server init process. These commands are run on the
        host after the host has booted up. 
        """
        # user_data = {
        #     "Fn::Base64": {
        #       "Fn::Join": [
        #         "",
        #           [
        #             "#!/bin/bash -v\n",
        #             "umount /mnt\n", 
        #             "parted --script /dev/vdb mklabel gpt\n", 
        #             "parted --script /dev/vdb mkpart primary xfs 0% 100%\n", 
        #             "mkfs.xfs /dev/vdb1\n", 
        #             "mkdir /ferrydata\n",
        #             "mount -o noatime /dev/vdb1 /ferrydata\n",
        #             "chown -R ferry:ferry /ferrydata\n", 
        #             "export FERRY_SCRATCH=/ferrydata\n", 
        #             "export FERRY_DIR=/ferry/master\n", 
        #             "export HOME=/root\n", 
        #             "ferry server &\n"
        #           ]
        #       ]
        #   }}
        user_data = {
            "Fn::Base64": {
              "Fn::Join": [
                "",
                  [
                    "#!/bin/bash -v\n",
                    "export FERRY_SCRATCH=/ferrydata\n", 
                    "export FERRY_DIR=/ferry/master\n" 
                  ]
              ]
          }}
        return user_data

    def _create_router_interface(self, iface_name, router, subnet):
        plan = { iface_name: { "Type": "OS::Neutron::RouterInterface",
                               "Properties": { "router_id": router,
                                               "subnet_id": { "Ref" : subnet }}}}
        desc = { "type" : "OS::Neutron::RouterInterface",
                 "router" : router }
        return plan, desc

    def _create_volume_attachment(self, iface, instance, volume_id):
        plan = { iface: { "Type": "OS::Cinder::VolumeAttachment",
                          "Properties": { "instance_uuid": { "Ref" : instance },
                                          "mountpoint": "/dev/vdc", 
                                          "volume_id": volume_id}}}
        desc = { "type" : "OS::Cinder::VolumeAttachment" }
        return plan, desc

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
        desc = { name : { "type" : "OS::Nova::Server",
                          "ports" : [],
                          "volumes" : [] }}

        # Create a port in each data network. 
        port_descs = []
        for n in data_networks:
            network = n[0]
            subnet = n[1]
            port_name = "ferry-port-%s-%s" % (name, network)
            port_descs.append(self._create_port(port_name, network, sec_group, ref=False))
            plan[name]["Properties"]["networks"].append({ "port" : { "Ref" : port_name }})
            desc[name]["ports"].append( port_name )
            desc[port_name] = { "type" : "OS::Neutron::Port" }

        # Create a port for the manage network.
        port_name = "ferry-port-%s-manage" % name
        port_descs.append(self._create_port(port_name, manage_network, sec_group, ref=False))
        plan[name]["Properties"]["networks"].append({ "port" : { "Ref" : port_name }}) 
        desc[name]["ports"].append(port_name)
        desc[port_name] = { "type" : "OS::Neutron::Port" }

        # Combine all the port descriptions. 
        for d in port_descs:
            plan = dict(plan.items() + d.items())

        # Now add the user script.
        user_data = self._create_server_init(name, data_networks)
        plan[name]["Properties"]["user_data"] = user_data

        return plan, desc

    def _output_instance_info(self, info_name, server_name):
        desc = {info_name : { "Value" : { "Fn::GetAtt" : [server_name, "PrivateIp"]}}}
        return desc

    def _create_floatingip_plan(self, cluster_uuid, ifaces):
        """
        Assign floating IPs to the supplied interfaces/ports. 
        """
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }
        desc = {}
        for i in range(0, len(ifaces)):
            ip_name = "ferry-ip-%s-%d" % (cluster_uuid, i)
            ip_plan, desc[ip_name] = self._create_floating_ip(ip_name, ifaces[i])
            plan["Resources"] = dict(plan["Resources"].items() + ip_plan.items())

        return plan, desc

    def _create_security_plan(self, cluster_uuid, ports):
        """
        Update the security group. 
        """
        sec_group_name = "ferry-sec-%s" % cluster_uuid
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : self._create_security_group(sec_group_name, ports) }
        desc = { sec_group_name : { "type" : "OS::Neutron::SecurityGroup" }}
        return plan, desc

    def _create_network_plan(self, cluster_uuid):
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {},
                 "Outputs" : {} }
        
        network_name = "ferry-net-%s" % cluster_uuid
        network = self._create_network(network_name)

        subnet_name = "ferry-sub-%s" % cluster_uuid
        public_subnet, subnet_desc = self._create_subnet(subnet_name, network_name)

        # Creating an interface between the public router and
        # the new subnet will make this network public. 
        iface_name = "ferry-iface-%s" %  cluster_uuid
        router, router_desc = self._create_router_interface(iface_name, self.manage_router, subnet_name)

        plan["Resources"] = dict(plan["Resources"].items() + network.items())
        plan["Resources"] = dict(plan["Resources"].items() + public_subnet.items())
        plan["Resources"] = dict(plan["Resources"].items() + router.items())
        desc = { network_name : { "type" : "OS::Neutron::Net" },
                 subnet_name : subnet_desc,
                 iface_name : router_desc }

        logging.info("create Heat network: " + str(desc))
        return plan, desc

    def _create_instance_plan(self, cluster_uuid, num_instances, image, size, network, sec_group_name, ctype): 
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {},
                 "Outputs" : {} }
        desc = {}

        for i in range(0, num_instances):
            # Create the actual instances. 
            instance_name = "ferry-instance-%s-%s-%d" % (cluster_uuid, ctype, i)
            instance_plan, instance_desc = self._create_instance(instance_name, image, size, self.manage_network, [network], sec_group_name)
            plan["Resources"] = dict(plan["Resources"].items() + instance_plan.items())
            desc = dict(desc.items() + instance_desc.items())

            # # Attach the Ferry image volume to the instance. 
            # attach_name = "ferry-attach-%s-%s-%d" % (cluster_uuid, ctype, i)
            # vol_plan, vol_desc = self._create_volume_attachment(attach_name, instance_name, self.ferry_volume)
            # plan["Resources"] = dict(plan["Resources"].items() + vol_plan.items())
            # desc = dict(desc.items() + vol_desc.items())

        return plan, desc

    def _launch_heat_plan(self, stack_name, heat_plan, stack_desc):
        """
        Launch the cluster plan.  
        """
        logging.info("launching heat plan: " + str(heat_plan))
        
        # Instruct Heat to create the stack, and wait 
        # for it to complete. 
        resp = self.heat.stacks.create(stack_name=stack_name, template=heat_plan)
        if not self._wait_for_stack(resp["stack"]["id"]):
            logging.warning("Network stack %s CREATE_FAILED" % resp["stack"]["id"])
            return None

        # Now find the physical IDs of all the resources. 
        resources = self._collect_resources(resp["stack"]["id"])
        for r in resources:
            if r["logical_resource_id"] in stack_desc:
                stack_desc[r["logical_resource_id"]]["id"] = r["physical_resource_id"]

        # Record the Stack ID in the description so that
        # we can refer back to it later. 
        stack_desc[stack_name] = { "id" : resp["stack"]["id"],
                                   "type": "OS::Heat::Stack" }
        return stack_desc

    def _update_heat_plan(self, stack_id, stack_plan):
        """
        Update the cluster plan. 
        """
        self.heat.stacks.update(stack_id, template=stack_plan)

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

    def _collect_network_info(self, stack_desc):
        """
        Collect all the ports. 
        """
        ports = self.neutron.list_ports()
        for p in ports['ports']:
            if p['name'] != "":
                port_desc = stack_desc[p['name']]
                port_desc["subnet"] = p['fixed_ips'][0]['subnet_id']
                port_desc["ip_address"] = p['fixed_ips'][0]['ip_address']
        return stack_desc

    def create_app_network(self, cluster_uuid):
        """
        Create a network for a new application. 
        """
        logging.info("creating network for %s" % cluster_uuid)
        stack_plan, stack_desc = self._create_network_plan(cluster_uuid)
        return self._launch_heat_plan("ferry-app-NET-%s" % cluster_uuid, stack_plan, stack_desc)


    def create_app_stack(self, cluster_uuid, num_instances, network, security_group_ports, assign_floating_ip, ctype):
        """
        Create an empty application stack. This includes the instances, 
        security groups, and floating IPs. 
        """

        logging.info("creating security group for %s" % cluster_uuid)
        sec_group_plan, sec_group_desc = self._create_security_plan(cluster_uuid = cluster_uuid,
                                                                      ports = security_group_ports)

        logging.info("creating instances for %s" % cluster_uuid)
        stack_plan, stack_desc = self._create_instance_plan(cluster_uuid = cluster_uuid, 
                                                            num_instances = num_instances, 
                                                            image = self.default_image,
                                                            size = self.default_personality, 
                                                            network = network,
                                                            sec_group_name = sec_group_desc.keys()[0], 
                                                            ctype = ctype)

        # See if we need to assign any floating IPs 
        # for this stack. We need the references to the neutron
        # port which is contained in the description. 
        if assign_floating_ip:
            logging.info("creating floating IPs for %s" % cluster_uuid)
            ifaces = []
            for k in stack_desc.keys():
                if stack_desc[k]["type"] == "OS::Neutron::Port":
                    ifaces.append(k)
            ip_plan, ip_desc = self._create_floatingip_plan(cluster_uuid = cluster_uuid,
                                                            ifaces = ifaces)
        else:
            ip_plan = { "Resources" : {}}
            ip_desc = {}

        # Now we need to combine all these plans and
        # launch the cluster. 
        stack_plan["Resources"] = dict(sec_group_plan["Resources"].items() + 
                                       ip_plan["Resources"].items() + 
                                       stack_plan["Resources"].items())
        stack_desc = dict(stack_desc.items() + 
                          sec_group_desc.items() +
                          ip_desc.items())
        stack_desc = self._launch_heat_plan("ferry-app-%s-%s" % (ctype.upper(), cluster_uuid), stack_plan, stack_desc)

        # Now find all the IP addresses of the various
        # machines. 
        return self._collect_network_info(stack_desc)

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

# def main():
#     fabric = OpenStackLauncherHeat(sys.argv[1])
#     fabric.test_neutron()

# if __name__ == "__main__":
#     main()
