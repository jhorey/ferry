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

import os
import json
import logging
from subprocess import Popen, PIPE

DOCKER_SOCK='unix:////var/run/ferry.sock'

""" Docker instance """
class DockerInstance(object):
    def __init__(self, json_data=None):
        if not json_data:
            self.container = ''
            self.service_type = None
            self.host_name = None
            self.external_ip = None
            self.internal_ip = None
            self.external_port = 0
            self.internal_port = 0
            self.image = ''
            self.volumes = None
            self.default_user = None
            self.name = None
            self.args = None
        else:
            self.container = json_data['container']
            self.service_type = json_data['type']
            self.host_name = json_data['hostname']
            self.external_ip = json_data['external_ip']
            self.internal_ip = json_data['internal_ip']
            self.external_port = json_data['external_port']
            self.internal_port = json_data['internal_port']
            self.image = json_data['image']
            self.volumes = json_data['volumes']
            self.default_user = json_data['user']
            self.name = json_data['name']
            self.args = json_data['args']

    """
    Return in JSON format. 
    """
    def json(self):
        json_reply = { '_type' : 'docker',
                       'external_ip' : self.external_ip,
                       'internal_ip' : self.internal_ip,
                       'external_port' : self.external_port,
                       'internal_port' : self.internal_port,
                       'hostname' : self.host_name,
                       'container' : self.container,
                       'image' : self.image,
                       'type': self.service_type, 
                       'volumes' : self.volumes,
                       'user' : self.default_user,
                       'name' : self.name,
                       'args' : self.args }
        return json_reply


