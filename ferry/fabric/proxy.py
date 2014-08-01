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

class ProxyFabric(object):
    """
    Proxy fabric. Contacts a remote fabric that manages a particular
    cluster (OpenStack, AWS, etc.). 
    """

    def __init__(self, bootstrap=False):
        self.repo = 'public'
        self.docker_user = 'root'
        self.bootstrap = bootstrap
        self.remote = ""

    def version(self):
        """
        Fetch the current docker version.
        """
        return "0.0.1"

    def get_fs_type(self):
        """
        Get the filesystem type associated with docker. 
        """
        return "xfs"

    def restart(self, containers):
        """
        Restart the stopped containers.
        """
        logging.warning("restarting containers: " + str(containers))
        return []

    def alloc(self, container_info):
        """
        Allocate several instances.
        """
        logging.warning("allocating containers: " + str(container_info))
        return []

    def stop(self, containers):
        """
        Forceably stop the running containers
        """
        logging.warning("stopping containers: " + str(containers))

    def remove(self, containers):
        """
        Remove the running instances
        """
        logging.warning("removing containers: " + str(containers))

    def snapshot(self, containers, cluster_uuid, num_snapshots):
        """
        Save/commit the running instances
        """
        logging.warning("snapshot containers: " + str(containers))
        return []

    def deploy(self, containers, registry=None):
        """
        Upload these containers to the specified registry.
        """
        logging.warning("deploy containers: " + str(containers))
        return []

    def push(self, image, registry=None):
        """
        Push an image to a remote registry.
        """        
        return ""

    def pull(self, image):
        """
        Pull a remote image to the local registry. 
        """        
        return ""

    def halt(self, containers):
        """
        Safe stop the containers. 
        """
        logging.warning("halt containers: " + str(containers))

    def copy(self, containers, from_dir, to_dir):
        """
        Copy over the contents to each container
        """
        logging.warning("copy containers: " + str(containers))

    def copy_raw(self, ip, from_dir, to_dir):
        logging.warning("copy raw: " + str(ip))

    def cmd(self, containers, cmd):
        """
        Run a command on all the containers and collect the output. 
        """
        logging.warning("cmd containers: " + str(containers))
        return {}

    def cmd_raw(self, ip, cmd):
        logging.warning("cmd raw containers: " + str(ip))
        return {}

    def login(self):
        """
        Login to a remote registry. Use the login credentials
        found in the user's home directory. 
        """
        return False
