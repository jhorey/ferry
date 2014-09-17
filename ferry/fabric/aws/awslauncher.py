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

import boto
import boto.cloudformation
import boto.ec2
import boto.vpc
from boto.ec2.address import *
from boto.ec2.networkinterface import *
from boto.exception import BotoServerError, EC2ResponseError
from boto.ec2.blockdevicemapping import BlockDeviceType, EBSBlockDeviceType, BlockDeviceMapping
import ferry.install
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
    def __init__(self, controller):
        self.docker_registry = None
        self.docker_user = None
        
        self.controller = controller
        self.subnets = []
        self.stacks = {}
        self.num_network_hosts = 1024
        self.num_subnet_hosts = 256
        self.vpc_cidr = None

        self._init_aws_stack()

    def _init_aws_stack(self):
        conf = ferry.install.read_ferry_config()
        provider = conf['system']['provider']

        params = conf[provider]['params']
        self.default_dc = params['dc']
        self.default_zone = params['zone']

        # This gives us information about the image to use
        # for the supplied provider. 
        deploy = conf[provider]['deploy']

        self.default_image = deploy['image']
        self.default_personality = deploy['personality']
        self.ssh_key = deploy['ssh']
        self.ssh_user = deploy['ssh-user']

        # Get user credentials
        self.aws_user = deploy['user']
        self.aws_access_key = deploy['access']
        self.aws_secret_key = deploy['secret']
        
        # Check for an existing VPC ID. If there isn't
        # one, we'll just go ahead and allocate one. 
        if 'vpc' in deploy:
            self.vpc_id = deploy['vpc']
        else:
            self.vpc_id = None

        # The user can also supply specific subnets for both
        # data/compute and connectors. If they aren't supplied,
        # then Ferry will just create them automatically. 
        if 'data_subnet' in deploy:
            self.data_subnet = deploy['data_subnet']
        else:
            self.data_subnet = None
        if 'manage_subnet' in deploy:
            self.manage_subnet = deploy['manage_subnet']
        else:
            self.manage_subnet = None

        # The NAT image enables private subnets to communicate
        # with the outside world. The user can supply their own
        # image ID, although they probably shouldn't. 
        if 'nat_image' in deploy:
            self.nat_image = deploy['nat_image']
        else:
            # The default image is the official Amazon VPC NAT
            # with HVM (HVM is compatible with more instance types). 
            self.nat_image = "ami-8b6912bb"

        # Initialize the AWS clients.
        self._init_aws_clients()

    def _init_aws_clients(self):
        # We will need to use both EC2 and VPC. 
        self.ec2 = boto.ec2.connect_to_region(self.default_dc,
                                              aws_access_key_id = self.aws_access_key,
                                              aws_secret_access_key = self.aws_secret_key)
        self.vpc = boto.vpc.VPCConnection(aws_access_key_id = self.aws_access_key,
                                          aws_secret_access_key = self.aws_secret_key)
        self.cf = boto.cloudformation.connect_to_region(self.default_dc, 
                                                        aws_access_key_id = self.aws_access_key,
                                                        aws_secret_access_key = self.aws_secret_key)

    def _get_host_key(self):
        """
        Get the location of the private ssh key. 
        """
        p = self.ssh_key.split("/")
        if len(p) == 1:
            return "/ferry/keys/" + self.ssh_key + ".pem"
        else:
            return self.ssh_key + ".pem"

    def _define_address_range(self, num_hosts, starting_address):
        """
        Choose a private address range. 
        """

        # First determine the cidr block. 
        exp = 32 - math.log(num_hosts, 2)

        # Now figure out where to start counting. As a note
        # we reserve one of the networks for management. 
        addr = map(int, starting_address.split("."))
        if num_hosts <= 256:
            slot = 2
        elif num_hosts <= 65536:
            slot = 1
        addr[slot] = len(self.subnets) + 1

        # Now set the gateway IP and address.
        gw = "%d.%d.%d.%d" % (addr[0], addr[1], addr[2], 1)
        cidr = "%d.%d.%d.%d/%d" % (addr[0], addr[1], addr[2], addr[3], exp)

        # Define the allocation pool. 
        start_pool = "%d.%d.%d.%d" % (addr[0], addr[1], addr[2], 2)
        end_pool = "%d.%d.%d.%d" % (addr[0], addr[1], addr[2], num_hosts - 2)

        return cidr, gw, start_pool, end_pool

    def _create_vpc(self, name):
        """
        Create a network (equivalent to VPC). 
        """
        cidr, _, _, _ = self._define_address_range(self.num_network_hosts,
                                                            "10.0.0.0")
        self.vpc_cidr = cidr.split("/")[0]
        
        desc = { name : { "Type" : "AWS::EC2::VPC",
                          "Properties" : { "CidrBlock" : cidr }}}
        return desc

    def _create_subnet(self, name, network):
        """
        Create a subnet. The subnet is attached to a network, but
        doesn't have a router associated with it. 
        """

        # Define the subnet range and store the information. 
        cidr, gateway, pool_start, pool_end = self._define_address_range(self.num_subnet_hosts, self.vpc_cidr)
        self.subnets.append( { name : { 'cidr' : cidr,
                                        'gw' : gateway }} )

        plan = { name : { "Type" : "AWS::EC2::Subnet",
                          "Properties" : { "CidrBlock" : cidr,
                                           "AvailabilityZone" : self.default_zone, 
                                           "VpcId" : network}}}

        desc = { "type" : "AWS::EC2::Subnet",
                 "cidr" : cidr }
        return plan, desc

    def _create_routetable(self, name, subnet, vpc):
        plan = { name : { "Type" : "AWS::EC2::RouteTable",
                          "Properties" : { "VpcId" : vpc}}}
        desc = { "type" : "AWS::EC2::RouteTable",
                 "vpc" : vpc }
        return plan, desc

    def _create_routeassoc(self, name, table, subnet):
        plan = { name : { "Type" : "AWS::EC2::SubnetRouteTableAssociation",
                          "Properties" : { "SubnetId" : { "Ref" : subnet},
                                           "RouteTableId" : { "Ref" : table } }}}
        desc = { "type" : "AWS::EC2::SubnetRouteTableAssociation",
                 "subnet" : subnet,
                 "table" : table }
        return plan, desc

    def _create_security_group(self, group_name, network, is_ref, ports, internal, outbound):
        """
        Create and assign a security group to the supplied server. 
        """

        # Determine whether we're creating a VPC that we've just created
        # or one that already exists. 
        if is_ref:
            vpc = { "Ref" : network }
        else:
            vpc = network

        # Create the basic security group. 
        # This only includes SSH. We can later update the group
        # to include additional ports. 
        desc = { group_name : { "Type" : "AWS::EC2::SecurityGroup",
                                "Properties" : { "GroupDescription" : "Ferry firewall rules", 
                                                 "VpcId" : vpc, 
                                                 "SecurityGroupIngress" : [ { "IpProtocol" : "tcp",
                                                                              "CidrIp": "0.0.0.0/0",
                                                                              "FromPort" : "22", 
                                                                              "ToPort" : "22" }]}}}
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

        # Outbound ports. This is not required. If the user
        # doesn't supply egress rules, then all outgoing requests are allowed. 
        if len(outbound) > 0:
            desc[group_name]["Properties"]["SecurityGroupEgress"] = []
        for p in outbound:
            min_port = p[0]
            max_port = p[1]
            desc[group_name]["Properties"]["SecurityGroupEgress"].append({ "IpProtocol" : "tcp",
                                                                           "CidrIp": "0.0.0.0/0",
                                                                           "FromPort" : min_port,
                                                                           "ToPort" : max_port })
        return desc
        
    def _create_nic(self, name, network, sec_group, ref=True):
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

    def _create_instance(self, name, subnet, image, size, sec_group, user_data):
        """
        Create a new instance
        """
        plan = { name : { "Type" : "AWS::EC2::Instance",
                          "Properties" : { "ImageId" : image,
                                           "InstanceType" : size,
                                           "KeyName" : self.ssh_key, 
                                           "AvailabilityZone" : self.default_zone, 
                                           "SubnetId" : subnet, 
                                           "SecurityGroupIds" : [ { "Ref" : sec_group } ] }}} 
        desc = { name : { "type" : "AWS::EC2::Instance",
                          "ports" : [],
                          "volumes" : [] }}

        # Now add the user script.
        if user_data:
            plan[name]["Properties"]["UserData"] = user_data

        return plan, desc

    def _create_security_plan(self, sec_group_name, network, is_ref, ports, internal, outbound=[]):
        """
        Update the security group. 
        """

        # We need to replace the '-' character since AWS
        # only likes alphanumeric characters.         
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated CloudFormation plan",
                 "Resources" : self._create_security_group(sec_group_name, network, is_ref, ports, internal, outbound) }
        desc = { sec_group_name : { "type" : "AWS::EC2::SecurityGroup" }}
        return plan, desc

    def _create_vpc_plan(self, network_name):
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }
        
        network = self._create_vpc(network_name)
        plan["Resources"] = dict(plan["Resources"].items() + network.items())

        desc = { network_name : { "type" : "AWS::VPC" } }
        return plan, desc

    def _create_subnet_plan(self, subnet_name, vpc, is_ref, is_public):
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }

        # Determine whether we're creating a VPC that we've just created
        # or one that already exists. 
        if is_ref:
            network = { "Ref" : vpc }
        else:
            network = vpc

        public_subnet, subnet_desc = self._create_subnet(subnet_name, network)
        plan["Resources"] = public_subnet
        return plan, subnet_desc

    def _create_routetable_plan(self, table_name, subnet, vpc, is_ref):
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }

        # Determine whether we're creating a VPC that we've just created
        # or one that already exists. 
        if is_ref:
            network = { "Ref" : vpc }
        else:
            network = vpc

        route_plan, route_desc = self._create_routetable(table_name, subnet, network)
        assoc_plan, assoc_desc = self._create_routeassoc(table_name + "Assoc", table_name, subnet)

        plan["Resources"] = dict(route_plan.items() + assoc_plan.items())
        return plan, dict(route_desc.items() + assoc_desc.items())

    def _create_nat_plan(self, table_name, subnet, vpc, is_ref):
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }

        # Create a NAT security group. This security group is
        # fairly locked down and only lets machines communicate via
        # HTTP and make outbound SSH calls.
        logging.info("creating NAT security group")
        sec_group_name = "FerryNATSec%s" % subnet
        sec_group_plan = self._create_security_group(group_name = sec_group_name, 
                                                     network = vpc,
                                                     is_ref = is_ref, 
                                                     ports = [("80","80"),("443","443")],
                                                     internal = [],
                                                     outbound = [("80","80"),("443","443")])

        # Create the NAT instance. Thsi is the actual machine that
        # handles all the NAT requests. 
        instance_name = "FerryNAT%s" % subnet
        instance_plan, instance_desc = self._create_instance(name = instance_name, 
                                                             subnet = { "Ref" : subnet }, 
                                                             image = self.nat_image, 
                                                             size = self.default_personality,
                                                             sec_group = sec_group_name,
                                                             user_data = None)

        plan["Resources"] = dict(instance_plan.items() + 
                                 sec_group_plan.items())
        desc = instance_desc

        return plan, desc

    def _create_igw_plan(self, name, route_table, vpc, is_ref):
        """
        Create a new internet gateway and associate it 
        with the VPC. 
        """

        # Determine whether we're creating a VPC that we've just created
        # or one that already exists. 
        if is_ref:
            network = { "Ref" : vpc }
        else:
            network = vpc

        # Create a new internet gateway. This one is pretty simple
        # since there are no options ;)
        logging.info("creating IGW")
        igw_plan = { name : { "Type" : "AWS::EC2::InternetGateway" }}

        # Attach the internet gateway to our VPC. 
        attach_plan = { name + "Attach": { "Type" : "AWS::EC2::VPCGatewayAttachment",
                          "Properties" : { "InternetGatewayId" : { "Ref" : name },
                                           "VpcId" : network}}}

        # Also create a new route associated with this
        # internet gateway. This will send all outbound internet
        # traffic to the gateway. 
        route_plan = { name + "Route": { "Type" : "AWS::EC2::Route",
                          "Properties" : { "GatewayId" : { "Ref" : name },
                                           "RouteTableId" : { "Ref" : route_table },
                                           "DestinationCidrBlock" : "0.0.0.0/0" }}}

        desc = { "type" : "AWS::EC2::InternetGateway",
                 "vpc" : network }
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {} }
        plan["Resources"] = dict(igw_plan.items() + 
                                 attach_plan.items() +
                                 route_plan.items() )
        return plan, desc

    def _create_instance_plan(self, cluster_uuid, subnet, num_instances, image, size, sec_group_name, ctype): 
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" : {},
                 "Outputs" : {} }
        desc = {}

        for i in range(0, num_instances):
            # Create the actual instances. 
            instance_name = "FerryInstance%s%s%d" % (cluster_uuid.replace("-", ""), ctype, i)
            user_data = self._create_server_init(instance_name)
            instance_plan, instance_desc = self._create_instance(instance_name, subnet, image, size, self.manage_network, sec_group_name, user_data)
            plan["Resources"] = dict(plan["Resources"].items() + instance_plan.items())
            desc = dict(desc.items() + instance_desc.items())

        return plan, desc

    def _launch_cloudformation(self, stack_name, cloud_plan, stack_desc):
        """
        Launch the cluster plan.  
        """
        try:
            # Try to create the application stack. 
            stack_id = self.cf.create_stack(stack_name, template_body=json.dumps((cloud_plan)))
        except boto.exception.BotoServerError as e:
            logging.error(str(e))
            return None
        except:
            # We could not create the stack. This probably means
            # that the AWS service is temporarily down. 
            logging.error("could not create Cloudformation stack")
            return None

        # Now wait for the stack to be in a completed state
        # before returning. That way we'll know if the stack creation
        # has failed or not. 
        if not self._wait_for_stack(stack_id):
            logging.warning("Heat plan %s CREATE_FAILED" % stack_id)
            return None

        # Now find the physical IDs of all the resources. 
        resources = self._collect_resources(stack_id)
        for r in resources:
            if r.logical_resource_id in stack_desc:
                stack_desc[r.logical_resource_id] = r.physical_resource_id

        # Record the Stack ID in the description so that
        # we can refer back to it later. 
        stack_desc[stack_name] = { "id" : stack_id,
                                   "type": "AWS::CloudFormation::Stack" }

        return stack_desc

    def _wait_for_stack(self, stack_id):
        """
        Wait for stack completion.
        """
        stacks = self.cf.describe_stacks(stack_id)
        for stack in stacks:
            while(True):
                try:
                    if stack.stack_status == "CREATE_COMPLETE":
                        return True
                    elif stack.stack_status == "CREATE_FAILED":
                        return False
                    else:
                        stack.update()
                        time.sleep(4)
                except:
                    logging.error("could not fetch stack status (%s)" % str(stack_id))
                    return False

    def _collect_resources(self, stack_id):
        """
        Collect all the stack resources so that we can create
        additional plans and use IDs. 
        """
        logging.warning("collect resources")
        try:
            resources = self.cf.list_stack_resources(stack_id)
            return resources
        except:
            return []

    def _collect_network_info(self, stack_desc):
        """
        Collect all the ports. 
        """
        logging.warning("collect network")

    def _create_app_stack(self, cluster_uuid, num_instances, security_group_ports, internal_ports, assign_floating_ip, ctype):
        """
        Create an empty application stack. This includes the instances, 
        security groups, and floating IPs. 
        """

        # Check if we need to create a VPC. The VPC will also optionally create two
        # subnets (data and manage). The data subnet is used to store
        # the storage and compute nodes, and is "private". That means no communication 
        # from the outside. The manage subnet is used to store the connectors and 
        # are "public" so that they can get elastic IPs. 
        stack_desc = {}
        stack_plan = {}
        if not self.vpc_id:
            logging.warning("Creating VPC")
            vpc_name = "FerryNet%s" % cluster_uuid.replace("-", "")
            vpc_plan, vpc_desc = self._create_vpc_plan(vpc_name)
            is_ref = True
            stack_plan = vpc_plan
            stack_desc = vpc_desc
        else:
            logging.warning("Using VPC " + str(self.vpc_id))
            vpc_plan = {}
            vpc_name = self.vpc_id
            is_ref = False

        if not self.data_subnet:
            logging.warning("Creating data subnet")
            subnet_name = "FerrySub%s" % cluster_uuid.replace("-", "")
            table_name = "FerryRoute%s" % cluster_uuid.replace("-", "")
            subnet_plan, subnet_desc = self._create_subnet_plan(subnet_name, vpc_name, is_ref, is_public=False)
            table_plan, table_desc = self._create_routetable_plan(table_name, subnet_name, vpc_name, is_ref)
            nat_plan, nat_desc = self._create_nat_plan(table_name, subnet_name, vpc_name, is_ref)

            # Combine the network resources. 
            if len(stack_plan) == 0:
                stack_plan = subnet_plan
            else:
                stack_plan["Resources"] = dict(stack_plan["Resources"].items() + 
                                               subnet_plan["Resources"].items() + 
                                               table_plan["Resources"].items() +
                                               nat_plan["Resources"].items() )
            stack_desc = dict(stack_desc.items() + 
                              subnet_desc.items() + 
                              table_desc.items() +
                              nat_desc.items())

        if not self.manage_subnet:
            logging.warning("Creating manage subnet")
            subnet_name = "FerryManage%s" % cluster_uuid.replace("-", "")
            table_name = "FerryManageRoute%s" % cluster_uuid.replace("-", "")
            igw_name = "FerryManageIGW%s" % cluster_uuid.replace("-", "")
            subnet_plan, subnet_desc = self._create_subnet_plan(subnet_name, vpc_name, is_ref, is_public=False)
            table_plan, table_desc = self._create_routetable_plan(table_name, subnet_name, vpc_name, is_ref)
            igw_plan, igw_desc = self._create_igw_plan(igw_name, table_name, vpc_name, is_ref)

            # Combine the network resources. 
            if len(stack_plan) == 0:
                stack_plan = subnet_plan
            else:
                stack_plan["Resources"] = dict(stack_plan["Resources"].items() + 
                                               subnet_plan["Resources"].items() + 
                                               table_plan["Resources"].items() +
                                               igw_plan["Resources"].items() )
            stack_desc = dict(stack_desc.items() + 
                              subnet_desc.items() + 
                              table_desc.items() +
                              igw_desc.items())

        logging.warning(json.dumps(stack_plan, 
                                   sort_keys=True,
                                   indent=2,
                                   separators=(',',':')))
        stack_desc = self._launch_cloudformation("FerrySubnet%s%s" % (ctype.upper(), cluster_uuid.replace("-", "")), stack_plan, stack_desc)

        # # Create the main data security group. This is the security
        # # group that controls both internal and external communication with
        # # the data subnet. 
        # logging.info("creating security group for %s" % cluster_uuid)
        # sec_group_name = "FerrySec%s" % cluster_uuid.replace("-", "")
        # sec_group_plan, sec_group_desc = self._create_security_plan(sec_group_name = sec_group_name,
        #                                                             network = vpc_name,
        #                                                             is_ref = is_ref,
        #                                                             ports = security_group_ports,
        #                                                             internal = internal_ports)

        # stack_desc = dict(stack_desc.items() + sec_group_desc.items())
        # stack_desc = self._launch_cloudformation("FerryApp%s%s" % (ctype.upper(), cluster_uuid.replace("-", "")), sec_group_plan, stack_desc)

        return stack_desc

        # logging.info("creating instances for %s" % cluster_uuid)
        # stack_plan, stack_desc = self._create_instance_plan(cluster_uuid = cluster_uuid, 
        #                                                     num_instances = num_instances, 
        #                                                     image = self.default_image,
        #                                                     size = self.default_personality, 
        #                                                     sec_group_name = sec_group_desc.keys()[0], 
        #                                                     ctype = ctype)

        # return stack_desc

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

        # stack_desc = self._launch_cloudformation("FerryApp%s%s" % (ctype.upper(), cluster_uuid.replace("-", "")), stack_plan, stack_desc)

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
