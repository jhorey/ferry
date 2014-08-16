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

import logging
import sh
import sys
from string import Template

class OpenMPIInitializer(object):
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.container_data_dir = None
        self.container_log_dir = MPIConfig.log_directory

    def new_host_name(self, instance_id):
        """
        Generate a new hostname
        """
        return 'openmpi' + str(instance_id)

    def _execute_service(self, containers, entry_point, fabric, cmd):
        """
        Start the service on the containers. 
        """
        master_output = fabric.cmd(containers[:1], '/service/sbin/startnode %s %s %s' % (cmd, entry_point['mount'], 'glustermaster'))
        slave_output = fabric.cmd(containers[1:len(containers)], '/service/sbin/startnode %s %s %s' % (cmd, entry_point['mount'], 'glusterslave'))
        return dict(master_output.items() + slave_output.items())
    def start_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "start")
    def restart_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "restart")
    def stop_service(self, containers, entry_point, fabric):        
        return self._execute_service(containers, entry_point, fabric, "stop")

    def _generate_config_dir(self, uuid):
        """
        Generate a new configuration.
        """
        return 'openmpi_' + str(uuid)

    def get_necessary_ports(self, num_instances):
        """
        Get the ports necessary.
        """
        return []

    def get_exposed_ports(self, num_instances):
        """
        Get the internal ports. 
        """
        BTL_PORT_END = MPIConfig.BTL_PORT_MIN + (MPIConfig.PORT_RANGE * num_instances)
        OOB_PORT_END = MPIConfig.OOB_PORT_MIN + (MPIConfig.PORT_RANGE * num_instances)
        BTL_PORTS = '%s-%s' % (MPIConfig.BTL_PORT_MIN, BTL_PORT_END)
        OOB_PORTS = '%s-%s' % (MPIConfig.OOB_PORT_MIN, OOB_PORT_END)
        return [BTL_PORTS, OOB_PORTS]

    def get_total_instances(self, num_instances, layers):
        instances = []

        for i in range(num_instances):
            instances.append('openmpi')

        return instances

    def generate(self, num):
        """
        Generate a new configuration
        Param num Number of instances that need to be configured
        Param image Image type of the instances

        """
        config = MPIConfig(num)
        config.btl_port_min = MPIConfig.BTL_PORT_MIN
        config.oob_port_min = MPIConfig.OOB_PORT_MIN
        config.btl_port_range = MPIConfig.PORT_RANGE * num
        config.oob_port_range = MPIConfig.PORT_RANGE * num

        return config

    def _generate_mca_params(self, config, new_config_dir):
        """
        Generate the mca-params configuration. 
        """
        in_file = open(self.template_dir + '/openmpi-mca-params.conf', 'r')
        out_file = open(new_config_dir + '/openmpi-mca-params.conf', 'w+')

        changes = { "BTL_PORT_MIN": config.btl_port_min,
                    "BTL_PORT_RANGE": config.btl_port_range,
                    "OOB_PORT_MIN": config.oob_port_min,
                    "OOB_PORT_RANGE": config.oob_port_range }
        for line in in_file:
            s = Template(line).substitute(changes)
            out_file.write(s)

        in_file.close()
        out_file.close()

    def _find_mpi_storage(self, containers):
        """
        Find a MPI compatible storage entry. 
        """
        for c in containers:
            for s in c['storage']:
                if s['type'] == 'gluster':
                    return s

    def _find_mpi_compute(self, containers):
        """
        Find a MPI compatible compute entry. 
        """
        for c in containers:
            for s in c['compute']:
                if s['type'] == 'openmpi':
                    return s
    
    def apply(self, config, containers):
        """
        Apply the configuration to the instances
        """
        entry_point = { 'type' : 'openmpi' }
        config_dirs = []

        new_config_dir = "/tmp/" + self._generate_config_dir(config.uuid)
        try:
            sh.mkdir('-p', new_config_dir)
        except:
            sys.stderr.write('could not create config dir ' + new_config_dir)

        # For now the MPI client assumes there is only one storage and that it is
        # a Gluster end point. 
        storage = self._find_mpi_storage(containers)
        if storage:
            mount_ip = storage['gluster']
            mount_dir = storage['volume']
            entry_point['mount'] = "%s:/%s" % (mount_ip, mount_dir)
            logging.warning("MOUNT: " + str(entry_point['mount']))

            # Check if we are being called as a compute instance or client.
            if not 'compute' in containers[0]:
                entry_point['hosts'] = []
                entry_point['instances'] = []
                for server in containers:
                    entry_point['instances'].append([server['data_ip'], server['host_name']])
                    entry_point['hosts'].append([server['data_ip'], server['host_name']])
            else:
                # This is the MPI client. First check if there are any compute
                # nodes (the MPI client can be used with just a raw GlusterFS
                # configuration). If it does have a compute, create a "hosts" file that contains the
                # IP addresses of the compute nodes. 
                entry_point['ip'] = containers[0]['data_ip']
                compute = self._find_mpi_compute(containers)
                if compute and 'hosts' in compute:
                    with open(new_config_dir + '/hosts', 'w+') as hosts_file:
                        for c in compute['hosts']:
                            hosts_file.write(c[0] + "\n")
                    self._generate_mca_params(config, new_config_dir)

            for c in containers:
                config_files = new_config_dir + '/*'
                config_dirs.append([c['container'],
                                    config_files, 
                                    config.config_directory])
        return config_dirs, entry_point

class MPIConfig(object):
    log_directory = '/service/logs/'
    config_directory = '/service/conf/openmpi/'

    BTL_PORT_MIN = 2000
    OOB_PORT_MIN = 6000
    PORT_RANGE = 4

    def __init__(self, num):
        self.num = num
        self.btl_port_min = 0
        self.btl_port_range = 0
        self.oob_port_min = 0
        self.oob_port_range = 0
        self.config_directory = MPIConfig.config_directory
        self.log_directory = MPIConfig.log_directory
