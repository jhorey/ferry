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

from ferry.docker.docker import DockerCLI
from ferry.fabric.openstack.heatlauncher import OpenStackLauncherHeat
import json
import logging
from subprocess import Popen, PIPE
import time
import yaml

class OpenStackFabric(object):

    def __init__(self, config=None, bootstrap=False):
        self.name = "openstack"
        self.repo = 'public'
        self.networks = {}
        self.apps = {}

        self.config = config
        self.heat = OpenStackLauncherHeat(self.config)

        self.cli = DockerCLI()
        self.cli.docker_user = self.heat.ssh_user
        self.cli.key = self._get_private_key(self.heat.ssh_key)

    def _get_private_key(self, public_key):
        return "/ferry/keys/" + public_key + ".pem"

    def version(self):
        """
        Fetch the current docker version.
        """
        return "0.1"

    def get_fs_type(self):
        """
        Get the filesystem type associated with docker. 
        """
        return "xfs"

    def restart(self, containers):
        """
        Restart the stopped containers.
        """
        return []

    def _fetch_network(self, cluster_uuid):
        """
        Check if this is a new cluster. If so, create
        a new application network. Otherwise, return
        the existing network. 
        """
        if not cluster_uuid in self.networks:
            self.networks[cluster_uuid] = self.heat.create_app_network(cluster_uuid)

        # Go through the network resources and find the network ID. 
        resources = self.networks[cluster_uuid]
        for r in resources.values(): 
            if r["type"] == "OS::Neutron::Net":
                return r["id"]

    def _fetch_subnet(self, cluster_uuid):
        """
        Fetch the subnet information. 
        """

        resources = self.networks[cluster_uuid]
        for r in resources.values(): 
            if r["type"] == "OS::Neutron::Subnet":
                return r

    def _execute_docker_containers(self, container, lxc_opts, server):
        host_map = None
        host_map_keys = []
        mounts = {}
        container['default_cmd'] = "/service/sbin/startnode init"
        container = self.cli.run(service_type = container['type'], 
                                 image = container['image'], 
                                 volumes = container['volumes'],
                                 keys = container['keys'], 
                                 open_ports = host_map_keys,
                                 host_map = host_map, 
                                 expose_group = container['exposed'], 
                                 hostname = container['hostname'],
                                 default_cmd = container['default_cmd'],
                                 args= container['args'],
                                 lxc_opts = lxc_opts,
                                 server = server)
        if container:
            container.default_user = self.docker_user
            containers.append(container)
            if not 'netenable' in c:
                container.internal_ip = ip
                self.network.set_owner(ip, container.container)

            if 'name' in c:
                container.name = container['name']

            if 'volume_user' in c:
                mounts[container] = {'user':container['volume_user'],
                                     'vols':container['volumes'].items()}

            # We should wait for a second to let the ssh server start
            # on the containers (otherwise sometimes we get a connection refused)
            time.sleep(2)
            return container, mounts

    def _get_net_ip(self, server, subnet_id, resources):
        """
        Get the IP address associated with the supplied server. 
        """
        for port_name in server["ports"]:
            port_desc = resources[port_name]
            if port_desc["subnet"] == subnet_id:
                return port_desc["ip_address"]

    def _get_subnet(self, network_info):
        """
        Get the subnet information. 
        """
        for r in network_info: 
            if r["type"] == "OS::Neutron::Subnet":
                return r

    def _get_servers(self, resources):
        servers = []
        for r in resources: 
            if r["type"] == "OS::Nova::Server":
                servers.append(r)
        return servers

    def _get_net_info(self, server_info, network_info, resources):
        """
        Look up the IP address, gateway, and subnet range. 
        """
        subnet = self._get_subnet(network_info)
        server = self._get_server(server_info)
        cidr = subnet["cidr"].split("/")[1]
        ip = self._get_net_ip(server, subnet["id"], resources)

        # We want to use the host NIC, so modify LXC to use phys networking, and
        # then start the docker containers on the server. 
        lxc_opts = ["lxc.network.type = phys",
                    "lxc.network.mtu = 1500", 
                    "lxc.network.ipv4 = %s/%s" % (ip, cidr),
                    "lxc.network.ipv4.gateway = %s" % subnet["gateway"],
                    "lxc.network.link = eth1",
                    "lxc.network.name = eth0"
                    "lxc.network.flags = up"]
        return lxc_opts

    def alloc(self, cluster_uuid, container_info, ctype):
        """
        Allocate several instances.
        """

        # Now take the cluster and create the security group
        # to expose all the right ports. 
        sec_group_ports = []
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
            # Since this is a backend type, we need to 
            # look at the internally exposed ports. 
            floating_ip = False
            
            # We need to create a range tuple, so check if 
            # the exposed port is a range.
            for p in container_info[0]['exposed']:
                s = p.split("-")
                if len(s) == 1:
                    sec_group_ports.append( (s[0], s[0]) )
                else:
                    sec_group_ports.append( (s[0], s[1]) )

        # Check if this is a new cluster. If so, we'll need to create
        # a new application network. 
        network = self._fetch_network(cluster_uuid)
        subnet = self._fetch_subnet(cluster_uuid)

        # Tell OpenStack to allocate the cluster. 
        resources = self.heat.create_app_stack(cluster_uuid = cluster_uuid, 
                                               num_instances = len(container_info), 
                                               network = (network, subnet), 
                                               security_group_ports = sec_group_ports,
                                               assign_floating_ip = floating_ip,
                                               ctype = ctype)
        self.apps[cluster_uuid] = resources

        # Now we need to ask the cluster to start the 
        # Docker containers.
        containers = []
        mounts = {}
        # servers = self._get_servers(resources)
        # for i in range(0, len(container_info)):
        #     # Fetch a server to run the Docker commands. 
        #     server = servers[i]

        #     # Get the LXC networking options
        #     lxc_opts = self._get_net_info(server, network, resources)
        #     container, cmounts = self._execute_docker_containers(container_info[i], lxc_opts, server)
        #     containers.append(container)
        #     mounts = dict(mounts.items() + cmounts.items())

        # # Check if we need to set the file permissions
        # # for the mounted volumes. 
        # for c, i in mounts.items():
        #     for _, v in i['vols']:
        #         self.cmd([c], 'chown -R %s %s' % (i['user'], v))

        return containers

    def stop(self, containers):
        """
        Forceably stop the running containers
        """
        logging.warning("stopping " + str(containers))

    def halt(self, containers):
        """
        Safe stop the containers. 
        """
        cmd = '/service/sbin/startnode halt'
        logging.warning("halting " + str(containers))

    def remove(self, containers):
        """
        Remove the running instances
        """
        logging.warning("removing " + str(containers))

    def copy(self, containers, from_dir, to_dir):
        """
        Copy over the contents to each container
        """
        logging.warning("copy " + str(containers))

    def copy_raw(self, ip, from_dir, to_dir):
        logging.warning("copy raw " + str(ip))

    def cmd(self, containers, cmd):
        """
        Run a command on all the containers and collect the output. 
        """
        return {}

    def cmd_raw(self, ip, cmd):
        logging.warning("cmd raw " + str(ip))
