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
import logging
import time
from subprocess import Popen, PIPE
from ferry.docker.docker import DockerCLI

"""
Allocate local docker instances
"""
class DockerFabric(object):
    def __init__(self):
        self.repo = 'public'
        self.docker_user = 'root'
        self.cli = DockerCLI()

    """
    Read the location of the directory containing the keys
    used to communicate with the containers. 
    """
    def _read_key_dir(self):
        f = open(ferry.install.DEFAULT_DOCKER_KEY, 'r')
        return f.read().strip()
 
    """
    Fetch the current docker version.
    """
    def version(self):
        return self.cli.version()

    """
    Get the filesystem type associated with docker. 
    """
    def get_fs_type(self):
        return self.cli.get_fs_type()

    """
    Restart the stopped containers.
    """
    def restart(self, container_info):
        container = self.cli.start(container_info['container'],
                                   container_info['type'],
                                   container_info['args'])
        container.default_user = self.docker_user
        return container

    """
    Allocate several instances.
    """
    def alloc(self, container_info):
        containers = []
        mounts = {}
        for c in container_info:
            # Start a container with a specific image, in daemon mode,
            # without TTY, and on a specific port
            container = self.cli.run(service_type = c['type'], 
                                     image = c['image'], 
                                     volumes = c['volumes'],
                                     phys_net = None, 
                                     security_group = c['ports'],
                                     expose_group = c['exposed'], 
                                     hostname = c['hostname'],
                                     args= c['args'])
            container.default_user = self.docker_user
            containers.append(container)

            # Not all containers have a unique name. 
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

    """
    Stop the running instances
    """
    def stop(self, containers):
        for c in containers:
            self.cli.stop(c.container)

    """
    Remove the running instances
    """
    def remove(self, containers):
        for c in containers:
            self.cli.remove(c.container)

    """
    Save/commit the running instances
    """
    def snapshot(self, containers, cluster_uuid, num_snapshots):
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
                               'args' : c.args} )
            self.cli.commit(c, snapshot_name)
        return snapshots

    """
    Upload these containers to the specified registry.
    """
    def deploy(self, containers, registry=None):
        deployed = []
        for c in containers:
            image_name = '%s-%s:DEPLOYED' % (c.image, 
                                             c.host_name)
            deployed.append( {'image' : image_name,
                              'base' : c.image,
                              'type' : c.service_type, 
                              'name' : c.name, 
                              'args' : c.args} )
            if not registry:
                self.cli.commit(c, image_name)
            else:
                self.cli.push(c, registry)
        return deployed

    """
    Copy over the contents to each container
    """
    def copy(self, containers, from_dir, to_dir):
        for c in containers:
            opts = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
            key = '-i ' + self._read_key_dir() + '/id_rsa'
            scp_cmd = 'scp ' + opts + ' ' + key + ' -r ' + from_dir + ' ' + self.docker_user + '@' + c.internal_ip + ':' + to_dir
            output = Popen(scp_cmd, stdout=PIPE, shell=True).stdout.read()

    """
    Run a command on all the containers and collect the output. 
    """
    def cmd(self, containers, cmd):
        all_output = {}
        key = self._read_key_dir() + '/id_rsa'
        for c in containers:
            ip = self.docker_user + '@' + c.internal_ip
            ssh = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ' + key + ' -t -t ' + ip + ' \'%s\'' % cmd
            logging.warning(ssh)
            output = Popen(ssh, stdout=PIPE, shell=True).stdout.read()
            all_output[c] = output.strip()

        return all_output
