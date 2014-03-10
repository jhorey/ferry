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
import importlib
import inspect
from pymongo import MongoClient
from ferry.docker.fabric import DockerFabric
from ferry.docker.docker import DockerInstance

class DeployEngine(object):
    def __init__(self, docker):
        self.docker = docker
        self.engines = {}
        self._load_engines()

    """
    Deploy the containers. This is a local version that
    uses either the local registry or a private registry. 
    """
    def deploy(self, cluster_uuid, containers, conf=None):
        if conf['_mode'] in self.engines:
            engine = self.engines[conf['_mode']]
            engine.deploy(cluster_uuid, containers, conf)

    """
    Dynamically load all the deployment engines
    """
    def _load_engines(self):
        engine_dir = os.environ['FERRY_HOME'] + '/deploy'
        files = os.listdir(engine_dir)
        for f in files:
            p = engine_dir + os.sep + f
            c = self._load_class(p)
            if c:
                self.engines[c.type] = c

    """
    Dynamically load a class from a string
    """
    def _load_class(self, full_name):
        class_info = full_name.split("/")[-1].split(".")
        module_name = class_info[0]
        file_extension = class_info[1]

        # Ignore the init and compiled files. 
        if module_name == "__init__" or file_extension == "pyc":
            return None

        # Construct the full module path. This lets us filter out only
        # the deployment engines and ignore all the other imported packages. 
        module_path = "ferry.deploy.%s" % module_name
        module = importlib.import_module(module_path)
        for n, o in inspect.getmembers(module):
            if inspect.isclass(o):
                if o.__module__ == module_path:
                    return o(self.docker)
        return None

    """
    Find the deployed application. 
    """
    def find(self, one=False, spec=None, conf=None):
        all_engines = []
        if conf and conf['_mode'] in self.engines:
            all_engines.append(self.engines[conf['_mode']])
        else:
            all_engines = self.engines.values()

        all_v = []
        for e in all_engines:
            v = e.find(one, spec, conf)
            if v and one:
                return v
            elif v:
                all_v.append(v)
                
        if one:
            return None
        else:
            return all_v
