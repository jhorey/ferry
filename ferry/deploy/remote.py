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
import uuid
import datetime
import logging
from pymongo import MongoClient
from ferry.docker.fabric import DockerFabric
from ferry.docker.docker import DockerInstance

class RemoteDeploy(object):
    def __init__(self, docker):
        self.type = 'remote'
        self.docker = docker
        self.mongo = None
        self.registry = None

    """
    Generate a new deployment UUID
    """
    def _new_deploy_uuid(self, cluster_uuid):
        return "dp-%s-%s" % (cluster_uuid, str(uuid.uuid4()))

    """
    Try connecting to mongo.
    """
    def _try_connect(self, mongo_url, mongo_port):
        for i in range(0, 3):
            try:
                self.mongo = MongoClient(mongo_url, 
                                         mongo_port, 
                                         connectTimeoutMS=6000)
                self.deploy_collection = self.mongo['state']['deploy']
                break
            except ConnectionFailure:
                time.sleep(2)

    """
    Initialize the registry and mongo information.
    """
    def _init_db(self, mongo, registry):
        self.registry = registry
        mongo_info = mongo.split(":")
        self._try_connect(mongo_info[0], 
                          int(mongo_info[1]))

    """
    Deploy the containers. This version uploads the images to a
    remote docker registry and a remote Mongo DB. 
    """
    def deploy(self, cluster_uuid, containers, conf=None):
        if conf:
            if 'registry' in conf and 'mongo' in conf:
                self._init_db(conf['mongo'], conf['registry'])

        if mongo and registry:
            # Deploy the containers. 
            deployed = self.docker.deploy(containers, self.registry)

            # Register the containers.
            deploy_uuid = self._new_deploy_uuid(cluster_uuid)
            deploy_ts = datetime.datetime.now()
            deploy_state = { 'ts' : deploy_ts, 
                             'uuid' : deploy_uuid,
                             'cluster_uuid' : cluster_uuid,
                             'connectors' : deployed }
            self.deploy_collection.insert( deploy_state )

    """
    Find the deployed application. 
    """
    def find(self, one=False, spec=None, conf=None):
        if conf:
            if 'registry' in conf and 'mongo' in conf:
                self._init_db(conf['mongo'], conf['registry'])

            if one:
                return self.deploy_collection.find_one(spec)
            else:
                return self.deploy_collection.find(spec)
