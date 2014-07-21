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
import time
import sh
from string import Template
from ferry.install import FERRY_HOME
from ferry.docker.fabric import DockerFabric
from ferry.config.hadoop.hiveconfig import *
from ferry.config.hadoop.metastore  import *
from ferry.config.system.info import *

class HadoopInitializer(object):

    def __init__(self):
        """
        Create a new initializer
        Param user The user login for the git repo
        """
        self.template_dir = None
        self.template_repo = None

        self.container_data_dir = HadoopConfig.data_directory
        self.container_log_dir = HadoopConfig.log_directory

        self.hive_client = HiveClientInitializer()
        self.hive_ms = MetaStoreInitializer()
        self.hive_client.template_dir = FERRY_HOME + '/data/templates/hive-metastore/'
        self.hive_ms.template_dir = FERRY_HOME + '/data/templates/hive-metastore/'

    def new_host_name(self, instance_id):
        """
        Generate a new hostname
        """
        return 'hadoop' + str(instance_id)

    def _execute_service(self, containers, entry_point, fabric, cmd):
        """
        Start the service on the containers. 
        """
        yarn_master = entry_point['yarn']
        hdfs_master = None

        # Now start the HDFS cluster. 
        if entry_point['hdfs_type'] == 'hadoop':
            hdfs_master = entry_point['hdfs']
            for c in containers:
                if c.service_type == 'hadoop':
                    if c.internal_ip == hdfs_master:
                        output = fabric.cmd([c], '/service/sbin/startnode %s namenode' % cmd)
                    elif c.internal_ip != yarn_master:
                        output = fabric.cmd([c], '/service/sbin/startnode %s datanode' % cmd)

            # Now wait a couple seconds to make sure
            # everything has started.
            time.sleep(5)
        elif entry_point['hdfs_type'] == 'gluster':
            mount_url = entry_point['gluster_url']
            output = fabric.cmd(containers, 
                                '/service/sbin/startnode %s gluster %s' % (cmd, mount_url))
                                
        # Now start the YARN cluster. 
        for c in containers:
            if c.service_type == 'hadoop' or c.service_type == 'yarn':
                if c.internal_ip == yarn_master:
                    output = fabric.cmd([c], '/service/sbin/startnode %s yarnmaster' % cmd)
                elif c.internal_ip != hdfs_master:
                    output = fabric.cmd([c], '/service/sbin/startnode %s yarnslave' % cmd)

        # Now start the Hive metastore. 
        for c in containers:
            if c.service_type == 'hive':
                self.hive_ms._execute_service([c], None, fabric, cmd)

    def start_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "start")
    def restart_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "restart")

    def stop_service(self, containers, entry_point, fabric):
        output = fabric.cmd(containers, '/service/sbin/startnode stop')

    def _generate_config_dir(self, uuid, container):
        """
        Generate a new configuration.
        """
        return 'hadoop_' + str(uuid) + '_' + str(container['data_ip'])

    def get_necessary_ports(self, num_instances):
        """
        Get the ports necessary. 
        """
        return []

    def get_exposed_ports(self, num_instances):
        """
        Get the ports to expose internally between containers
        (but not outside containers). 
        """
        ports = []
        ports.append(HadoopConfig.YARN_SCHEDULER)
        ports.append(HadoopConfig.YARN_ADMIN)
        ports.append(HadoopConfig.YARN_IPC)
        ports.append(HadoopConfig.YARN_RESOURCE)
        ports.append(HadoopConfig.YARN_TRACKER)
        ports.append(HadoopConfig.YARN_HTTP)
        ports.append(HadoopConfig.YARN_HTTPS)
        ports.append(HadoopConfig.YARN_JOB_HISTORY)
        ports.append(HadoopConfig.YARN_JOB_HISTORY_HTTP)
        ports.append(HadoopConfig.HDFS_MASTER)
        ports.append(HadoopConfig.HDFS_HTTP)
        ports.append(HadoopConfig.DATA_HTTP)
        ports.append(HadoopConfig.SECOND_HTTP)
        ports.append(HadoopConfig.YARN_RPC_PORTS)
        ports.append(HadoopConfig.HIVE_META)
        ports.append(HadoopConfig.HIVE_SERVER)
        return ports

    def get_total_instances(self, num_instances, layers):
        """
        Get total number of instances. For Hadoop we must have additional containers
        for the YARN master, HDFS master, and possibly the Hive metastore. 
        """
        instances = []

        for i in range(num_instances + 2):
            instances.append('hadoop')

        if len(layers) > 0 and layers[0] == "hive":
            instances.append('hive')

        return instances

    def generate(self, num):
        """
        Generate a new configuration
        """
        return HadoopConfig(num)

    def _generate_gluster_core_site(self, new_config_dir, container):
        """
        Generate the core-site configuration for a local filesystem. 
        """
        core_in_file = open(self.template_dir + '/core-site.xml.template', 'r')
        core_out_file = open(new_config_dir + '/core-site.xml', 'w+')

        changes = { "DEFAULT_NAME":"file:///", 
                    "DATA_TMP":"/service/data/%s/tmp" % container['host_name'] }
        for line in core_in_file:
            s = Template(line).substitute(changes)
            core_out_file.write(s)

        core_in_file.close()
        core_out_file.close()

    def _generate_core_site(self, hdfs_master, new_config_dir):
        """
        Generate the core-site configuration. 
        """
        core_in_file = open(self.template_dir + '/core-site.xml.template', 'r')
        core_out_file = open(new_config_dir + '/core-site.xml', 'w+')

        default_name = "%s://%s:%s" % ("hdfs",
                                       hdfs_master['data_ip'],
                                       HadoopConfig.HDFS_MASTER)
        changes = { "DEFAULT_NAME":default_name,
                    "DATA_TMP":"/service/data/tmp" }
        for line in core_in_file:
            s = Template(line).substitute(changes)
            core_out_file.write(s)

        core_in_file.close()
        core_out_file.close()

    def _generate_hdfs_site(self, config, hdfs_master, new_config_dir):
        """
        Generate the hdfs-site configuration. 
        """
        hdfs_in_file = open(self.template_dir + '/hdfs-site.xml.template', 'r')
        hdfs_out_file = open(new_config_dir + '/hdfs-site.xml', 'w+')

        changes = { "DATA_DIR":config.data_directory }
        for line in hdfs_in_file:
            s = Template(line).substitute(changes)
            hdfs_out_file.write(s)

        hdfs_in_file.close()
        hdfs_out_file.close()

    def _generate_httpfs_site(self, config, new_config_dir):
        """
        Generate the hdfs-site configuration. 
        """
        in_file = open(self.template_dir + '/httpfs-site.xml.template', 'r')
        out_file = open(new_config_dir + '/httpfs-site.xml', 'w+')

        changes = {}
        for line in in_file:
            s = Template(line).substitute(changes)
            out_file.write(s)

        in_file.close()
        out_file.close()

    def _generate_yarn_site(self, yarn_master, new_config_dir, container=None):
        """
        Generate the yarn-site configuration. 
        """
        yarn_in_file = open(self.template_dir + '/yarn-site.xml.template', 'r')
        yarn_out_file = open(new_config_dir + '/yarn-site.xml', 'w+')

        changes = { "YARN_MASTER":yarn_master['data_ip'] } 

        # Get memory information.
        changes['MEM'] = get_total_memory()
        changes['CMEM'] = max(get_total_memory() / 8, 512)
        changes['RMEM'] = 2 * changes['CMEM']
        changes['ROPTS'] = '-Xmx' + str(int(0.8 * changes['RMEM'])) + 'm'
        
        # Generate the staging table. This differs depending on whether
        # we need to be container specific or not. 
        if container:
            changes['DATA_STAGING'] = '/service/data/%s/staging' % container['host_name']
        else:
            changes['DATA_STAGING'] = '/service/data/staging'

        for line in yarn_in_file:
            s = Template(line).substitute(changes)
            yarn_out_file.write(s)

        yarn_in_file.close()
        yarn_out_file.close()

    def _generate_log4j(self, new_config_dir):
        in_file = open(self.template_dir + '/log4j.properties', 'r')
        out_file = open(new_config_dir + '/log4j.properties', 'w+')

        for line in in_file:
            out_file.write(line)

        in_file.close()
        out_file.close()

    def _generate_yarn_env(self, yarn_master, new_config_dir):
        """
        Generate the yarn-env configuration. 
        """
        yarn_in_file = open(self.template_dir + '/yarn-env.sh.template', 'r')
        yarn_out_file = open(new_config_dir + '/yarn-env.sh', 'w+')

        for line in yarn_in_file:
            yarn_out_file.write(line)

        yarn_in_file.close()
        yarn_out_file.close()

    def _generate_mapred_env(self, new_config_dir):
        """
        Generate the yarn-env configuration. 
        """
        in_file = open(self.template_dir + '/mapred-env.sh', 'r')
        out_file = open(new_config_dir + '/mapred-env.sh', 'w+')

        for line in in_file:
            out_file.write(line)

        in_file.close()
        out_file.close()

    def _generate_mapred_site(self, yarn_master, config, containers, new_config_dir, container=None):
        """
        Generate the mapred-site configuration. 
        """
        mapred_in_file = open(self.template_dir + '/mapred-site.xml.template', 'r')
        mapred_out_file = open(new_config_dir + '/mapred-site.xml', 'w+')
        changes = {"HISTORY_SERVER":yarn_master['data_ip']}

        # Get memory information.
        changes['MMEM'] = max(get_total_memory() / 8, 512)
        changes['RMEM'] = 2 * changes['MMEM']
        changes['MOPTS'] = '-Xmx' + str(int(0.8 * changes['MMEM'])) + 'm'
        changes['ROPTS'] = '-Xmx' + str(int(0.8 * changes['RMEM'])) + 'm'

        # These are the mapred variables. 
        changes['NODE_REDUCES'] = get_total_memory() / ( len(containers) - 2 ) / 2
        changes['NODE_MAPS'] = changes['NODE_REDUCES'] * 4
        changes['JOB_MAPS'] = changes['NODE_MAPS'] * ( len(containers) - 2 )
        changes['JOB_REDUCES'] = changes['NODE_REDUCES'] * ( len(containers) - 2 )

        # Generate the temp area. This differs depending on whether
        # we need to be container specific or not. 
        if container:
            changes['DATA_TMP'] = '/service/data/%s/tmp' % container['host_name']
        else:
            changes['DATA_TMP'] = '/service/data/tmp'

        for line in mapred_in_file:
            s = Template(line).substitute(changes)
            mapred_out_file.write(s)

        mapred_in_file.close()
        mapred_out_file.close()

    def _apply_hive_metastore(self, config, containers):
        """
        Apply the Hive metastore configuration
        """
        return self.hive_ms.apply(config, containers)

    def _apply_hive_client(self, config, containers):
        """
        Apply the Hive client configuration
        """
        return self.hive_client.apply(config, containers)

    def _apply_hadoop(self, config, containers):
        """
        Apply the Hadoop configuration
        """
        entry_point = { 'type' : 'hadoop' }

        # Pick out the various master nodes. The Hadoop configuration assumes
        # that the first two containers are used for metadata purposes. 
        yarn_master = containers[0]
        hdfs_master = containers[1]
            
        # Remember the entry points
        entry_point['yarn'] = str(yarn_master['data_ip'])
        entry_point['hdfs'] = str(hdfs_master['data_ip'])
        entry_point['instances'] = []

        # Create a new configuration directory, and place
        # into the template directory. 
        config_dirs = []
        for c in containers:
            new_config_dir = "/tmp/" + self._generate_config_dir(config.uuid, c)
            try:
                sh.mkdir('-p', new_config_dir)
            except:
                sys.stderr.write('could not create config dir ' + new_config_dir)

            # Only add the container to the instances list once. 
            entry_point['instances'].append([c['data_ip'], c['host_name']])

            # Generate some mapred-site config
            self._generate_mapred_site(yarn_master, config, containers, new_config_dir)
            self._generate_mapred_env(new_config_dir)

            # Now generate the yarn config files
            self._generate_yarn_site(yarn_master, new_config_dir)
            self._generate_yarn_env(yarn_master, new_config_dir)

            # Now generate the core config
            self._generate_core_site(hdfs_master, new_config_dir)

            # Now generate the HDFS config
            self._generate_hdfs_site(config, hdfs_master, new_config_dir)

            # Now generate the HDFS config
            self._generate_httpfs_site(config, new_config_dir)

            # Generate the log4j config
            self._generate_log4j(new_config_dir)

            config_dirs.append([c['container'], 
                                new_config_dir + '/*',
                                config.config_directory])

        return config_dirs, entry_point

    def _find_hadoop_storage(self, containers):
        """
        Find a Hadoop compatible storage entry. 
        """
        for c in containers:
            for s in c['storage']:
                if s['type'] == 'gluster' or s['type'] == 'hadoop':
                    return s

    def _apply_yarn(self, config, containers):
        """
        Apply the YARN-only configuration
        """
        entry_point = { 'type' : 'yarn' }

        # Pick out the various master nodes. The Hadoop configuration assumes
        # that the first two containers are used for metadata purposes. 
        yarn_master = containers[0]
        entry_point['yarn'] = str(yarn_master['data_ip'])
        entry_point['instances'] = []

        # Create a new configuration directory, and place
        # into the template directory. 
        config_dirs = []
        for c in containers:            
            new_config_dir = "/tmp/" + self._generate_config_dir(config.uuid, c)
            try:
                sh.mkdir('-p', new_config_dir)
            except:
                sys.stderr.write('could not create config dir ' + new_config_dir)

            # Slaves file used to figure out who hosts the actual work/data
            for server in containers:
                entry_point['instances'].append([server['data_ip'], server['host_name']])

            # Generate the log4j config
            self._generate_log4j(new_config_dir)

            # Generate some mapred-site config
            self._generate_mapred_site(yarn_master, config, containers, new_config_dir, c)
            self._generate_mapred_env(new_config_dir)

            # Now generate the yarn config files
            self._generate_yarn_site(yarn_master, new_config_dir, c)
            self._generate_yarn_env(yarn_master, new_config_dir)

            # Now we need to configure additional storage parameters. For example,
            # for Gluster, etc. 
            storage_entry = self._find_hadoop_storage(containers)
            entry_point['hdfs_type'] = storage_entry['type']
            if storage_entry['type'] == 'gluster':
                url = self._apply_gluster(config, storage_entry, new_config_dir, c)
                entry_point['gluster_url'] = url

            config_dirs.append([c['container'], 
                                new_config_dir + '/*',
                                config.config_directory])
        return config_dirs, entry_point

    def _apply_hive(self, config, hadoop_entry, hadoop_dirs, hadoop_containers, hive_containers):
        # First configure the metastore service
        ms_config = MetaStoreConfig(1)
        ms_config.uuid = config.uuid
        ms_config.hadoop_dirs = hadoop_dirs
        ms_dirs, ms_entry = self._apply_hive_metastore(ms_config, hive_containers)

        # Now configure the Hive client. This configuration
        # gets applied to the Hadoop containers. 
        hive_config = HiveClientConfig(1)
        hive_config.uuid = config.uuid
        hive_config.hadoop_config_dir = config.config_directory
        hive_config.metastore = ms_entry['db']
        hive_dirs, hive_entry = self._apply_hive_client(hive_config, hadoop_containers)
        hive_dirs.extend(ms_dirs)
        return hive_dirs, hive_config

    def _apply_gluster(self, config, storage_entry, new_config_dir, container):
        # We assume that the new configuration directory has already 
        # been created. In the future, may want to check for this. 
        self._generate_gluster_core_site(new_config_dir, container)

        # The mount URL specifies how to connect to Gluster. 
        mount_url = "%s:/%s" % (storage_entry['gluster'], storage_entry['volume'])
        return mount_url

    def apply(self, config, containers):
        """
        Apply the configuration to the instances
        """
        # First separate the Hadoop and Hive containers.
        hadoop_containers = []
        hive_containers = []
        for c in containers:
            if c['type'] == 'hadoop' or c['type'] == 'yarn':
                hadoop_containers.append(c)
            elif c['type'] == 'hive':
                hive_containers.append(c)

        if 'storage' in hadoop_containers[0]:
            # This Hadoop instance is being applied to an existing
            # storage mechanism. So just configure yarn.
            hadoop_dirs, hadoop_entry = self._apply_yarn(config, hadoop_containers)
        else:
            # This Hadoop instance is being applied for both storage
            # and compute. Right now there's no way to just instantiate HDFS. 
            hadoop_dirs, hadoop_entry = self._apply_hadoop(config, hadoop_containers)
            hadoop_entry['hdfs_type'] = 'hadoop'

        hive_entry = {}
        if len(hive_containers) > 0:
            # We also need to configure some Hive services
            hive_dirs, hive_config = self._apply_hive(config, hadoop_entry, hadoop_dirs, hadoop_containers, hive_containers)

            # Now merge the configuration dirs.
            hadoop_dirs.extend(hive_dirs)
            hadoop_entry['db'] = hive_config.metastore

        return hadoop_dirs, hadoop_entry

class HadoopConfig(object):
    data_directory = '/service/data/main'
    log_directory = '/service/data/logs'
    tmp_directory = '/service/data/tmp'
    config_directory = '/service/conf/hadoop'

    YARN_SCHEDULER = 8030
    YARN_IPC = 8032
    YARN_ADMIN = 8033
    YARN_RESOURCE = 8041
    YARN_TRACKER = 8025
    YARN_HTTP = 8088
    YARN_HTTPS = 8090
    YARN_JOB_HISTORY = 10020
    YARN_JOB_HISTORY_HTTP = 19888
    HDFS_MASTER = 9000
    HDFS_HTTP = 50070
    DATA_HTTP = 50075
    SECOND_HTTP = 50090
    YARN_RPC_PORTS = '50100-50200'
    HIVE_META = 9083
    HIVE_SERVER = 10000

    def __init__(self, num):
        self.num = num
        self.data_directory = HadoopConfig.data_directory
        self.log_directory = HadoopConfig.log_directory
        self.tmp_directory = HadoopConfig.tmp_directory
        self.config_directory = HadoopConfig.config_directory
        self.system_info = None
