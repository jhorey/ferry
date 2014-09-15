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
import math
import os
import sys
import time
import yaml

class AWSLauncher(object):
    """
    Launches new instances/networks on an AWS
    cluster and initializes the instances to run Ferry processes. 
    """
    def __init__(self, conf_file):
        self.docker_registry = None
        self.docker_user = None

        self.networks = {}
        self.stacks = {}
        self.num_network_hosts = 128
        self.num_subnet_hosts = 32

        self._init_aws_stack(conf_file)

    def _init_aws_stack(self, conf_file):
        with open(conf_file, 'r') as f:
            args = yaml.load(f)

            params = args['aws']['params']
            self.default_dc = params['dc']
            self.default_zone = params['zone']

            deploy = args['hp']['deploy']
            self.default_image = deploy['image']
            self.ferry_volume = deploy['image-volume']
            self.default_personality = deploy['personality']
            self.ssh_key = deploy['ssh']
            self.ssh_user = deploy['ssh-user']

    def _define_address_range(self, num_hosts):
        """
        Choose a private address range. 
        """

        # First determine the cidr block. 
        exp = 32 - math.log(num_hosts, 2)

        # Now figure out where to start counting. As a note
        # we reserve one of the networks for management. 
        addr = [10, 0, 0, 0]
        if num_hosts < 256:
            slot = 1
        elif num_hosts < 65536:
            slot = 2
        addr[slot] = len(self.networks) + 1

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

        desc = { name : { "Type" : "AWS::EC2::VPC",
                          "Properties" : { "CidrBlock" : cidr }}}
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

        plan = { name : { "Type" : "AWS::EC2::Subnet",
                          "Properties" : { "CidrBlock" : cidr,
                                           "AvailabilityZone" : self.default_zone, 
                                           "VpcId" : { "Ref" : network}}}}

        desc = { "type" : "AWS::EC2::Subnet",
                 "cidr" : cidr }
        return plan, desc

    def _create_security_group(self, group_name, ports, internal):
        """
        Create and assign a security group to the supplied server. 
        """
        # Create the basic security group. 
        # This only includes SSH. We can later update the group
        # to include additional ports. 
        desc = { group_name : { "Type" : "AWS::EC2::SecurityGroup",
                                "Properties" : { "GroupDescription" : "Ferry firewall rules", 
                                                 "VpcId" : { "Ref" : network }, 
                                                 "SecurityGroupIngress" : [ { "IpProtocol" : "icmp",
                                                                              "CidrIp": "0.0.0.0/0" },
                                                                            { "IpProtocol" : "tcp",
                                                                              "CidrIp": "0.0.0.0/0",
                                                                              "FromPort" : 22, 
                                                                              "ToPort" : 22 }]}}}
        # Ports for internal connections. 
        for p in ports:
            min_port = p[0]
            max_port = p[1]
            desc[group_name]["Properties"]["SecurityGroupIngress"].append({ "IpProtocol" : "tcp",
                                                                            "CidrIp": "0.0.0.0/0",
                                                                            "FromPort" : min_port, 
                                                                            "ToPort" : max_port })

        # Additional ports for the security group. These
        # port values can only be accessed from within the same network. 
        for p in internal:
            min_port = p[0]
            max_port = p[1]
            desc[group_name]["Properties"]["SecurityGroupIngress"].append({ "IpProtocol" : "tcp",
                                                                            "CidrIp": self.subnet["cidr"],
                                                                            "FromPort" : min_port,
                                                                            "ToPort" : max_port })
        return desc
        
    def _create_port(self, name, network, sec_group, ref=True):
        """
        Create a network interface and attachment 
        """

        desc = { name : { "Type" : "AWS::EC2::NetworkInterface",
                          "Properties" : { }}}
                                           
        return desc

    def _create_server_init(self, instance_name):
        """
        Create the server init process. These commands are run on the
        host after the host has booted up. 
        """

        user_data = {
            "Fn::Base64": {
              "Fn::Join": [
                "",
                  [
                    "#!/bin/bash -v\n",
                    "umount /mnt\n", 
                    "parted --script /dev/vdb mklabel gpt\n", 
                    "parted --script /dev/vdb mkpart primary xfs 0% 100%\n",
                    "mkfs.xfs /dev/vdb1\n", 
                    "mkdir /ferry/data\n",
                    "mkdir /ferry/keys\n",
                    "mkdir /ferry/containers\n",
                    "mount -o noatime /dev/vdb1 /ferry/data\n",
                    "export FERRY_SCRATCH=/ferry/data\n", 
                    "export FERRY_DIR=/ferry/master\n",
                    "echo export FERRY_SCRATCH=/ferry/data >> /etc/profile\n", 
                    "echo export FERRY_DIR=/ferry/master >> /etc/profile\n",
                    "export HOME=/root\n",
                    "export USER=root\n",
                    "mkdir /home/ferry/.ssh\n",
                    "cp /home/%s/.ssh/authorized_keys /home/ferry/.ssh/\n" % self.default_user,
                    "cp /home/%s/.ssh/authorized_keys /root/.ssh/\n" % self.default_user,
                    "chown -R ferry:ferry /home/ferry/.ssh\n",
                    "chown -R ferry:ferry /ferry/data\n",
                    "chown -R ferry:ferry /ferry/keys\n",
                    "chown -R ferry:ferry /ferry/containers\n",
                    "ferry server -n\n",
                    "sleep 3\n"
                  ]
              ]
          }}
        return user_data

    def _create_instance(self, name, image, size, sec_group):
        """
        Create a new instance
        """
        plan = { name : { "Type" : "AWS::EC2::Instance",
                          "Properties" : { "ImageId" : image,
                                           "InstanceType" : size,
                                           "KeyName" : self.ssh_key, 
                                           "AvailabilityZone" : self.default_zone, 
                                           "SecurityGroups" : [ { "Ref" : sec_group } ] }}} 
        desc = { name : { "type" : "AWS::EC2::Instance",
                          "ports" : [],
                          "volumes" : [] }}

        # Now add the user script.
        user_data = self._create_server_init(name)
        plan[name]["Properties"]["UserData"] = user_data

        return plan, desc

    def _create_security_plan(self, cluster_uuid, ports, internal, ctype):
        """
        Update the security group. 
        """
        sec_group_name = "ferry-sec-%s" % cluster_uuid
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated CloudFormation plan",
                 "Resources" : self._create_security_group(sec_group_name, ports, internal) }
        desc = { sec_group_name : { "type" : "AWS::EC2::SecurityGroup" }}
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

        plan["Resources"] = dict(plan["Resources"].items() + network.items())
        plan["Resources"] = dict(plan["Resources"].items() + public_subnet.items())
        desc = { network_name : { "type" : "OS::Neutron::Net" },
                 subnet_name : subnet_desc }

        logging.info("create Heat network: " + str(desc))
        return plan, desc

    def _create_instance_plan(self, cluster_uuid, num_instances, image, size, sec_group_name, ctype): 
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {},
                 "Outputs" : {} }
        desc = {}

        for i in range(0, num_instances):
            # Create the actual instances. 
            instance_name = "ferry-instance-%s-%s-%d" % (cluster_uuid, ctype, i)
            instance_plan, instance_desc = self._create_instance(instance_name, image, size, self.manage_network, sec_group_name)
            plan["Resources"] = dict(plan["Resources"].items() + instance_plan.items())
            desc = dict(desc.items() + instance_desc.items())


        return plan, desc

    def _launch_heat_plan(self, stack_name, heat_plan, stack_desc):
        """
        Launch the cluster plan.  
        """
        logging.info("launching heat plan: " + str(heat_plan))

    def _collect_resources(self, stack_id):
        """
        Collect all the stack resources so that we can create
        additional plans and use IDs. 
        """
        logging.warning("collect resources")

    def _collect_network_info(self, stack_desc):
        """
        Collect all the ports. 
        """
        logging.warning("collect network")

    def create_app_network(self, cluster_uuid):
        """
        Create a network for a new application. 
        """
        logging.info("creating network for %s" % cluster_uuid)
        stack_plan, stack_desc = self._create_network_plan(cluster_uuid)
        return self._launch_heat_plan("ferry-app-NET-%s" % cluster_uuid, stack_plan, stack_desc)


    def _create_app_stack(self, cluster_uuid, num_instances, security_group_ports, internal_ports, assign_floating_ip, ctype):
        """
        Create an empty application stack. This includes the instances, 
        security groups, and floating IPs. 
        """

        logging.info("creating security group for %s" % cluster_uuid)
        sec_group_plan, sec_group_desc = self._create_security_plan(cluster_uuid = cluster_uuid,
                                                                    ports = security_group_ports,
                                                                    internal = internal_ports, 
                                                                    ctype = ctype) 

        return sec_group_plan
        # logging.info("creating instances for %s" % cluster_uuid)
        # stack_plan, stack_desc = self._create_instance_plan(cluster_uuid = cluster_uuid, 
        #                                                     num_instances = num_instances, 
        #                                                     image = self.default_image,
        #                                                     size = self.default_personality, 
        #                                                     sec_group_name = sec_group_desc.keys()[0], 
        #                                                     ctype = ctype)

        # # See if we need to assign any floating IPs 
        # # for this stack. We need the references to the neutron
        # # port which is contained in the description. 
        # if assign_floating_ip:
        #     logging.info("creating floating IPs for %s" % cluster_uuid)
        # else:
        #     ip_plan = { "Resources" : {}}
        #     ip_desc = {}

        # # Now we need to combine all these plans and
        # # launch the cluster. 
        # stack_plan["Resources"] = dict(sec_group_plan["Resources"].items() + 
        #                                ip_plan["Resources"].items() + 
        #                                stack_plan["Resources"].items())
        # stack_desc = dict(stack_desc.items() + 
        #                   sec_group_desc.items() +
        #                   ip_desc.items())

        # return stack_plan

        # stack_desc = self._launch_heat_plan("ferry-app-%s-%s" % (ctype.upper(), cluster_uuid), stack_plan, stack_desc)

        # # Now find all the IP addresses of the various
        # # machines. 
        # return self._collect_network_info(stack_desc)

    def alloc(self, cluster_uuid, service_uuid, container_info, ctype, proxy):
        """
        Allocate a new cluster. 
        """
        # Now take the cluster and create the security group
        # to expose all the right ports. 
        sec_group_ports = []
        internal_ports = []
        if ctype == "connector": 
            # Since this is a connector, we need to expose
            # the public ports. For now, we ignore the host port. 
            floating_ip = True
            for c in container_info:
                for p in c['ports']:
                    s = str(p).split(":")
                    if len(s) > 1:
                        sec_group_ports.append( (s[1], s[1]) )
                    else:
                        sec_group_ports.append( (s[0], s[0]) )
        else:
            if proxy:
                # If the controller is acting as a proxy, then it has
                # direct access to the VMs, so the backend shouldn't
                # get any floating IPs. 
                floating_ip = False
            else:
                # Otherwise, the backend should also get floating IPs
                # so that the controller can access it. 
                floating_ip = True

            # We need to create a range tuple, so check if 
            # the exposed port is a range.
            for p in container_info[0]['exposed']:
                s = p.split("-")
                if len(s) == 1:
                    sec_group_ports.append( (s[0], s[0]) )
                else:
                    sec_group_ports.append( (s[0], s[1]) )

            # Also see if there are any ports that should be
            # open within the cluster (but not outside). Typically
            # used for IPC (where ports may be assigned within a random range). 
            for p in container_info[0]['internal']:
                s = p.split("-")
                if len(s) == 1:
                    internal_ports.append( (s[0], s[0]) )
                else:
                    internal_ports.append( (s[0], s[1]) )

        # Tell AWS to allocate the cluster. 
        resources = self._create_app_stack(cluster_uuid = cluster_uuid, 
                                           num_instances = len(container_info), 
                                           security_group_ports = sec_group_ports,
                                           internal_ports = internal_ports, 
                                           assign_floating_ip = floating_ip,
                                           ctype = ctype)
        
        logging.warning("STACK: " + str(resources))

        # Now we need to ask the cluster to start the 
        # Docker containers.
        containers = []
        mounts = {}

        # if resources:
        #     # Store the resources cluster ID. 
        #     self._update_app_db(cluster_uuid, service_uuid, resources)

        #     servers = self._get_servers(resources)
        #     for i in range(0, len(container_info)):
        #         # Fetch a server to run the Docker commands. 
        #         server = servers[i]

        #         # Get the LXC networking options
        #         lxc_opts, private_ip = self._get_net_info(server, self.subnet, resources)

        #         # Now get an addressable IP address. If we're acting as a proxy within
        #         # the same cluster, we can just use the private address. Otherwise
        #         # we'll need to route via the public IP address. 
        #         if proxy:
        #             server_ip = private_ip
        #         else:
        #             server_ip = self._get_public_ip(server, resources)

        #         # Verify that the user_data processes all started properly
        #         # and that the docker daemon is actually running. If it is
        #         # not running, try re-executing. 
        #         if not self.controller._verify_ferry_server(server_ip):
        #             self.controller._execute_server_init(server_ip)

        #         # Copy over the public keys, but also verify that it does
        #         # get copied over properly. 
        #         self.controller._copy_public_keys(container_info[i], server_ip)
        #         if self.controller._verify_public_keys(server_ip):
        #             container, cmounts = self.controller.execute_docker_containers(container_info[i], lxc_opts, private_ip, server_ip)
                
        #             if container:
        #                 mounts = dict(mounts.items() + cmounts.items())
        #                 containers.append(container)
        #         else:
        #             logging.error("could not copy over ssh key!")
        #             return None

        #     # Check if we need to set the file permissions
        #     # for the mounted volumes. 
        #     for c, i in mounts.items():
        #         for _, v in i['vols']:
        #             self.controller.cmd([c], 'chown -R %s %s' % (i['user'], v))
        #     return containers
        # else:
        #     # AWS failed to launch the application stack.
        #     return None