""" Alternative API for Docker that uses external commands """
class DockerCLI(object):
    def __init__(self):
        self.docker = 'docker-ferry -H=' + DOCKER_SOCK
        self.version_cmd = 'version'
        self.start_cmd = 'start'
        self.run_cmd = 'run -privileged'
        self.build_cmd = 'build -privileged'
        self.inspect_cmd = 'inspect'
        self.images_cmd = 'images'
        self.commit_cmd = 'commit'
        self.push_cmd = 'push'
        self.stop_cmd = 'stop'
        self.tag_cmd = 'tag'
        self.rm_cmd = 'rm'
        self.ps_cmd = 'ps'
        self.info_cmd = 'info'
        self.daemon = '-d'
        self.interactive = '-i'
        self.tty = '-t'
        self.port_flag = ' -p'
        self.expose_flag = ' -expose'
        self.volume_flag = ' -v'
        self.net_flag = ' -nb'
        self.host_flag = ' -h'
        self.fs_flag = ' -s'

    """
    Get the backend driver docker is using. 
    """
    def get_fs_type(self):
        cmd = self.docker + ' ' + self.info_cmd + ' | grep Driver | awk \'{print $2}\''
        logging.warning(cmd)

        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
        return output.strip()
        
    """
    Fetch the current docker version.
    """
    def version(self):
        cmd = self.docker + ' ' + self.version_cmd + ' | grep Client | awk \'{print $3}\''
        logging.warning(cmd)

        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
        return output.strip()
        
    """
    List all the containers. 
    """
    def list(self):
        cmd = self.docker + ' ' + self.ps_cmd + ' -q' 
        logging.warning(cmd)

        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
        output = output.strip()

        # There is a container ID for each line
        return output.split()

    """
    List all images that match the image name
    """
    def images(self, image_name=None):
        if not image_name:
            cmd = self.docker + ' ' + self.images_cmd + ' | awk \'{print $1}\''
            output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
        else:
            cmd = self.docker + ' ' + self.images_cmd + ' | awk \'{print $1}\'' + ' | grep ' + image_name
            output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()

        logging.warning(cmd)
        return output.strip()
    """
    Build a new image from a Dockerfile
    """
    def build(self, image, docker_file=None):
        path = '.'
        if docker_file != None:
            path = docker_file

        cmd = self.docker + ' ' + self.build_cmd + ' -t %s %s' % (image, path)
        logging.warning(cmd)
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()

    def _get_default_run(self, container):
        cmd = self.docker + ' ' + self.inspect_cmd + ' ' + container.container
        logging.warning(cmd)

        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
        data = json.loads(output.strip())
        
        cmd = data[0]['Config']['Cmd']
        return json.dumps( {'Cmd' : cmd} )

    """
    Push an image to a remote registry.
    """
    def push(self, container, registry):
        raw_image_name = container.image.split("/")[1]
        new_image = "%s/%s" % (registry, raw_image_name)

        tag = self.docker + ' ' + self.tag_cmd + ' ' + container.image + ' ' + new_image
        push = self.docker + ' ' + self.push_cmd + ' ' + new_image
        logging.warning(tag)
        logging.warning(push)
        
        Popen(tag, stdout=PIPE, shell=True).stdout.read()
        Popen(push, stdout=PIPE, shell=True).stdout.read()

    """
    Commit a container
    """
    def commit(self, container, snapshot_name):
        default_run = self._get_default_run(container)
        run_cmd = "-run='%s'" % default_run

        # Construct a new container using the given snapshot name. 
        cmd = self.docker + ' ' + self.commit_cmd + ' ' + run_cmd + ' ' + container.container + ' ' + snapshot_name
        logging.warning(cmd)
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()

    """
    Stop a running container
    """
    def stop(self, container, phys_net=None, remove=False):
        cmd = self.docker + ' ' + self.stop_cmd + ' ' + container
        logging.warning(cmd)
        # Popen(cmd, stdout=PIPE, shell=True)
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()

    """
    Remove a container
    """
    def remove(self, container, phys_net=None, remove=False):
        cmd = self.docker + ' ' + self.rm_cmd + ' ' + container
        logging.warning(cmd)
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()

    """
    Start a stopped container. 
    """
    def start(self, container, service_type, args):
        cmd = self.docker + ' ' + self.start_cmd + ' ' + container
        logging.warning(cmd)
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()

        # Now parse the output to get the IP and port
        container = output.strip()
        return self.inspect(container = container, 
                            service_type = service_type, 
                            args = args)

    """
    Run a command in a virtualized container
    The Docker allocator will ignore subnet, volumes, instance_name, and key
    information since everything runs locally. 
    """
    def run(self, service_type, image, volumes, phys_net, security_group, expose_group=None, hostname=None, args=None):
        flags = self.daemon 
        if phys_net != None:
            flags += self.net_flag
            flags += ' %s ' % phys_net

        # Specify the hostname (this is optional)
        if hostname != None:
            flags += self.host_flag
            flags += ' %s ' % hostname

        # Add the port value if provided a valid port. 
        if security_group != None:
            for p in security_group:
                flags += self.port_flag
                flags += ' %s' % str(p)

        # Add the port value if provided a valid port. 
        if expose_group != None and len(expose_group) > 0:
            for p in expose_group:
                flags += self.expose_flag
                flags += ' %s' % str(p)

        # Add all the bind mounts
        if volumes != None:
            for v in volumes.keys():
                flags += self.volume_flag
                flags += ' %s:%s' % (v, volumes[v])

        # Now construct the final docker command. 
        cmd = self.docker + ' ' + self.run_cmd + ' ' + flags + ' ' + image
        logging.warning(cmd)
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()

        # Now parse the output to get the IP and port
        container = output.strip()
        return self.inspect(container, volumes, hostname, service_type, args)

    """
    Inspect a container and return information on how
    to connect to the container. 
    """
    def inspect(self, container, volumes=None, hostname=None, service_type=None, args=None):
        cmd = self.docker + ' ' + self.inspect_cmd + ' ' + container
        logging.warning(cmd)

        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()

        data = json.loads(output.strip())
        instance = DockerInstance()

        if type(data) is list:
            data = data[0]

        instance.image = data['Config']['Image']
        instance.container = data['ID']
        instance.internal_ip = data['NetworkSettings']['IPAddress']

        if hostname:
            instance.host_name = hostname
        else:
            # Need to inspect to get the hostname.
            instance.host_name = data['Config']['Hostname']

        instance.service_type = service_type
        instance.args = args

        port_mapping = data['NetworkSettings']['PortMapping']
        if port_mapping:
            for origin in port_mapping:
                instance.internal_port = origin
                instance.external_port = port_mapping[origin]

        # Add any data volume information. 
        if volumes:
            instance.volumes = volumes
        else:
            # Need to inspect to get the volume bindings. 
            instance.volumes = data['Volumes']
        return instance
