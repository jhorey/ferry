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
import sh
import sys
from string import Template
from ferry.docker.fabric import DockerFabric

class MetaStoreInitializer(object):
    """
    Create a new initializer
    Param user The user login for the git repo
    """
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.container_data_dir = MetaStoreConfig.data_directory
        self.container_log_dir = MetaStoreConfig.log_directory

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'hive-metastore' + str(instance_id)

    """
    Start the service on the containers. 
    """
    def _execute_service(self, containers, entry_point, fabric, cmd):
        output = fabric.cmd(containers, '/service/sbin/startnode %s metastore' % cmd)
    def start_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "start")
    def restart_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "restart")
    def stop_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "stop")

    """
    Generate a new configuration.
    """
    def _generate_config_dir(self, uuid):
        return 'hive_ms_' + str(uuid)

    """
    Get the ports necessary. 
    """
    def get_necessary_ports(self, num_instances):
        return [MetaStoreConfig.POSTGRES_PORT, 
                MetaStoreConfig.METASTORE_PORT,
                MetaStoreConfig.SERVER_PORT]

    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        return []

    """
    Generate a new configuration
    """
    def generate(self, num):
        return MetaStoreConfig(num)

    """
    Generate the postgres configuration. 
    """
    def _generate_postgres_site(self, new_config_dir):
        in_file = open(self.template_dir + '/postgresql.conf', 'r')
        out_file = open(new_config_dir + '/postgresql.conf', 'w+')

        for line in in_file:
            out_file.write(line)

        in_file.close()
        out_file.close()

    """
    Generate the security configuration. 
    """
    def _generate_security_site(self, entry_point, new_config_dir):
        in_file = open(self.template_dir + '/pg_hba.conf', 'r')
        out_file = open(new_config_dir + '/pg_hba.conf', 'w+')

        # We need to figure out the local mask so that clients can connect
        # to the statistics database. Right now we're guessing. 
        p = entry_point['db'].split(".")
        subnet = "%s.%s.%s.1/24" % (p[0], p[1], p[2])
        changes = { "LOCAL_IP" : entry_point['db'],
                    "LOCAL_MASK" : subnet }
        for line in in_file:
            s = Template(line).substitute(changes)
            out_file.write(s)

        in_file.close()
        out_file.close()

    """
    Generate the hive site configuration. 
    """
    def _generate_hive_site(self, entry_point, config, new_config_dir):
        in_file = open(self.template_dir + '/hive-site.xml.template', 'r')
        out_file = open(new_config_dir + '/hive-site.xml', 'w+')
        
        changes = { "DB": entry_point['db'],
                    "USER": os.environ['USER'] }
        for line in in_file:
            s = Template(line).substitute(changes)
            out_file.write(s)

        in_file.close()
        out_file.close()

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers):
        # The "entry point" is the way to contact the storage service.
        # For gluster this is the IP address of the "master" and the volume name. 
        entry_point = { 'type' : 'hive' }

        # Remember the entry points
        entry_point['db'] = str(containers[0]['data_ip'])

        # Create a new configuration directory, and place
        # into the template directory. 
        config_dirs = []
        new_config_dir = "/tmp/postgres/" + self._generate_config_dir(config.uuid)
        hive_config_dir = "/tmp/hive/" + self._generate_config_dir(config.uuid)
        try:
            sh.mkdir('-p', new_config_dir)
            sh.mkdir('-p', hive_config_dir)
        except:
            sys.stderr.write('could not create config dir ' + new_config_dir)

        self._generate_postgres_site(new_config_dir)
        self._generate_security_site(entry_point, new_config_dir)
        self._generate_hive_site(entry_point, config, hive_config_dir)

        # Each container needs to point to a new config dir. 
        for c in containers:
            config_files = new_config_dir + '/*'
            config_dirs.append([c['container'],
                                config_files, 
                                config.config_directory])

        # Transfer the Hive config
        for c in containers:
            config_files = hive_config_dir + '/*'
            config_dirs.append([c['container'],
                                config_files, 
                                config.hive_config])

        # Merge the Hadoop configuration
        from_files = config.hadoop_dirs[0][1]
        for c in containers:
            config_dirs.append([c['container'],
                                from_files, 
                                config.hadoop_config])
        return config_dirs, entry_point

class MetaStoreConfig(object):
    data_directory = '/service/data/main'
    log_directory = '/service/data/logs'
    tmp_directory = '/service/data/tmp'
    config_directory = '/etc/postgresql/9.3/main/'
    hive_config = '/service/packages/hive/conf'
    hadoop_config = '/service/packages/hadoop/etc/hadoop'

    POSTGRES_PORT = 5432
    METASTORE_PORT = 9083
    SERVER_PORT = 10000

    def __init__(self, num):
        self.data_directory = MetaStoreConfig.data_directory
        self.log_directory = MetaStoreConfig.log_directory
        self.tmp_directory = MetaStoreConfig.tmp_directory
        self.config_directory = MetaStoreConfig.config_directory
        self.hive_config = MetaStoreConfig.hive_config
        self.hadoop_config = MetaStoreConfig.hadoop_config

        self.num = num
        self.system_info = None
        self.hadoop_dirs = None
        self.metastore = None
