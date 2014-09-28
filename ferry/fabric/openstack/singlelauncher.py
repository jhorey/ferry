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

import copy
import ferry.install
from ferry.install import Installer
from ferry.config.system.info import System
from heatclient import client as heat_client
from heatclient.exc import HTTPUnauthorized, HTTPNotFound, HTTPBadRequest
import json
import logging
import math
from neutronclient.neutron import client as neutron_client
from novaclient import client as nova_client
import os
from pymongo import MongoClient
import sys
import time
import uuid
import yaml

class SingleLauncher(object):
    """
    Launches new Ferry containers on an OpenStack cluster.

    Unlike the multi-launcher, containers use a single pre-assigned
    network for all communication. This makes it suitable for OpenStack
    environments that only support a single network (i.e., HP Cloud). 
    """
    def __init__(self, controller):
        self.name = "OpenStack launcher"
        self.docker_registry = None
        self.docker_user = None
        self.heat_server = None
        self.openstack_key = None

        self.system = System()
        self.installer = Installer()
        self.controller = controller
        self._init_open_stack()
        self._init_app_db()

    def support_proxy(self):
        """
        The OpenStack backend supports proxy mode by assigning all the
        machines a floating IP.
        """
        return True

    def _init_app_db(self):
        self.mongo = MongoClient(os.environ['MONGODB'], 27017, connectTimeoutMS=6000)
        self.apps = self.mongo['cloud']['openstack']

    def _init_open_stack(self):
        conf = ferry.install.read_ferry_config()

        # First we need to know the deployment system
        # we are using. 
        self.data_device = conf['system']['network']
        provider = conf['system']['provider']
            
        # Now get some basic OpenStack information
        params = conf[provider]['params']
        self.default_dc = params['dc']
        self.default_zone = params['zone']

        # Some OpenStack login credentials. 
        if self._check_openstack_credentials():
            self.openstack_user = os.environ['OS_USERNAME']
            self.openstack_pass = os.environ['OS_PASSWORD']
            self.tenant_id = os.environ['OS_TENANT_ID']
            self.tenant_name = os.environ['OS_TENANT_NAME']
        else:
            logging.error("Missing OpenStack credentials")
            raise ValueError("Missing OpenStack credentials")

        # Some information regarding OpenStack
        # networking. Necessary for 
        servers = conf[provider][self.default_dc]
        self.manage_network = servers['network']
        self.external_network = servers['extnet']
        
        # OpenStack API endpoints. 
        self.region = servers['region']
        self.keystone_server = servers['keystone']
        self.nova_server = servers['nova']
        self.neutron_server = servers['neutron']

        # Check if the user has provided a Heat
        # server. Not all OpenStack clusters provide
        # Heat. If not, we'll need to start a local instance. 
        self.heatuuid = None
        if 'HEAT_URL' in os.environ:
            self.heat_server = os.environ['HEAT_URL']
        elif 'heat' in servers:
            self.heat_server = servers['heat']
        else:
            self.heat_server = self._check_and_start_heat(self.tenant_id)
        logging.warning("using heat server " + str(self.heat_server))

        # This gives us information about the image to use
        # for the supplied provider. 
        deploy = conf[provider]['deploy']
        self.default_image = deploy['image']
        self.default_personality = deploy['personality']
        self.default_user = deploy['default-user']
        self.ssh_key = deploy['ssh']
        self.ssh_user = deploy['ssh-user']

        # Make sure that the ssh key is actually present. 
        keypath = self._get_host_key()
        if not os.path.exists(keypath):
            logging.error("could not find ssh key (%s)" % self.ssh_key)
            raise ValueError("Missing ssh keys")

        # Initialize the OpenStack clients and also
        # download some networking information (subnet ID, 
        # cidr, gateway, etc.)
        self._init_openstack_clients()
        self._collect_subnet_info()

    def _get_host_key(self):
        """
        Get the location of the private ssh key. 
        """
        p = self.ssh_key.split("/")
        if len(p) == 1:
            return "/ferry/keys/" + self.ssh_key + ".pem"
        else:
            return self.ssh_key + ".pem"

    def _check_and_start_heat(self, tenant_id):
        """
        Check and start the Ferry Heat image.
        """

        # Check if the image is downloaded locally. 
        # If not, it will automatically pull it. 
        logging.info("Check for Heat image")
        self.installer._check_and_pull_image("ferry/heatserver")

        # Check if the Heat log directory exists yet. If not
        # go ahead and create it. 
        heatlogs = ferry.install.DOCKER_DIR + "/heatlog"
        try:
            if not os.path.isdir(heatlogs):
                os.makedirs(heatlogs)
                self.installer._change_permission(heatlogs)
        except OSError as e:
            logging.error(e.strerror)
            sys.exit(1)

        # Start the Heat image and capture the IP address. We can
        # then hand over this IP to the rest of the configuration. 
        volumes = { heatlogs : "/var/log/heat" }
        heatplan = {'image':'ferry/heatserver',
                    'type':'ferry/heatserver', 
                    'keydir': {},
                    'keyname': None, 
                    'privatekey': None, 
                    'volumes':volumes,
                    'volume_user':ferry.install.DEFAULT_FERRY_OWNER, 
                    'ports':[],
                    'exposed':["8004","8000"], 
                    'internal':[],
                    'hostname':'heatserver',
                    'netenable':True, 
                    'default_cmd' : '',
                    'args': 'trust'
                     }
        self.heatuuid = 'fht-' + str(uuid.uuid4()).split('-')[0]
        self.heatbox = self.installer.fabric.alloc(self.heatuuid, self.heatuuid, [heatplan], "HEAT")[0]
        if not self.heatbox:
            logging.error("Could not start Heat server")
            sys.exit(1)
        else:
            return "http://%s:8004/v1/%s" % (str(self.heatbox.internal_ip),
                                             tenant_id)

    def _check_openstack_credentials(self):
        envs = ['OS_USERNAME', 'OS_PASSWORD', 
                'OS_TENANT_ID', 'OS_TENANT_NAME']
        for e in envs:
            if not e in os.environ:
                return False
        return True

    def _init_openstack_clients(self):
        # Instantiate the Heat client. 
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
            'auth_url' : self.keystone_server
        }
        self.heat = heat_client.Client(heat_api_version, 
                                       self.heat_server, 
                                       **kwargs)

        # Check to make sure that the Heat client can actually 
        # connect to the Heat server. This is because we may 
        # have just started the Heat server, so it can a while to refresh. 
        for i in range(0, 10):
            try:
                stacks = self.heat.stacks.list()
                for s in stacks:
                    logging.warning("found Heat stack: " + str(s))
                connected = True
                break
            except:
                time.sleep(12)
                connected = False
        if not connected:
            raise ValueError("Could not connect to Heat")
            
        # Instantiate the Neutron client.
        # There should be a better way of figuring out the API version. 
        neutron_api_version = "2.0"
        kwargs['endpoint_url'] = self.neutron_server
        self.neutron = neutron_client.Client(neutron_api_version, **kwargs)
                                             
        # Instantiate the Nova client. The Nova client is used
        # to stop/restart instances.
        nova_api_version = "1.1"
        kwargs = {
            'username' : self.openstack_user,
            'api_key' : self.openstack_pass,
            'tenant_id': self.tenant_id,
            'auth_url' : self.keystone_server,
            'service_type' : 'compute',
            'region_name' : self.region
        }
        self.nova = nova_client.Client(nova_api_version, **kwargs)

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

    def _create_security_group(self, group_name, ports, internal):
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
        # Additional ports for the security group. These
        # port values can be accessible from anywhere. 
        for p in ports:
            min_port = p[0]
            max_port = p[1]
            desc[group_name]["Properties"]["rules"].append({ "protocol" : "tcp",
                                                             "remote_ip_prefix": "0.0.0.0/0",
                                                             "port_range_min" : min_port,
                                                             "port_range_max" : max_port })
        # Additional ports for the security group. These
        # port values can only be accessed from within the same network. 
        for p in internal:
            min_port = p[0]
            max_port = p[1]
            desc[group_name]["Properties"]["rules"].append({ "protocol" : "tcp",
                                                             "remote_ip_prefix": self.subnet["cidr"],
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

    def _create_server_init(self):
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

    def _create_volume_attachment(self, iface, instance, volume_id):
        plan = { iface: { "Type": "OS::Cinder::VolumeAttachment",
                          "Properties": { "instance_uuid": { "Ref" : instance },
                                          "mountpoint": "/dev/vdc", 
                                          "volume_id": volume_id}}}
        desc = { "type" : "OS::Cinder::VolumeAttachment" }
        return plan, desc

    def _create_instance(self, name, image, size, manage_network, sec_group):
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
                          "name" : name,
                          "ports" : [],
                          "volumes" : [] }}

        # Create a port for the manage network.
        port_descs = []
        port_name = "ferry-port-%s" % name
        port_descs.append(self._create_port(port_name, manage_network, sec_group, ref=False))
        plan[name]["Properties"]["networks"].append({ "port" : { "Ref" : port_name },
                                                      "network" : manage_network}) 
        desc[name]["ports"].append(port_name)
        desc[port_name] = { "type" : "OS::Neutron::Port",
                            "role" : "manage" }
                                                      
        # Combine all the port descriptions. 
        for d in port_descs:
            plan = dict(plan.items() + d.items())

        # Now add the user script.
        user_data = self._create_server_init()
        plan[name]["Properties"]["user_data"] = user_data

        return plan, desc

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

    def _create_security_plan(self, cluster_uuid, ports, internal, ctype):
        """
        Update the security group. 
        """
        sec_group_name = "ferry-sec-%s-%s" % (cluster_uuid, ctype)
        plan = { "AWSTemplateFormatVersion" : "2010-09-09",
                 "Description" : "Ferry generated Heat plan",
                 "Resources" :  self._create_security_group(sec_group_name, ports, internal)}
        desc = { sec_group_name : { "type" : "OS::Neutron::SecurityGroup" }}
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
        
        try:
            # Try to create the application stack.
            resp = self.heat.stacks.create(stack_name=stack_name, template=heat_plan)
        except HTTPBadRequest as e:
            logging.error(e.strerror)
            return None
        except:
            # We could not create the stack. This probably
            # means that either the Heat server is down or the
            # OpenStack cluster is down.
            logging.error("could not create Heat stack")
            return None

        # Now wait for the stack to be in a completed state
        # before returning. That way we'll know if the stack creation
        # has failed or not. 
        if not self._wait_for_stack(resp["stack"]["id"]):
            logging.warning("Heat plan %s CREATE_FAILED" % resp["stack"]["id"])
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
                    time.sleep(4)
            except:
                logging.error("could not fetch stack status (%s)" % str(stack_id))

    def _collect_resources(self, stack_id):
        """
        Collect all the stack resources so that we can create
        additional plans and use IDs. 
        """
        try:
            resources = self.heat.resources.list(stack_id)
            descs = [r.to_dict() for r in resources]
            return descs
        except:
            return []

    def _collect_subnet_info(self):
        """
        Collect the data network subnet info (ID, CIDR, and gateway). 
        """
        subnets = self.neutron.list_subnets()
        for s in subnets['subnets']:
            if s['network_id'] == self.manage_network:
                self.subnet = { "id" : s['id'],
                                "cidr" : s['cidr'], 
                                "gateway" : s['gateway_ip'] }

    def _collect_network_info(self, stack_desc):
        """
        Collect all the networking information. 
        """

        # First get the floating IP information. 
        ip_map = {}
        floatingips = self.neutron.list_floatingips()
        for f in floatingips['floatingips']:
            if f['fixed_ip_address']:
                ip_map[f['fixed_ip_address']] = f['floating_ip_address']

        # Now fill in the various networking information, including
        # subnet, IP address, and floating address. We should also
        # probably collect MAC addresseses..
        ports = self.neutron.list_ports()
        for p in ports['ports']:
            if p['name'] != "" and p['name'] in stack_desc:
                port_desc = stack_desc[p['name']]
                port_desc["subnet"] = p['fixed_ips'][0]['subnet_id']
                port_desc["ip_address"] = p['fixed_ips'][0]['ip_address']

                # Not all ports are associated with a floating IP, so
                # we need to check first. 
                if port_desc["ip_address"] in ip_map:
                    port_desc["floating_ip"] = ip_map[port_desc["ip_address"]]
        return stack_desc

    def _collect_instance_info(self, stack_desc):
        """
        Collect all the instance information. 
        """

        servers = self.nova.servers.list()
        for s in servers:
            if s.name != "" and s.name in stack_desc:
                instance_desc = stack_desc[s.name]
                instance_desc["id"] = s.id
        return stack_desc

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

        logging.info("creating instances for %s" % cluster_uuid)
        stack_plan, stack_desc = self._create_instance_plan(cluster_uuid = cluster_uuid, 
                                                            num_instances = num_instances, 
                                                            image = self.default_image,
                                                            size = self.default_personality, 
                                                            sec_group_name = sec_group_desc.keys()[0], 
                                                            ctype = ctype)

        # See if we need to assign any floating IPs 
        # for this stack. We need the references to the neutron
        # port which is contained in the description. 
        if assign_floating_ip:
            logging.info("creating floating IPs for %s" % cluster_uuid)
            ifaces = []
            for k in stack_desc.keys():
                if stack_desc[k]["type"] == "OS::Neutron::Port" and stack_desc[k]["role"] == "manage":
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

        # Now find all the IP addresses of the various machines. 
        if stack_desc:
            stack_desc = self._collect_instance_info(stack_desc)
            return self._collect_network_info(stack_desc)
        else:
            return None

    def _get_private_ip(self, server, subnet_id, resources):
        """
        Get the IP address associated with the supplied server. 
        """
        for port_name in server["ports"]:
            port_desc = resources[port_name]
            if port_desc["subnet"] == subnet_id:
                return port_desc["ip_address"]

    def _get_public_ip(self, server, resources):
        """
        Get the IP address associated with the supplied server. 
        """
        for port_name in server["ports"]:
            port_desc = resources[port_name]
            if "floating_ip" in port_desc:
                return port_desc["floating_ip"]

    def _get_servers(self, resources):
        servers = []
        for r in resources.values(): 
            if type(r) is dict and r["type"] == "OS::Nova::Server":
                servers.append(r)
        return servers

    def _get_net_info(self, server_info, subnet, resources):
        """
        Look up the IP address, gateway, and subnet range. 
        """
        cidr = subnet["cidr"].split("/")[1]
        ip = self._get_private_ip(server_info, subnet["id"], resources)

        # We want to use the host NIC, so modify LXC to use phys networking, and
        # then start the docker containers on the server. 
        lxc_opts = ["lxc.network.type = phys",
                    "lxc.network.ipv4 = %s/%s" % (ip, cidr),
                    "lxc.network.ipv4.gateway = %s" % subnet["gateway"],
                    "lxc.network.link = %s" % self.data_device,
                    "lxc.network.name = eth0", 
                    "lxc.network.flags = up"]
        return lxc_opts, ip

    def _update_app_db(self, cluster_uuid, service_uuid, heat_plan):
        # Make a copy of the plan before inserting into
        # mongo, otherwise the "_id" field will be added
        # silently. 
        heat_plan["_cluster_uuid"] = cluster_uuid
        heat_plan["_service_uuid"] = service_uuid
        self.apps.insert(copy.deepcopy(heat_plan))

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
                # Otherwise, the backend should also get floating IPs
                # so that the controller can access it. 
                floating_ip = True
            else:
                # If the controller is acting as a proxy, then it has
                # direct access to the VMs, so the backend shouldn't
                # get any floating IPs. 
                floating_ip = False

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

        # Tell OpenStack to allocate the cluster. 
        resources = self._create_app_stack(cluster_uuid = cluster_uuid, 
                                           num_instances = len(container_info), 
                                           security_group_ports = sec_group_ports,
                                           internal_ports = internal_ports, 
                                           assign_floating_ip = floating_ip,
                                           ctype = ctype)
        
        # Now we need to ask the cluster to start the 
        # Docker containers.
        containers = []
        mounts = {}

        if resources:
            # Store the resources cluster ID. 
            self._update_app_db(cluster_uuid, service_uuid, resources)

            servers = self._get_servers(resources)
            for i in range(0, len(container_info)):
                # Fetch a server to run the Docker commands. 
                server = servers[i]

                # Get the LXC networking options
                lxc_opts, private_ip = self._get_net_info(server, self.subnet, resources)

                # Now get an addressable IP address. If we're acting as a proxy within
                # the same cluster, we can just use the private address. Otherwise
                # we'll need to route via the public IP address. 
                if proxy:
                    server_ip = private_ip
                else:
                    server_ip = self._get_public_ip(server, resources)

                # Verify that the user_data processes all started properly
                # and that the docker daemon is actually running. If it is
                # not running, try re-executing. 
                if not self.controller._verify_ferry_server(server_ip):
                    self.controller._execute_server_init(server_ip)

                # Copy over the public keys, but also verify that it does
                # get copied over properly. 
                self.controller._copy_public_keys(container_info[i], server_ip)
                if self.controller._verify_public_keys(server_ip):
                    container, cmounts = self.controller.execute_docker_containers(container_info[i], lxc_opts, private_ip, server_ip)
                
                    if container:
                        mounts = dict(mounts.items() + cmounts.items())
                        containers.append(container)
                else:
                    logging.error("could not copy over ssh key!")
                    return None

            # Check if we need to set the file permissions
            # for the mounted volumes. 
            for c, i in mounts.items():
                for _, v in i['vols']:
                    self.controller.cmd([c], 'chown -R %s %s' % (i['user'], v))
            return containers
        else:
            # OpenStack failed to launch the application stack.
            # This can be caused by improper OpenStack credentials
            # or if the OpenStack cluster is under heavy load (i.e.,
            # requests are getting timed out). 
            return None

    def _delete_stack(self, cluster_uuid, service_uuid):
        # Find the relevant stack information. 
        ips = []
        stacks = self.apps.find( { "_cluster_uuid" : cluster_uuid,
                                   "_service_uuid" : service_uuid } )

        logging.warning("Deleting cluster %s" % str(cluster_uuid))
        for stack in stacks:
            for s in stack.values():
                if type(s) is dict and s["type"] == "OS::Heat::Stack":
                    stack_id = s["id"]

                    # To delete the stack properly, we first need to disassociate
                    # the floating IPs. 
                    resources = self._collect_resources(stack_id)
                    for r in resources:
                        if r["resource_type"] == "OS::Neutron::FloatingIP":
                            self.neutron.update_floatingip(r["physical_resource_id"], {'floatingip': {'port_id': None}})

                    # Now try to delete the stack. Wrap this in a try-block so that
                    # we don't completely fail even if the stack doesn't exist. 
                    try:
                        logging.warning("Deleting stack %s" % str(stack_id))
                        self.heat.stacks.delete(stack_id)
                    except HTTPNotFound as e:
                        logging.warning(e)

        self.apps.remove( { "_cluster_uuid" : cluster_uuid,
                            "_service_uuid" : service_uuid } )

    def _stop_stack(self, cluster_uuid, service_uuid):
        stacks = self.apps.find( { "_cluster_uuid" : cluster_uuid,
                                   "_service_uuid" : service_uuid } )
        for stack in stacks:
            servers = self._get_servers(stack)
            for s in servers:
                self.nova.servers.stop(s["id"])

    def _restart_stack(self, cluster_uuid, service_uuid):
        ips = []
        stacks = self.apps.find( { "_cluster_uuid" : cluster_uuid,
                                   "_service_uuid" : service_uuid } )
        for stack in stacks:
            # Find the set of servers and restart them
            # one by one. It would be nicer if Heat had a way to
            # restart them all at once, but not sure how to do that...
            servers = self._get_servers(stack)
            for s in servers:
                self.nova.servers.start(s["id"])
                ips.append(self._get_public_ip(s, stack))

            # Wait for the servers to actually be in the 
            # "running" status before returning. 
            for s in servers:
                while(True):
                    found = self.nova.servers.list(search_opts = { "name" : s["name"] })
                    for f in found["servers"]:
                        if f["status"] == "ACTIVE":
                            break
                    time.sleep(4)
        return ips

    def quit(self):
        """
        Check if the Heat server is running, and if so
        go ahead and stop it. 
        """
        if self.heatuuid:
            self.installer.fabric.stop(self.heatuuid, self.heatuuid, [self.heatbox])
