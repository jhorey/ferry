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
import time
import logging
from ferry.docker.fabric import DockerFabric
from ferry.docker.docker import DockerInstance
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

class LocalDeploy(object):
    def __init__(self, docker):
        self.type = 'local'
        self.docker = docker
        self._try_connect()

    """
    Try connecting to mongo.
    """
    def _try_connect(self):
        for i in range(0, 3):
            try:
                self.mongo = MongoClient(os.environ['MONGODB'], 27017, connectTimeoutMS=6000)
                self.deploy_collection = self.mongo['state']['deploy']
                break
            except ConnectionFailure:
                time.sleep(2)

    """
    Generate a new deployment UUID
    """
    def _new_deploy_uuid(self, cluster_uuid):
        return "dp-%s-%s" % (cluster_uuid, str(uuid.uuid4()))

    """
    Deploy the containers. This is a local version that
    uses either the local registry or a private registry. 
    """
    def deploy(self, cluster_uuid, containers, conf=None):
        # Deploy the containers. 
        deployed = self.docker.deploy(containers)

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
        if one:
            return self.deploy_collection.find_one(spec)
        else:
            return self.deploy_collection.find(spec)
