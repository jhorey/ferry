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

import sh
import os
import stat
import logging
from string import Template
from ferry.docker.fabric import DockerFabric

"""
Create Gluster configurations and apply them to a set of instances
"""
class GlusterInitializer(object):
    """
    Create a new initializer
    Param user The user login for the git repo
    """
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.MOUNT_VOLUME = '/gv0'
        self.MOUNT_ROOT = '/service'
        self.name = "GLUSTER"

        self.container_data_dir = GlusterConfig.data_directory 
        self.container_log_dir = GlusterConfig.log_directory 

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'gluster' + str(instance_id)

    def _execute_service(self, containers, entry_point, fabric, cmd):
        """
        Start the gluster service on the containers. We want to start/stop the
        slave nodes before the master, since the master assumes everything is
        waiting for it to start. 
        """
        all_output = {}
        master_ip = entry_point['gluster']
        for c in containers:
            if c.internal_ip != master_ip:
                output = fabric.cmd([c], '/service/sbin/startnode %s slave' % cmd)
                all_output = dict(all_output.items() + output.items())
        for c in containers:
            if c.internal_ip == master_ip:
                output = fabric.cmd([c], '/service/sbin/startnode %s master' % cmd)
                all_output = dict(all_output.items() + output.items())
        return all_output
    def start_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "start")
    def restart_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "restart")
    def stop_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "stop")

    """
    Generate a new Gluster configuration repo for a new
    Gluster filesystem instantiation. 
    """
    def generate_config_dir(self, uuid):
        return 'gluster_' + str(uuid)

    """
    Get the ports necessary for Gluster. 
    """
    def get_necessary_ports(self, num_instances):
        return []

    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        ports = []
        
        ports.append(GlusterConfig.MANAGEMENT_PORT)
        for i in range(0, num_instances):
            ports.append(GlusterConfig.BRICK_PORT + i)

        return ports

    """
    Get total number of instances.
    """
    def get_total_instances(self, num_instances, layers):
        instances = []

        for i in range(num_instances):
            instances.append('gluster')

        return instances

    """
    Generate a new configuration
    Param num Number of instances that need to be configured
    Param image Image type of the instances
    """
    def generate(self, num):
        return GlusterConfig(num)

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers):
        # The "entry point" is the way to contact the storage service.
        # For gluster this is the IP address of the "master" and the volume name. 
        entry_point = { 'type' : 'gluster' }

        # Create a new configuration directory, and place
        # into the template directory. 
        new_config_dir = "/tmp/" + self.generate_config_dir(config.uuid)

        try:
            sh.mkdir('-p', new_config_dir)
        except:
            logging.warning("gluster " + new_config_dir + " already exists")

        # Choose one of the instances as the "head" node. 
        # The head node is special since it "runs" the installation. 
        config.head_node = containers[0]

        # Start making the changes. 
        try:
            # Write out the list of all addresses
            entry_point['gluster'] = config.head_node['data_ip']
            entry_point['instances'] = []
            for server in containers:
                entry_point['instances'].append([server['data_ip'], server['host_name']])

            # These are the commands the head node will execute. 
            in_file = open(self.template_dir + '/configure.template', 'r')
            out_file = open(new_config_dir + '/configure', 'w+')

            probe = ""
            volume_id = "gluster-volume-" + str(config.uuid)
            volumes = "gluster volume create " + str(volume_id) + " "
            for server in containers:
                # The head node should not list itself in the peer probe.
                if server != config.head_node:
                    probe += "gluster peer probe " + str(server['data_ip']) + "\n"

                # All vumes get listed including the head node. 
                volumes += str(server['data_ip']) + ":/" + config.data_directory + " "

            # Now make the changes to the template file. 
            entry_point['volume'] = volume_id
            changes = { "BRICK_DIR":config.data_directory, 
                        "PEER_PROBE":probe,
                        "VOLUME_LIST":volumes,
                        "VOLUME_ID":volume_id }
            for line in in_file:
                s = Template(line).substitute(changes)
                out_file.write(s)

            in_file.close()
            out_file.close()

            # Change the permissions of the configure file to be executable.
            os.chmod(new_config_dir + '/configure', 
                     stat.S_IRUSR |
                     stat.S_IWUSR |
                     stat.S_IXUSR | 
                     stat.S_IRGRP |
                     stat.S_IWGRP |
                     stat.S_IXGRP |
                     stat.S_IROTH)
        except IOError as e:
            logging.error(e.strerror)

        # We need to assign a configuration to each container. 
        config_dirs = []
        for c in containers:
            config_dirs.append([c['container'],
                                new_config_dir, 
                                config.config_directory])

        return config_dirs, entry_point

"""
A GlusterFS configuration. 
"""
class GlusterConfig(object):
    data_directory = '/service/data/'
    log_directory = '/service/logs/'
    config_directory = '/service/conf/gluster/'

    BRICK_PORT = 24009
    MANAGEMENT_PORT = 24007

    def __init__(self, num):
        self.num = num
        self.data_directory = GlusterConfig.data_directory
        self.log_directory = GlusterConfig.log_directory
        self.config_directory = GlusterConfig.config_directory
        self.mode = 'stripe,replicate' # Use both striping and replication
        self.stripe_count = 2 * num
        self.stripe_size = '128kb'
        self.head_node = None
        self.uuid = None
