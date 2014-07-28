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

class OpenStackFabric(object):

    def __init__(self, bootstrap=False):
        self.repo = 'public'
        self.heat = OpenStackLauncherHeat()

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

    def alloc(self, container_info):
        """
        Allocate several instances.
        """
        return []

    def stop(self, containers):
        """
        Forceably stop the running containers
        """
        logging.warning("stopping " + str(containers))

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
