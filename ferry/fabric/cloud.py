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
from ferry.fabric.com import robust_com
import importlib
import inspect
import json
import logging
import re
from subprocess import Popen, PIPE
import time
import yaml

class CloudFabric(object):

    def __init__(self, bootstrap=False):
        self.name = "cloud"
        self.repo = 'public'

        self._init_cloudfabric()
        self.bootstrap = bootstrap
        self.cli = DockerCLI()
        self.cli.key = self.launcher._get_host_key()
        self.docker_user = self.cli.docker_user
        self.inspector = CloudInspector(self)

        # The system returns information regarding 
        # the instance types. 
        self.system = self.launcher.system

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
                    return o(self)
        return None

    def _init_cloudfabric(self):
        conf = ferry.install.read_ferry_config()

        # The actual cloud launcher. This lets us customize 
        # launching into different cloud environments that each
        # may be slightly different (HP Cloud, Rackspace, etc). 
        launcher = conf["system"]["mode"]
        self.launcher = self._load_class(launcher)

        # Determine if we are using this fabric in proxy
        # mode. Proxy mode means that the client is external
        # to the network, but controller has direct access. 
        self.proxy = bool(conf["system"]["proxy"])

        # Check if the launcher supports proxy mode. 
        if self.proxy and not self.launcher.support_proxy():
            logging.error("%s does not support proxy mode" % self.launcher.name)

    def get_data_dir(self):
        return "/ferry/data"

    def installed_images(self):
        """
        List all the installed Docker images. We should really
        contact the index server responsible for serving out
        images and ask it. 
        """
        images = []
        image_string = self.cli.images()
        for image in image_string.split():
            image_name = image.strip()
            if image_name != "REPOSITORY" and image_name != "<none>":
                images.append(image_name)
        return images

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

    def quit(self):
        """
        Quit the cloud fabric. 
        """
        logging.info("quitting cloud fabric")
        self.launcher.quit()

    def restart(self, cluster_uuid, service_uuid, containers):
        """
        Restart the stopped containers.
        """
        # First need to restart all the virtual machines.
        logging.warning("restarting virtual machines...")
        addrs = self.launcher._restart_stack(cluster_uuid, service_uuid)
        
        # Then need to restart Ferry on all the hosts. 
        logging.warning("restarting ferry...")
        cmd = "source /etc/profile && ferry server -n"
        for ip in addrs:
            output, err, _ = self.cmd_raw(self.cli.key, ip, cmd, self.docker_user)

        # Finally, restart the stopped containers. 
        logging.warning("restarting containers...")
        cmd = "cat /ferry/containers/container.pid && rm /ferry/containers/container.pid"
        for c in containers:
            # Before restarting the containers, we need to learn their
            # container IDs. It should be stored on a cidfile. 
            output, err, _ = self.cmd_raw(self.cli.key, c.external_ip, cmd, self.launcher.ssh_user)
            c.container = output.strip()
            self.cli.start(image = c.image,
                           container = c.container, 
                           service_type = c.service_type,
                           keydir = c.keydir,
                           keyname = c.keyname,
                           privatekey = c.privatekey,
                           volumes = c.volumes,
                           args = c.args,
                           server = c.external_ip, 
                           user = self.launcher.ssh_user,
                           inspector = self.inspector,
                           background = True)
        return containers

    def _copy_public_keys(self, container, server):
        """
        Copy over the public ssh key to the server so that we can start the
        container correctly. 
        """

        keydir = container['keydir'].values()[0]
        self.copy_raw(key = self.cli.key,
                      ip = server, 
                      from_dir = keydir + "/" + container["keyname"], 
                      to_dir = "/ferry/keys/",
                      user = self.launcher.ssh_user)

    def _verify_public_keys(self, server):
        """
        Verify that the public key has been copied over correctly. 
        """
        out, _, _ = self.cmd_raw(key = self.cli.key, 
                                 ip = server, 
                                 cmd = "ls /ferry/keys",
                                 user = self.launcher.ssh_user)
        if out and out.strip() == "":
            return False
        elif out:
            logging.warning("found ssh key: " + out.strip())
            return True
        else:
            return False

    def _verify_ferry_server(self, server):
        """
        Verify that the docker daemon is actually running on the server. 
        """

        # Try a couple times before giving up. 
        for i in range(0, 2):
            out, err, success = self.cmd_raw(key = self.cli.key, 
                                             ip = server, 
                                             cmd = "if [ -f /var/run/ferry.pid ]; then echo \"launched\"; fi",
                                             user = self.launcher.ssh_user)
            if success and out and out.strip() != "":
                logging.warning("docker daemon " + out.strip())
                return True
            elif not success:
                return False
            else:
                time.sleep(6)
        return False

    def _execute_server_init(self, server):
        """
        Restart the Ferry docker daemon. 
        """
        out, err, _ = self.cmd_raw(key = self.cli.key, 
                                   ip = server, 
                                   cmd = "ferry server -n && sleep 3",
                                   user = self.launcher.ssh_user)
        logging.warning("restart ferry out: " + out)
        logging.warning("restart ferry err: " + err)
        
    def execute_docker_containers(self, cinfo, lxc_opts, private_ip, server_ip, background=True, simulate=False):
        """
        Run the Docker container and use the cloud inspector to get information
        about the container/VM.
        """

        host_map = None
        host_map_keys = []
        mounts = {}        

        if not 'default_cmd' in cinfo:
            cinfo['default_cmd'] = "/service/sbin/startnode init"
        container = self.cli.run(service_type = cinfo['type'], 
                                 image = cinfo['image'], 
                                 volumes = cinfo['volumes'],
                                 keydir = { '/service/keys' : '/ferry/keys' }, 
                                 keyname = cinfo['keyname'], 
                                 privatekey = cinfo['privatekey'], 
                                 open_ports = host_map_keys,
                                 host_map = host_map, 
                                 expose_group = cinfo['exposed'], 
                                 hostname = cinfo['hostname'],
                                 default_cmd = cinfo['default_cmd'],
                                 args= cinfo['args'],
                                 lxc_opts = lxc_opts,
                                 server = server_ip,
                                 user = self.launcher.ssh_user, 
                                 inspector = self.inspector,
                                 background = background,
                                 simulate= simulate)
        if container:
            container.manage_ip = server_ip
            container.internal_ip = private_ip
            if self.proxy:
                # Otherwise, the controller can only interact with the
                # VMs via their public IP address. 
                container.external_ip = server_ip
            else:
                # When the fabric controller is acting in proxy mode, 
                # it can contact the VMs via their private addresses. 
                container.external_ip = private_ip

            container.vm = self.launcher.default_personality
            container.default_user = self.cli.docker_user

            if 'name' in cinfo:
                container.name = cinfo['name']

            if 'volume_user' in cinfo:
                mounts[container] = {'user':cinfo['volume_user'],
                                     'vols':cinfo['volumes'].items()}

            # We should wait for a second to let the ssh server start
            # on the containers (otherwise sometimes we get a connection refused)
            time.sleep(3)

            return container, mounts
        else:
            return None, None

    def alloc(self, cluster_uuid, service_uuid, container_info, ctype):
        """
        Allocate a new service cluster. 
        """
        containers = self.launcher.alloc(cluster_uuid, service_uuid, container_info, ctype, self.proxy)
        
        if not containers:
            # The underlying cloud infrastructure could not allocate
            # the service cluster. Sometimes it's just a temporary glitch, so
            # get rid of the attempt and try some more. 
            logging.error("Failed to allocate service cluster. Trying again.")
            self.launcher._delete_stack(cluster_uuid, service_uuid)
            return self.launcher.alloc(cluster_uuid, service_uuid, container_info, ctype, self.proxy)
        else:
            return containers

    def stop(self, cluster_uuid, service_uuid, containers):
        """
        Stop the running containers
        """
        self.remove(cluster_uuid, service_uuid, containers)

    def halt(self, cluster_uuid, service_uuid, containers):
        """
        Safe stop the containers. 
        """

        # Stop the containers in the VMs. Stopping the container
        # should jump us back out to the host. Afterwards, quit
        # ferry so that we can restart later. 
        halt = '/service/sbin/startnode halt'
        ferry = 'ferry quit'
        for c in containers:
            self.cmd_raw(c.privatekey, c.external_ip, halt, c.default_user)
            self.cmd_raw(self.cli.key, c.manage_ip, ferry, self.launcher.ssh_user)

        # Now go ahead and stop the VMs. 
        self.launcher._stop_stack(cluster_uuid, service_uuid)

    def remove(self, cluster_uuid, service_uuid, containers):
        """
        Remove the running instances
        """
        self.launcher._delete_stack(cluster_uuid, service_uuid)

    def copy(self, containers, from_dir, to_dir):
        """
        Copy over the contents to each container
        """
        for c in containers:
            self.copy_raw(c.privatekey, c.external_ip, from_dir, to_dir, c.default_user)

    def copy_raw(self, key, ip, from_dir, to_dir, user):
        opts = '-o ConnectTimeout=20 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
        scp = 'scp ' + opts + ' -i ' + key + ' -r ' + from_dir + ' ' + user + '@' + ip + ':' + to_dir
        logging.warning(scp)
        robust_com(scp)
        
    def cmd(self, containers, cmd):
        """
        Run a command on all the containers and collect the output. 
        """
        all_output = {}
        for c in containers:
            output, _, _ = self.cmd_raw(c.privatekey, c.external_ip, cmd, c.default_user)
            if output.strip() != "":
                all_output[c.host_name] = output.strip()
        return all_output

    def cmd_raw(self, key, ip, cmd, user):
        ip = user + '@' + ip
        ssh = 'LC_ALL=C && ssh -o ConnectTimeout=20 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ' + key + ' -t -t ' + ip + ' \'%s\'' % cmd
        logging.warning(ssh)
        return robust_com(ssh)

class CloudInspector(object):
    def __init__(self, fabric):
        self.fabric = fabric

    def inspect(self, image, container, keydir=None, keyname=None, privatekey=None, volumes=None, hostname=None, open_ports=[], host_map=None, service_type=None, args=None, server=None):
        """
        Inspect a container and return information on how
        to connect to the container. 
        """        
        instance = DockerInstance()

        # We don't keep track of the container ID in single-network
        # mode, so use this to store the VM image instead. 
        # instance.container = self.fabric.launcher.default_image
        instance.container = container

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
    
