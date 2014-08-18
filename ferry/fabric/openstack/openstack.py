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

import ferry.install
from ferry.docker.docker import DockerInstance, DockerCLI
import importlib
import inspect
import json
import logging
from subprocess import Popen, PIPE
import time
import yaml

class OpenStackFabric(object):

    def __init__(self, config=None, bootstrap=False):
        self.name = "openstack"
        self.repo = 'public'

        # Initialize the launcher and data networks. 
        self.config = config
        self._init_openstack(self.config)

        self.bootstrap = bootstrap
        self.cli = DockerCLI()
        self.cli.docker_user = self.launcher.ssh_user
        self.cli.key = self._get_host_key()
        self.inspector = OpenStackInspector(self)

    def _load_class(self, class_name):
        """
        Dynamically load a class
        """
        s = class_name.split("/")
        module_path = s[0]
        clazz_name = s[1]
        module = importlib.import_module(module_path)
        for n, o in inspect.getmembers(module):
            if inspect.isclass(o):
                if o.__module__ == module_path and o.__name__ == clazz_name:
                    return o(self, self.config)
        return None

    def _init_openstack(self, conf_file):
        with open(conf_file, 'r') as f:
            args = yaml.load(f)

            # The actual OpenStack launcher. This lets us customize 
            # launching into different OpenStack environments that each
            # may be slightly different (HP Cloud, Rackspace, etc). 
            launcher = args["system"]["mode"]
            self.launcher = self._load_class(launcher)

            # The name of the data network device (eth*). 
            self.data_network = args["system"]["network"]

            # Determine if we are using this fabric in proxy
            # mode. Proxy mode means that the client is external
            # to the network, but controller has direct access. 
            self.proxy = bool(args["system"]["proxy"])

    def _get_host_key(self):
        return "/ferry/keys/" + self.launcher.ssh_key + ".pem"

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

    def _copy_public_keys(self, container, server):
        """
        Copy over the public ssh key to the server so that we can start the
        container correctly. 
        """
        keydir = container['keydir'].values()[0]
        self.copy_raw(key = self.cli.key,
                      ip = server, 
                      from_dir = keydir + "/" + container["keyname"], 
                      to_dir = "/ferry/keys/")

    def execute_docker_containers(self, container, lxc_opts, private_ip, public_ip):
        host_map = None
        host_map_keys = []
        mounts = {}
        container['default_cmd'] = "/service/sbin/startnode init"
        container = self.cli.run(service_type = container['type'], 
                                 image = container['image'], 
                                 volumes = container['volumes'],
                                 keydir = { '/service/keys' : '/ferry/keys' }, 
                                 keyname = container['keyname'], 
                                 privatekey = container['privatekey'], 
                                 open_ports = host_map_keys,
                                 host_map = host_map, 
                                 expose_group = container['exposed'], 
                                 hostname = container['hostname'],
                                 default_cmd = container['default_cmd'],
                                 args= container['args'],
                                 lxc_opts = lxc_opts,
                                 server = public_ip,
                                 inspector = self.inspector)
        if container:
            # Fill in some information that the inspector doesn't, such
            # as both the internal and external IP. 
            container.external_ip = public_ip
            if self.proxy:
                # When the fabric controller is acting in proxy mode, 
                # it can contact the VMs via their private addresses. 
                container.internal_ip = private_ip
            else:
                # Otherwise, the controller can only interact with the
                # VMs via their public IP address. 
                container.internal_ip = public_ip
                logging.warning("USING PUBLIC FOR INTERNAL")

            container.default_user = self.cli.docker_user

            if 'name' in container:
                container.name = container['name']

            if 'volume_user' in container:
                mounts[container] = {'user':container['volume_user'],
                                     'vols':container['volumes'].items()}

            # We should wait for a second to let the ssh server start
            # on the containers (otherwise sometimes we get a connection refused)
            time.sleep(2)
            return container, mounts
        else:
            return None, None


    def alloc(self, cluster_uuid, container_info, ctype):
        """
        Allocate a new cluster. 
        """
        return self.launcher.alloc(cluster_uuid, container_info, ctype, self.proxy)

    def stop(self, containers):
        """
        Forceably stop the running containers
        """
        logging.warning("stopping " + str(containers))

    def halt(self, containers):
        """
        Safe stop the containers. 
        """
        logging.warning("halting " + str(containers))
        cmd = '/service/sbin/startnode halt'
        for c in containers:
            self.cmd_raw(c.internal_ip, cmd)

    def remove(self, containers):
        """
        Remove the running instances
        """
        logging.warning("removing " + str(containers))

    def copy(self, containers, from_dir, to_dir):
        """
        Copy over the contents to each container
        """
        for c in containers:
            self.copy_raw(c.privatekey, c.internal_ip, from_dir, to_dir)

    def copy_raw(self, key, ip, from_dir, to_dir):
        opts = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
        scp = 'scp ' + opts + ' -i ' + key + ' -r ' + from_dir + ' ' + self.cli.docker_user + '@' + ip + ':' + to_dir
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
        ip = self.cli.docker_user + '@' + ip
        ssh = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ' + key + ' -t -t ' + ip + ' \'%s\'' % cmd
        logging.warning(ssh)
        output = Popen(ssh, stdout=PIPE, shell=True).stdout.read()
        return output

class OpenStackInspector(object):
    def __init__(self, fabric):
        self.fabric = fabric

    def inspect(self, image, container, keydir=None, keyname=None, privatekey=None, volumes=None, hostname=None, open_ports=[], host_map=None, service_type=None, args=None, server=None):
        """
        Inspect a container and return information on how
        to connect to the container. 
        """        
        logging.warning("inspecting")
        instance = DockerInstance()

        # We don't keep track of the container ID in single-network
        # mode, so use this to store the VM image instead. 
        instance.container = self.fabric.launcher.default_image

        # The port mapping should be 1-to-1 since we're using
        # the physical networking mode. 
        instance.ports = {}
        for p in open_ports:
            instance.ports[p] = { 'HostIp' : '0.0.0.0',
                                  'HostPort' : p }

        # These values are just stored for convenience. 
        instance.image = image
        instance.host_name = hostname
        instance.service_type = service_type
        instance.args = args
        instance.volumes = volumes
        instance.keydir = keydir
        instance.keyname = keyname
        instance.privatekey = privatekey

        return instance        
    
