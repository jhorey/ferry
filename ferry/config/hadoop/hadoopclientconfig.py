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
import sys
import sh
from string import Template
from ferry.install import FERRY_HOME
from ferry.docker.fabric import DockerFabric
from ferry.config.hadoop.hiveconfig import *
from ferry.config.system.info import *

class HadoopClientInitializer(object):
    """
    Create a new initializer
    Param user The user login for the git repo
    """
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.hive_client = HiveClientInitializer()
        self.hive_client.template_dir = FERRY_HOME + '/data/templates/hive-metastore/'

        self.container_data_dir = None
        self.container_log_dir = HadoopClientConfig.log_directory

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'hadoop-client' + str(instance_id)

    """
    Start the service on the containers. 
    """
    def _execute_service(self, containers, entry_point, fabric, cmd):
        # We need to know what sort of storage backend we are
        # using, since this will help set up everything.
        if entry_point['hdfs_type'] == 'hadoop':
            output = fabric.cmd(containers, '/service/sbin/startnode %s hadoop' % cmd)
        elif entry_point['hdfs_type'] == 'gluster':
            mount_url = entry_point['gluster_url']
            output = fabric.cmd(containers, 
                                '/service/sbin/startnode %s gluster %s' % (cmd, mount_url))
        return output
    def start_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "start")
    def restart_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "restart")
    def stop_service(self, containers, entry_point, fabric):        
        return self._execute_service(containers, entry_point, fabric, "stop")

    """
    Generate a new configuration.
    """
    def _generate_config_dir(self, uuid):
        return 'hadoop_client_' + str(uuid)

    """
    Get the ports necessary. 
    """
    def get_necessary_ports(self, num_instances):
        return []

    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        return []

    """
    Generate a new configuration
    """
    def generate(self, num):
        return HadoopClientConfig(num)

    """
    Generate the core-site configuration for a local filesystem. 
    """
    def _generate_gluster_core_site(self, mount_point, new_config_dir):
        core_in_file = open(self.template_dir + '/core-site.xml.template', 'r')
        core_out_file = open(new_config_dir + '/core-site.xml', 'w+')

        changes = { "DEFAULT_NAME":"file:///", 
                    "DATA_TMP":"/service/data/client/tmp" }
        for line in core_in_file:
            s = Template(line).substitute(changes)
            core_out_file.write(s)

        core_in_file.close()
        core_out_file.close()

    def _generate_log4j(self, new_config_dir):
        in_file = open(self.template_dir + '/log4j.properties', 'r')
        out_file = open(new_config_dir + '/log4j.properties', 'w+')

        for line in in_file:
            out_file.write(line)

        in_file.close()
        out_file.close()

    def _generate_core_site(self, hdfs_master, new_config_dir):
        """
        Generate the core-site configuration. 
        """
        core_in_file = open(self.template_dir + '/core-site.xml.template', 'r')
        core_out_file = open(new_config_dir + '/core-site.xml', 'w+')

        default_name = "%s://%s:%s" % ("hdfs",
                                       hdfs_master,
                                       HadoopClientConfig.HDFS_MASTER)
        changes = { "DEFAULT_NAME":default_name,
                    "DATA_TMP":"/service/data/client/tmp" }
        for line in core_in_file:
            s = Template(line).substitute(changes)
            core_out_file.write(s)

        core_in_file.close()
        core_out_file.close()

    """
    Generate the yarn-site configuration. 
    """
    def _generate_yarn_site(self, yarn_master, new_config_dir):
        yarn_in_file = open(self.template_dir + '/yarn-site.xml.template', 'r')
        yarn_out_file = open(new_config_dir + '/yarn-site.xml', 'w+')

        changes = { "YARN_MASTER":yarn_master,
                    "DATA_STAGING":"/service/data/client/staging" }

        # Get memory information.
        changes['MEM'] = get_total_memory()
        changes['CMEM'] = max(get_total_memory() / 8, 512)
        changes['RMEM'] = 2 * changes['CMEM']
        changes['ROPTS'] = '-Xmx' + str(int(0.8 * changes['RMEM'])) + 'm'

        for line in yarn_in_file:
            s = Template(line).substitute(changes)
            yarn_out_file.write(s)

        yarn_in_file.close()
        yarn_out_file.close()


    """
    Generate the mapred-site configuration. 
    """
    def _generate_mapred_site(self, config, containers, new_config_dir):
        mapred_in_file = open(self.template_dir + '/mapred-site.xml.template', 'r')
        mapred_out_file = open(new_config_dir + '/mapred-site.xml', 'w+')

        # Most of these values aren't applicable for the client,
        # so just make up fake numbers. 
        changes = { "NODE_REDUCES":1, 
                    "NODE_MAPS":1,
                    "JOB_REDUCES":1,
                    "JOB_MAPS":1,
                    "HISTORY_SERVER":config.yarn_master, 
                    "DATA_TMP":"/service/data/client/tmp" }

        # Get memory information.
        changes['MMEM'] = max(get_total_memory() / 8, 512)
        changes['RMEM'] = 2 * changes['MMEM']
        changes['MOPTS'] = '-Xmx' + str(int(0.8 * changes['MMEM'])) + 'm'
        changes['ROPTS'] = '-Xmx' + str(int(0.8 * changes['RMEM'])) + 'm'

        for line in mapred_in_file:
            s = Template(line).substitute(changes)
            mapred_out_file.write(s)

        mapred_in_file.close()
        mapred_out_file.close()

    """
    Apply the Hive client configuration
    """
    def _apply_hive_client(self, config, containers):
        return self.hive_client.apply(config, containers)

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers):
        entry_point = { 'type' : 'hadoop-client' }
        entry_point['ip'] = containers[0]['data_ip']

        # Create a new configuration directory, and place
        # into the template directory. 
        new_config_dir = "/tmp/" + self._generate_config_dir(config.uuid)
        try:
            sh.mkdir('-p', new_config_dir)
        except:
            sys.stderr.write('could not create config dir ' + new_config_dir)

        # Check if there is an explicit compute cluster. If there
        # is, then we use that for YARN information. 
        storage = containers[0]['storage'][0]
        compute = None
        if 'compute' in containers[0] and len(containers[0]['compute']) > 0:
            compute = containers[0]['compute'][0]

        if compute and 'yarn' in compute:
            config.yarn_master = compute['yarn']
            if 'db' in compute:
                config.hive_meta = compute['db']                
        else:
            # Use the storage backend for the YARN info. However, first
            # check if the storage is compatible.
            if 'yarn' in storage:
                config.yarn_master = storage['yarn']
            if 'db' in storage:
                config.hive_meta = storage['db']

        # Check what sort of storage we are using.
        entry_point['hdfs_type'] = storage['type']
        if storage['type'] == 'hadoop':
            config.hdfs_master = storage['hdfs']
            self._generate_core_site(config.hdfs_master, new_config_dir)
        elif storage['type'] == 'gluster':
            mount_url = "%s:/%s" % (storage['gluster'], storage['volume'])
            entry_point['gluster_url'] = mount_url
            self._generate_gluster_core_site('/data', new_config_dir)

        # Generate the Hadoop conf files.
        if config.yarn_master:
            self._generate_log4j(new_config_dir)
            self._generate_mapred_site(config, containers, new_config_dir)
            self._generate_yarn_site(config.yarn_master, new_config_dir)

        # Each container needs to point to a new config dir. 
        config_dirs = []
        for c in containers:
            config_dirs.append([c['container'],
                                new_config_dir + '/*',
                                config.config_directory])

        # Now configure the Hive client.
        if config.hive_meta:
            hive_config = HiveClientConfig(1)
            hive_config.uuid = config.uuid
            hive_config.hadoop_config_dir = config.config_directory
            hive_config.metastore = config.hive_meta
            hive_dirs, hive_entry = self._apply_hive_client(hive_config, containers)
            config_dirs.extend(hive_dirs)

        return config_dirs, entry_point

class HadoopClientConfig(object):
    log_directory = '/service/data/logs/'
    config_directory = '/service/conf/hadoop/'

    HDFS_MASTER = 9000

    def __init__(self, num):
        self.num = num
        self.config_directory = HadoopClientConfig.config_directory
        self.system_info = None
        self.yarn_master = None
        self.hdfs_master = None
        self.hive_meta = None
