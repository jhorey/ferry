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

import sys
import sh
from string import Template
from ferry.config.mongo.mongoconfig import *

class MongoClientInitializer(object):
    def __init__(self):
        """
        Create a new initializer
        Param user The user login for the git repo
        """
        self.mongo = MongoInitializer()
        self.container_data_dir = self.mongo.container_data_dir
        self.container_log_dir = self.mongo.container_log_dir

    @property
    def fabric(self):
        self.mongo.fabric

    @fabric.setter
    def fabric(self, value):
        self.mongo.fabric = value

    @property
    def template_dir(self):
        self.mongo.template_dir

    @template_dir.setter
    def template_dir(self, value):
        self.mongo.template_dir = value

    @property
    def template_repo(self):
        self.mongo.template_repo

    @template_repo.setter
    def template_repo(self, value):
        self.mongo.template_repo = value

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'mongo_client' + str(instance_id)

    """
    Start the service on the containers. 
    """
    def start_service(self, containers, entry_point, fabric):
        return self.mongo.start_service(containers, entry_point, fabric)
    def restart_service(self, containers, entry_point, fabric):
        return self.mongo.restart_service(containers, entry_point, fabric)
    def stop_service(self, containers, entry_point, fabric):        
        return self.mongo.stop_service(containers, entry_point, fabric)

    """
    Get the ports necessary.
    """
    def get_necessary_ports(self, num_instances):
        return self.mongo.get_necessary_ports(num_instances)

    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        return self.mongo.get_exposed_ports(num_instances)

    """
    Generate a new configuration
    Param num Number of instances that need to be configured
    Param image Image type of the instances
    """
    def generate(self, num):
        return self.mongo.generate(num)

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers):
        config_dirs, entry_point = self.mongo.apply(config, containers)
        entry_point['type'] = 'mongo-client'
        entry_point['ip'] = entry_point['mongo']
        return config_dirs, entry_point
