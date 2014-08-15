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
from ferry.ip.client import DHCPClient
import ferry.install
import json
import logging
from subprocess import Popen, PIPE
import time
import yaml

class DockerFabric(object):
    def __init__(self, bootstrap=False):
        self.repo = 'public'
        self.docker_user = 'root'
        self.cli = DockerCLI(ferry.install.DOCKER_REGISTRY)
        self.bootstrap = bootstrap

        # Bootstrap mode means that the DHCP network
        # isn't available yet, so we can't use the network. 
        if not bootstrap:
            self.network = DHCPClient(self._get_gateway())

    def _get_gateway(self):
        """
        Get the gateway address in CIDR notation. This defines the
        range of IP addresses available to the containers. 
        """
        cmd = "LC_MESSAGES=C ifconfig drydock0 | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}'"
        gw = Popen(cmd, stdout=PIPE, shell=True).stdout.read().strip()

        cmd = "LC_MESSAGES=C ifconfig drydock0 | grep 'inet addr:' | cut -d: -f4 | awk '{ print $1}'"
        netmask = Popen(cmd, stdout=PIPE, shell=True).stdout.read().strip()
        mask = map(int, netmask.split("."))
        cidr = 1
        if mask[3] == 0:
            cidr = 8
        if mask[2] == 0:
            cidr *= 2

        return "%s/%d" % (gw, 32 - cidr)

    def _get_host(self):
        cmd = "ifconfig eth0 | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}'"
        return Popen(cmd, stdout=PIPE, shell=True).stdout.read().strip()

    def version(self):
        """
        Fetch the current docker version.
        """
        return self.cli.version()

    def get_fs_type(self):
        """
        Get the filesystem type associated with docker. 
        """
        return self.cli.get_fs_type()

    def restart(self, containers):
        """
        Restart the stopped containers.
        """
        new_containers = []
        for c in containers:
            container = self.cli.start(c.container,
                                       c.service_type,
                                       c.keydir,
                                       c.keyname,
                                       c.privatekey,
                                       c.volumes,
                                       c.args)
            container.default_user = self.docker_user
            new_containers.append(container)

        # We should wait for a second to let the ssh server start
        # on the containers (otherwise sometimes we get a connection refused)
        time.sleep(2)
        return new_containers

    def alloc(self, container_info):
        """
        Allocate several instances.
        """
        containers = []
        mounts = {}
        for c in container_info:
            # Get a new IP address for this container and construct
            # a default command. 
            gw = self._get_gateway().split("/")[0]

            # Check if we should use the manual LXC option. 
            if not 'netenable' in c:
                ip = self.network.assign_ip(c)
                lxc_opts = ["lxc.network.type = veth",
                            "lxc.network.ipv4 = %s/24" % ip, 
                            "lxc.network.ipv4.gateway = %s" % gw,
                            "lxc.network.link = drydock0",
                            "lxc.network.name = eth0",
                            "lxc.network.flags = up"]

                # Check if we need to forward any ports. 
                host_map = {}
                for p in c['ports']:
                    p = str(p)
                    s = p.split(":")
                    if len(s) > 1:
                        host = s[0]
                        dest = s[1]
                    else:
                        host = self.network.random_port()
                        dest = s[0]
                    host_map[dest] = [{'HostIp' : '0.0.0.0',
                                       'HostPort' : host}]
                    self.network.forward_rule('0.0.0.0/0', host, ip, dest)
                host_map_keys = host_map.keys()
            else:
                lxc_opts = None
                host_map = None
                host_map_keys = []

            # Start a container with a specific image, in daemon mode,
            # without TTY, and on a specific port
            c['default_cmd'] = "/service/sbin/startnode init"
            container = self.cli.run(service_type = c['type'], 
                                     image = c['image'], 
                                     volumes = c['volumes'],
                                     keydir = c['keydir'], 
                                     keyname = c['keyname'], 
                                     privatekey = c['privatekey'], 
                                     open_ports = host_map_keys,
                                     host_map = host_map, 
                                     expose_group = c['exposed'], 
                                     hostname = c['hostname'],
                                     default_cmd = c['default_cmd'],
                                     args= c['args'],
                                     lxc_opts = lxc_opts)
            if container:
                container.default_user = self.docker_user
                containers.append(container)
                if not 'netenable' in c:
                    container.internal_ip = ip
                    self.network.set_owner(ip, container.container)

                if 'name' in c:
                    container.name = c['name']

                if 'volume_user' in c:
                    mounts[container] = {'user':c['volume_user'],
                                         'vols':c['volumes'].items()}

                # We should wait for a second to let the ssh server start
                # on the containers (otherwise sometimes we get a connection refused)
                time.sleep(2)

        # Check if we need to set the file permissions
        # for the mounted volumes. 
        for c, i in mounts.items():
            for _, v in i['vols']:
                self.cmd([c], 'chown -R %s %s' % (i['user'], v))

        return containers

    def stop(self, containers):
        """
        Forceably stop the running containers
        """
        for c in containers:
            self.cli.stop(c['container'])

    def remove(self, containers):
        """
        Remove the running instances
        """
        for c in containers:
            for p in c.ports.keys():
                self.network.delete_rule(c.internal_ip, p)
            self.network.free_ip(c.internal_ip)
            self.cli.remove(c.container)

    def snapshot(self, containers, cluster_uuid, num_snapshots):
        """
        Save/commit the running instances
        """
        snapshots = []
        for c in containers:
            snapshot_name = '%s-%s-%s:SNAPSHOT-%s' % (c.image, 
                                                      cluster_uuid,
                                                      c.host_name,
                                                      num_snapshots)
            snapshots.append( {'image' : snapshot_name,
                               'base' : c.image,
                               'type' : c.service_type, 
                               'name' : c.name, 
                               'args' : c.args,
                               'ports': c.ports} )
            self.cli.commit(c, snapshot_name)
        return snapshots

    def deploy(self, containers, registry=None):
        """
        Upload these containers to the specified registry.
        """
        deployed = []
        for c in containers:
            image_name = '%s-%s:DEPLOYED' % (c.image, 
                                             c.host_name)
            deployed.append( {'image' : image_name,
                              'base' : c.image,
                              'type' : c.service_type, 
                              'name' : c.name, 
                              'args' : c.args,
                              'ports': c.ports} )
            if not registry:
                self.cli.commit(c, image_name)
            else:
                self.cli.push(c.image, registry)
        return deployed

    def push(self, image, registry=None):
        """
        Push an image to a remote registry.
        """        
        return self.cli.push(image, registry)

    def pull(self, image):
        """
        Pull a remote image to the local registry. 
        """        
        return self.cli.pull(image)

    def halt(self, containers):
        """
        Safe stop the containers. 
        """
        cmd = '/service/sbin/startnode halt'
        for c in containers:
            self.cmd_raw(c.privatekey, c.internal_ip, cmd)

    def copy(self, containers, from_dir, to_dir):
        """
        Copy over the contents to each container
        """
        for c in containers:
            self.copy_raw(c.privatekey, c.internal_ip, from_dir, to_dir)

    def copy_raw(self, key, ip, from_dir, to_dir):
        opts = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
        scp = 'scp ' + opts + ' -i ' + key + ' -r ' + from_dir + ' ' + self.docker_user + '@' + ip + ':' + to_dir
        logging.warning(scp)
        output = Popen(scp, stdout=PIPE, shell=True).stdout.read()

    def cmd(self, containers, cmd):
        """
        Run a command on all the containers and collect the output. 
        """
        all_output = {}
        for c in containers:
            output = self.cmd_raw(c.privatekey, c.internal_ip, cmd)
            all_output[c.host_name] = output.strip()
        return all_output

    def cmd_raw(self, key, ip, cmd):
        ip = self.docker_user + '@' + ip
        ssh = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ' + key + ' -t -t ' + ip + ' \'%s\'' % cmd
        logging.warning(ssh)
        output = Popen(ssh, stdout=PIPE, shell=True).stdout.read()
        return output

    def login(self):
        """
        Login to a remote registry. Use the login credentials
        found in the user's home directory. 
        """
        with open(ferry.install.DEFAULT_DOCKER_LOGIN, 'r') as f:
            args = yaml.load(f)
            args = args['docker']
            if all(k in args for k in ("user","password","email")):
                if 'server' in args:
                    server = args['server']
                else:
                    server = ''
                return self.cli.login(user = args['user'], 
                                      password = args['password'],
                                      email = args['email'],
                                      registry = server)
        logging.error("Could not open login credentials " + ferry.install.DEFAULT_LOGIN_KEY)
        return False

