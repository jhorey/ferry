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
import datetime
import grp
import json
import logging
import os
import os.path
import pwd
import sh
import shutil
import stat
import sys
import time
import uuid
import yaml
from pymongo import MongoClient
from sets import Set
from ferry.install import *
from ferry.docker.resolve       import DefaultResolver
from ferry.docker.docker        import DockerInstance
from ferry.docker.fabric        import DockerFabric
from ferry.docker.configfactory import ConfigFactory
from ferry.docker.deploy        import DeployEngine

class DockerManager(object):
    SSH_PORT = 22

    def __init__(self):
        # Generate configuration.
        self.docker = DockerFabric()
        self.config = ConfigFactory()
        self.resolver = DefaultResolver()

        # Service mappings
        self.service = {
            'openmpi' : { 
                'server' : self.config.mpi,
                'client' : self.config.mpi_client },
            'yarn': { 
                'server' : self.config.yarn,
                'client' : self.config.hadoop_client },
            'spark': { 
                'server' : self.config.spark,
                'client' : self.config.spark_client },
            'gluster': { 
                'server' : self.config.gluster,
                'client' : self.config.mpi_client },
            'cassandra': { 
                'server' : self.config.cassandra,
                'client' : self.config.cassandra_client},
            'titan': { 
                'server' : self.config.titan,
                'client' : self.config.cassandra_client},
            'hadoop': { 
                'server' : self.config.hadoop,
                'client' : self.config.hadoop_client},
            'hive': { 
                'server' : self.config.hadoop,
                'client' : self.config.hadoop_client},
            'mongodb': { 
                'server' : self.config.mongo,
                'client' : self.config.mongo_client}
            }

        # Initialize the state. 
        self.deploy = DeployEngine(self.docker)
        self._init_state_db()
        self._clean_state_db()

    def _init_state_db(self):
        """
        Contact the state database. 
        """
        self.mongo = MongoClient(os.environ['MONGODB'], 27017, connectTimeoutMS=6000)

        self.cluster_collection = self.mongo['state']['clusters']
        self.service_collection = self.mongo['state']['services']
        self.snapshot_collection = self.mongo['state']['snapshots']

    def _clean_state_db(self):
        """
        Remove all the services that are "terminated". 
        """
        self.cluster_collection.remove( {'status':'removed'} )

    def _serialize_containers(self, containers):
        info = []
        for c in containers:
            info.append(c.json())
        return info

    def _update_service_configuration(self, service_uuid, service_info):
        """
        Update the service configuration. 
        """
        service = self.service_collection.find_one( {'uuid':service_uuid} )
        if not service:
            self.service_collection.insert( service_info )
        else:
            self.service_collection.update( {'uuid' : service_uuid},
                                            {'$set': service_info} )

    def _get_service_configuration(self, service_uuid, detailed=False):
        """
        Get the storage information. 
        """
        info = self.service_collection.find_one( {'uuid':service_uuid}, {'_id':False} )
        if info:
            if detailed:
                return info
            else:
                return info['entry']
        else:
            return None

    def _get_inspect_info(self, service_uuid):
        json_reply = {'uuid' : service_uuid}

        # Get the service information. If we can't find it,
        # return an empty reply (this shouldn't happen btw). 
        raw_info = self._get_service_configuration(service_uuid, detailed=True)
        if not raw_info:
            return json_reply

        # Get individual container information
        json_reply['containers'] = []
        for c in raw_info['containers']:
            json_reply['containers'].append(c)

        # Now get the entry information
        json_reply['entry'] = raw_info['entry']

        # Check if this service has a user-defined
        # unique name.
        if 'uniq' in raw_info:
            json_reply['uniq'] = raw_info['uniq']
        else:
            json_reply['uniq'] = None

        return json_reply

    def _get_snapshot_info(self, stack_uuid):
        v = self.cluster_collection.find_one( {'uuid' : stack_uuid} )
        if v:
            s = self.snapshot_collection.find_one( {'snapshot_uuid':v['snapshot_uuid']} )
            if s:
                time = s['snapshot_ts'].strftime("%m/%w/%Y (%I:%M %p)")
                return { 'snapshot_ts' : time,
                         'snapshot_uuid' : v['snapshot_uuid'] }

    def _get_service(self, service_type):
        if service_type in self.service:
            service = self.service[service_type]['server']
            service.fabric = self.docker
            return service
        else:
            logging.error("unknown service " + service_type)
            return None

    def _get_client_services(self, storage_entry, compute_entry):
        """
        Get a list of all the client types that are needed for the supplied
        storage and compute backends. So, for example, if the user has specified
        a Hadoop backend, then we'll need to supply the Hadoop client, etc. 
        """
        client_services = Set()
        service_names = []
        for storage in storage_entry:
            if storage['type'] in self.service:
                if 'client' in self.service[storage['type']]:
                    cs = self.service[storage['type']]['client']
                    cs.fabric = self.docker
                    client_services.add(cs)
                service_names.append(storage['type'])
        for compute in compute_entry:
            if compute['type'] in self.service:
                if 'client' in self.service[compute['type']]:
                    cs = self.service[compute['type']]['client']
                    cs.fabric = self.docker
                    client_services.add(cs)
                service_names.append(compute['type'])
        return client_services, service_names

    def _copytree(src, dst):
        """
        Helper method to copy directories. shutil fails if the 
        destination already exists. 
        """
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

    def _copy_instance_logs(self, instance, to_dir):
        service = self._get_service(instance.service_type)
        log_dir = service.container_log_dir

        # We're performing a reverse lookup. 
        for d in instance.volumes.keys():
            if instance.volumes[d] == log_dir:
                self._copytree(d, to_dir)
                return

    def copy_logs(self, stack_uuid, to_dir):
        _, compute, storage = self._get_cluster_instances(stack_uuid)
        storage_dir = to_dir + '/' + stack_uuid + '/storage'
        compute_dir = to_dir + '/' + stack_uuid + '/compute'

        for c in compute:
            for i in c['instances']:
                self._copy_instance_logs(i, compute_dir)
        for c in storage:
            for i in c['instances']:
                self._copy_instance_logs(i, storage_dir)

    def _inspect_application(self, app, directory):
        """
        Read out the contents of an application
        """
        s = app.split('/')
        if len(s) > 1:
            name = s[1]
        else:
            name = s[0]

        dir_path = os.path.dirname(os.path.join(directory, app))
        if os.path.exists(dir_path):
            for item in os.listdir(dir_path):
                n, e = item.split('.')
                if n == name:
                    with open(os.path.join(dir_path, item), 'r') as f:
                        return f.read()

    def inspect_installed(self, app):
        """
        Inspect an installed application
        """
        content = self._inspect_application(app, ferry.install.DEFAULT_BUILTIN_APPS)
        if not content:
            content = self._inspect_application(app, ferry.install.DEFAULT_FERRY_APPS)
        
        if content:
            return content
        else:
            return ""
        
    def inspect_deployed(self, uuid, registry):
        """
        Inspect a deployed stack. 
        """
        json_reply = {}

        # Need to inspect the registry to make sure
        # that all the images are available. 

        return json.dumps(json_reply, 
                          sort_keys=True,
                          indent=2,
                          separators=(',',':'))

    def inspect_stack(self, stack_uuid):
        """
        Inspect a running stack. 
        """
        json_reply = {}

        # Get the collection of all backends and connector UUIDS.
        cluster = self.cluster_collection.find_one( {'uuid': stack_uuid} )

        connector_uuids = []
        if cluster and 'connectors' in cluster:
            connector_uuids = cluster['connectors']

        storage_uuids = []
        compute_uuids = []
        if cluster and 'backends' in cluster:
            for b in cluster['backends']['uuids']:
                if b['storage'] != None:
                    storage_uuids.append(b['storage'])

                if b['compute'] != None:
                    for c in b['compute']:
                        compute_uuids.append(c)

        # For each UUID, collect the detailed service information. 
        json_reply['connectors'] = []            
        for uuid in connector_uuids:
            json_reply['connectors'].append(self._get_inspect_info(uuid))

        json_reply['storage'] = []
        for uuid in storage_uuids:
            json_reply['storage'].append(self._get_inspect_info(uuid))

        json_reply['compute'] = []
        for uuid in compute_uuids:
            json_reply['compute'].append(self._get_inspect_info(uuid))

        # Now append some snapshot info. 
        json_reply['snapshots'] = self._get_snapshot_info(stack_uuid)
           
        json_reply['status'] = 'stack'
        return json.dumps(json_reply, 
                          sort_keys=True,
                          indent=2,
                          separators=(',',':'))

    def _read_file_arg(self, file_name):
        """
        Helper method to read a file.
        """
        json_file = open(os.path.abspath(file_name), 'r')
        json_text = ''

        for line in json_file:
            json_text += line.strip()

        return json_text

    def _list_applications(self, directory):
        apps = set()
        content = os.listdir(directory)
        for c in content:
            if os.path.isdir(os.path.join(directory, c)):
                user_apps = self._list_applications(os.path.join(directory, c))
                for u in user_apps:
                    apps.add(c + '/' + u)
            else:
                apps.add(c)
        return apps

    def _query_application(self, directory):
        apps = {}
        app_files = self._list_applications(directory)
        for f in app_files:
            file_path = directory + '/' + f
            n, e = f.split(".")
            content = None
            if e == 'json':
                json_string = self._read_file_arg(file_path)
                content = json.loads(json_string)
            elif e == 'yaml' or e == 'yml':
                yaml_file = open(file_path, 'r')
                content = yaml.load(yaml_file)

            if content and 'metadata' in content:
                apps[n] = { 'author' : content['metadata']['author'],
                            'version': content['metadata']['version'],
                            'description': content['metadata']['description'][:21] + "..." }
            else:
                apps[n] = { 'author' : "Unknown",
                            'version': "Unknown",
                            'description': "Unknown" }
        return apps
    
    def query_applications(self):
        """
        Get list of installed applications.
        """
        builtin = self._query_application(ferry.install.DEFAULT_BUILTIN_APPS)
        installed = self._query_application(ferry.install.DEFAULT_FERRY_APPS)
        return json.dumps(dict(builtin.items() + installed.items()))
        
    def query_snapshots(self, constraints=None):
        """
        Query the available snapshots. 
        """
        json_reply = {}

        values = self.snapshot_collection.find()
        for v in values:
            c = self.cluster_collection.find_one( {'uuid':v['cluster_uuid']} )
            if c:
                time = v['snapshot_ts'].strftime("%m/%w/%Y (%I:%M %p)")
                json_reply[v['snapshot_uuid']] = { 'uuid' : v['snapshot_uuid'],
                                                   'base' : c['base'], 
                                                   'snapshot_ts' : time }
        return json.dumps(json_reply, 
                          sort_keys=True,
                          indent=2,
                          separators=(',',':'))
    
    def query_stacks(self, constraints=None):
        """
        Query the available stacks. 
        """
        json_reply = {}

        if constraints:
            values = self.cluster_collection.find(constraints)
        else:
            values = self.cluster_collection.find()

        for v in values:
            time = ''
            s = self.snapshot_collection.find_one( {'snapshot_uuid':v['snapshot_uuid']} )
            if s:
                time = v['ts'].strftime("%m/%w/%Y (%I:%M %p)")
            json_reply[v['uuid']] = { 'uuid' : v['uuid'],
                                      'base' : v['base'], 
                                      'ts' : time,
                                      'backends' : v['backends']['uuids'],
                                      'connectors': v['connectors'],
                                      'status' : v['status']}
        return json.dumps(json_reply, 
                          sort_keys=True,
                          indent=2,
                          separators=(',',':'))

    def query_deployed(self, conf=None):
        """
        Query the deployed applications. 
        """
        json_reply = {}

        cursors = self.deploy.find(conf=conf)
        for c in cursors:
            for v in c:
                time = v['ts'].strftime("%m/%w/%Y (%I:%M %p)")
                c = self.cluster_collection.find_one( {'uuid':v['cluster_uuid']} )
                
                json_reply[v['uuid']] = { 'uuid' : v['uuid'],
                                          'base' : c['base'], 
                                          'ts' : time,
                                          'backends' : c['backends']['uuids'],
                                          'connectors': c['connectors'],
                                          'status': 'deployed' }
        return json.dumps(json_reply, 
                          sort_keys=True,
                          indent=2,
                          separators=(',',':'))

    def _new_service_uuid(self):
        """
        Allocate new UUIDs. 
        """
        while True:
            longid = str(uuid.uuid4())
            shortid = 'se-' + longid.split('-')[0]
            services = self.service_collection.find_one( {'uuid' : shortid} )
            if not services:
                return shortid

    def _new_stack_uuid(self):
        while True:
            longid = str(uuid.uuid4())
            shortid = 'sa-' + longid.split('-')[0]
            services = self.cluster_collection.find_one( {'uuid' : shortid} )
            if not services:
                return shortid

    def _new_snapshot_uuid(self, cluster_uuid):
        while True:
            longid = str(uuid.uuid4())
            shortid = 'sn-' + longid.split('-')[0]
            services = self.snapshot_collection.find_one( {'snapshot_uuid' : shortid} )
            if not services:
                return shortid

    def is_snapshot(self, snapshot_uuid):
        """
        Determine if the supplied UUID is a valid snapshot. 
        """
        v = self.snapshot_collection.find_one( {'snapshot_uuid':snapshot_uuid} )
        if v:
            return True
        else:
            return False

    def _confirm_status(self, uuid, status):
        """
        Check if the application status
        """
        cluster = self.cluster_collection.find_one( {'uuid':uuid} )
        if cluster:
            return cluster['status'] == status
        return False
    def is_running(self, uuid, conf=None):
        return self._confirm_status(uuid, 'running')
    def is_stopped(self, uuid, conf=None):
        return self._confirm_status(uuid, 'stopped')
    def is_removed(self, uuid, conf=None):
        return self._confirm_status(uuid, 'removed')
    
    def is_deployed(self, uuid, conf=None):
        """
        Check if the UUID is of a deployed application. 
        """
        v = self.deploy.find( one=True, 
                              spec = {'uuid':uuid},
                              conf = conf )
        if v:
            return True
        else:
            return False

    def is_installed(self, app):
        """
        Indicate whether the application is installed. 
        """
        apps = self.query_applications()
        return app in apps

    def get_base_image(self, uuid):
        """
        Get the base image of this cluster. 
        """
        cluster = self.cluster_collection.find_one( {'uuid':uuid} )
        if cluster:
            return cluster['base']
        return None

    def _new_data_dir(self, service_uuid, storage_type, storage_id):
        """
        Create a new data directory
        """
        scratch_dir = ferry.install._get_ferry_scratch()

        # First check if this data directory already exists. If so,
        # go ahead and delete it (this will hopefully get rid of all xattr stuff)
        new_dir = scratch_dir + '/%s/data_%s' % (service_uuid, storage_type + '_' + str(storage_id))
        return self._create_dir(new_dir, replace=True)

    def _new_log_dir(self, service_uuid, storage_type, storage_id, replace = False):
        """
        Create a new log directory
        """
        scratch_dir = ferry.install._get_ferry_scratch()

        # First check if this data directory already exists. If so,
        # go ahead and delete it (this will hopefully get rid of all xattr stuff)
        new_dir = scratch_dir + '/%s/log_%s' % (service_uuid, storage_type + '_' + str(storage_id))
        return self._create_dir(new_dir, replace=replace)

    def _create_dir(self, new_dir, replace=False):
        # See if we need to delete an existing data dir.
        if os.path.exists(new_dir) and replace:
            logging.warning("deleting dir " + new_dir)
            shutil.rmtree(new_dir)

        try:
            # Now create the new directory and assign
            # the right permissions. 
            sh.mkdir('-p', new_dir)
        except:
            logging.warning(new_dir + " already exists")

        try:
            uid, gid = ferry.install._get_ferry_user()
            os.chown(new_dir, uid, gid)
            os.chmod(new_dir, 0774)
        except OSError as e:
            logging.warning("could not change permissions for " + new_dir)

        return os.path.abspath(new_dir)

    def _get_service_environment(self,
                                 service, 
                                 instance, 
                                 num_instances):
        container_dir = service.container_data_dir
        log_dir = service.container_log_dir
        host_name = service.new_host_name(instance)
        ports = service.get_necessary_ports(num_instances)
        exposed = service.get_exposed_ports(num_instances)
        
        # Add SSH port for management purposes. 
        exposed.append(DockerManager.SSH_PORT)

        return container_dir, log_dir, host_name, ports, exposed

    def _read_key_dir(self, private_key):
        """
        Read the directory containing the key we should use. 
        """
        return { '/service/keys' : os.path.dirname(private_key)  }

    def _read_public_key(self, private_key):
        s = private_key.split("/")
        p = os.path.splitext(s[len(s) - 1])[0]
        return p

    def _prepare_storage_environment(self, 
                                     service_uuid, 
                                     num_instances, 
                                     storage_type, 
                                     layers,
                                     key_name, 
                                     args = None,
                                     replace = False):
        """
        Prepare the environment for storage containers.
        """
        # Generate the data volumes. This basically defines which
        # directories on the host get mounted in the container. 
        ports = []
        exposed = []
        plan = {'localhost':{'containers':[]}}

        # Get the actual number of containers needed. 
        storage_service = self._get_service(storage_type)
        instances = storage_service.get_total_instances(num_instances, layers)

        # Now get the new container-specific information. 
        i = 0
        for t in instances:
            instance_type = self._get_instance_image(t)
            service = self._get_service(t)
            container_dir, log_dir, host_name, ports, exposed = self._get_service_environment(service, i, num_instances)
            new_log_dir = self._new_log_dir(service_uuid, t, i, replace=replace)
            dir_info = { new_log_dir : log_dir }

            # Only use a data directory mapping if we're not
            # using BTRFS (this is to get around the xattr problem). 
            if self.docker.get_fs_type() != "btrfs":
                new_data_dir = self._new_data_dir(service_uuid, t, i)
                dir_info[new_data_dir] = container_dir

            container_info = {'image':instance_type,
                              'type':t, 
                              'volumes':dir_info,
                              'volume_user':DEFAULT_FERRY_OWNER, 
                              'keydir': self._read_key_dir(key_name), 
                              'keyname': self._read_public_key(key_name), 
                              'privatekey': key_name, 
                              'ports':ports,
                              'exposed':exposed, 
                              'hostname':host_name,
                              'args':args}
            plan['localhost']['containers'].append(container_info)
            i += 1

        return plan

    def _prepare_compute_environment(self, 
                                     service_uuid, 
                                     num_instances, 
                                     compute_type,
                                     key_name, 
                                     layers, 
                                     args = None):
        """
        Prepare the environment for compute containers.
        """
        # Generate the data volumes. This basically defines which
        # directories on the host get mounted in the container. 
        ports = []
        exposed = []
        instance_type = ''
        plan = {'localhost':{'containers':[]}}

        # Get the actual number of containers needed. 
        compute_service = self._get_service(compute_type)
        instances = compute_service.get_total_instances(num_instances, layers)

        i = 0
        for t in instances:
            instance_type = self._get_instance_image(t)
            service = self._get_service(t)
            container_dir, log_dir, host_name, ports, exposed = self._get_service_environment(service, i, num_instances)
            new_log_dir = self._new_log_dir(service_uuid, t, i)
            dir_info = { new_log_dir : log_dir }
            container_info = {'image':instance_type,
                              'volumes':dir_info,
                              'volume_user':DEFAULT_FERRY_OWNER, 
                              'keydir': self._read_key_dir(key_name), 
                              'keyname': self._read_public_key(key_name), 
                              'privatekey': key_name, 
                              'type':t, 
                              'ports':ports,
                              'exposed':exposed, 
                              'hostname':host_name,
                              'args':args}
            plan['localhost']['containers'].append(container_info)
            i += 1
        return plan

    def _get_instance_image(self, instance_type, uuid=None):
        """
        Fetch the instance type. If the UUID is not associated with a running
        service, then just use the raw image. Otherwise, look for a snapshot image. 
        """
        s = instance_type.split('/')
        if len(s) == 1:
            instance_type = DEFAULT_DOCKER_REPO + '/' + instance_type
        return instance_type

    def _prepare_connector_environment(self, 
                                       service_uuid, 
                                       connector_type, 
                                       key_name, 
                                       instance_type=None,
                                       name=None, 
                                       ports=[],
                                       args=None):
        """
        Prepare the environment for connector containers.
        """
        plan = {'localhost':{'containers':[]}}

        # Determine the instance type from the connector type. 
        if not instance_type:
            instance_type = self._get_instance_image(connector_type)

        if not name:
            host_name = "client-%s" % str(service_uuid)
        else:
            host_name = name
        container_info = { 'image':instance_type,
                           'keydir': self._read_key_dir(key_name), 
                           'keyname': self._read_public_key(key_name), 
                           'privatekey': key_name, 
                           'volumes':{},
                           'type':connector_type, 
                           'ports':ports,
                           'exposed':[], 
                           'hostname':host_name,
                           'name':name, 
                           'args':args}

        plan['localhost']['containers'].append(container_info)
        return plan

    def _transfer_config(self, config_dirs):
        """
        Transfer the configuration to the containers. 
        """
        for c in config_dirs:
            container = c[0]
            from_dir = c[1]
            to_dir = c[2]
            logging.warning("transfer config %s -> %s" % (from_dir, to_dir))
            self.docker.copy([container], from_dir, to_dir)

    def _transfer_ip(self, private_key, ips):
        """
        Transfer the hostname/IP addresses to all the containers. 
        """
        with open('/tmp/instances', 'w+') as hosts_file:
            for ip in ips:
                hosts_file.write("%s %s\n" % (ip[0], ip[1]))
        for ip in ips:
            self.docker.copy_raw(private_key, ip[0], '/tmp/instances', '/service/sconf/instances')
            self.docker.cmd_raw(private_key, ip[0], '/service/sbin/startnode hosts')
        
    def _transfer_env_vars(self, containers, env_vars):
        """
        Transfer these environment variables to the containers.
        Since the user normally interacts with these containers by 
        logging in (via ssh), we must place these variables in the profile. 
        """
        for k in env_vars.keys():
            self.docker.cmd(containers, 
                            "echo export %s=%s >> /etc/profile" % (k, env_vars[k]))

    def _start_containers(self, plan):
        """
        Start the containers on the specified environment
        """
        return self.docker.alloc(plan['localhost']['containers']);

    def _restart_containers(self, containers):
        """
        Restart the stopped containers. 
        """
        return self.docker.restart(containers)

    def cancel_stack(self, backends, connectors):
        """
        The stack could not be instantiated correctly. Just get rid
        of these containers. 
        """
        for b in backends['uuids']:
            conf = self._get_service_configuration(b['storage'], detailed=True)
            if conf and 'containers' in conf:
                for c in conf['containers']:
                    self.docker.stop([c])
            for compute in b['compute']:
                conf = self._get_service_configuration(compute, detailed=True)
                if conf and 'containers' in conf:
                    for c in conf['containers']:
                        self.docker.stop([c])

        for b in connectors:
            s = self._get_service_configuration(b, detailed=True)
            if s and 'containers' in s:
                for c in s['containers']:
                    self.docker.stop([c])

    def register_stack(self, backends, connectors, base, key=None, uuid=None):
        """
        Register the set of services under a single cluster identifier. 
        """
        if not uuid:
            cluster_uuid = self._new_stack_uuid()
        else:
            cluster_uuid = uuid

        ts = datetime.datetime.now()
        cluster = { 'uuid' : cluster_uuid,
                    'backends':backends,
                    'connectors':connectors,
                    'num_snapshots':0,
                    'snapshot_ts':'', 
                    'snapshot_uuid':base, 
                    'base':base,
                    'status': 'running',
                    'ts':ts }

        if not uuid:
            cluster['key'] = key
            self.cluster_collection.insert( cluster )
        else:
            self._update_stack(uuid, cluster)

        return cluster_uuid

    def _update_stack(self, cluster_uuid, state):
        """
        Helper method to update a cluster's status. 
        """
        self.cluster_collection.update( {'uuid' : cluster_uuid},
                                        {'$set' : state} )

    def _get_cluster_instances(self, cluster_uuid):
        all_connectors = []
        all_storage = []
        all_compute = []
        cluster = self.cluster_collection.find_one( {'uuid':cluster_uuid} )
        if cluster:
            backends = cluster['backends']
            connector_uuids = cluster['connectors']
            for c in connector_uuids:
                connectors = {'uuid' : c,
                              'instances' : []}
                connector_info = self._get_service_configuration(c, detailed=True)
                if connector_info:
                    for connector in connector_info['containers']:
                        connector_instance = DockerInstance(connector)
                        connectors['instances'].append(connector_instance)
                        connectors['type'] = connector_instance.service_type
                    all_connectors.append(connectors)

            # Collect all the UUIDs of the backend containers. 
            # and stop them. The backend is considered ephemeral!
            for b in backends['uuids']:
                if b['storage'] != None:
                    storage = {'uuid' : b['storage'],
                               'instances' : []}
                    storage_info = self._get_service_configuration(b['storage'], detailed=True)
                    if storage_info:
                        for s in storage_info['containers']:
                            storage_instance = DockerInstance(s)
                            storage['instances'].append(storage_instance)
                            storage['type'] = storage_instance.service_type
                        all_storage.append(storage)

                if b['compute'] != None:
                    for c in b['compute']:
                        compute = {'uuid' : c,
                                   'instances' : []}
                        compute_info = self._get_service_configuration(c, detailed=True)
                        if compute_info:
                            for container in compute_info['containers']:
                                compute_instance = DockerInstance(container)
                                compute['instances'].append(compute_instance)
                                compute['type'] = compute_instance.service_type
                            all_compute.append(compute)
            return all_connectors, all_compute, all_storage

    def _stop_stack(self, cluster_uuid):
        """
        Stop a running cluster.
        """
        # First stop all the running services. 
        connectors, compute, storage = self._get_cluster_instances(cluster_uuid)
        for c in connectors:
            self._stop_service(c['uuid'], c['instances'], c['type'])
        for c in compute:
            self._stop_service(c['uuid'], c['instances'], c['type'])
        for c in storage:
            self._stop_service(c['uuid'], c['instances'], c['type'])

        # Then actually stop the containers. 
        for c in connectors:
            self.docker.halt(c['instances'])
        for c in compute:
            self.docker.halt(c['instances'])
        for c in storage:
            self.docker.halt(c['instances'])

    def _purge_stack(self, cluster_uuid):
        volumes = []
        connectors, compute, storage = self._get_cluster_instances(cluster_uuid)
        for c in connectors:
            self.docker.remove(c['instances'])
        for c in compute:
            self.docker.remove(c['instances'])
        for s in storage:
            for i in s['instances']:
                for v in i.volumes.keys():
                    volumes.append(v)
            self.docker.remove(s['instances'])

        # Now remove the data directories. 
        for v in volumes:
            shutil.rmtree(v)
    
    def _snapshot_stack(self, cluster_uuid):
        """
        Take a snapshot of an existing stack. 
        """
        cluster = self.cluster_collection.find_one( {'uuid':cluster_uuid} )
        if cluster:
            # We need to deserialize the docker containers from the cluster/service
            # description so that the snapshot code has access to certain pieces
            # of information (service type, etc.). 
            connectors = []
            connector_uuids = cluster['connectors']
            for c in connector_uuids:
                connector_info = self._get_service_configuration(c, detailed=True)
                if connector_info:
                    connectors.append(DockerInstance(connector_info['containers'][0]))
            cs_snapshots = self.docker.snapshot(connectors, 
                                                cluster_uuid, 
                                                cluster['num_snapshots'])

            # Register the snapshot in the snapshot state. 
            snapshot_uuid = self._new_snapshot_uuid(cluster_uuid)
            snapshot_ts = datetime.datetime.now()
            snapshot_state = { 'snapshot_ts' : snapshot_ts, 
                               'snapshot_uuid' : snapshot_uuid,
                               'snapshot_cs' : cs_snapshots,
                               'cluster_uuid' : cluster_uuid}
            self.snapshot_collection.insert( snapshot_state )

            # Now update the cluster state. 
            cluster_state = { 'num_snapshots' : cluster['num_snapshots'] + 1,
                              'snapshot_uuid' : snapshot_uuid }
            self.cluster_collection.update( {'uuid':cluster_uuid}, 
                                             {"$set": cluster_state } )

    def start_service(self, uuid, containers):
        """
        Start the service.
        """
        service_info = self._get_service_configuration(uuid, detailed=True)
        return self._start_service(uuid, containers, service_info)

    def allocate_compute(self,
                         compute_type, 
                         key_name, 
                         storage_uuid,
                         args, 
                         num_instances=1,
                         layers=[]):
        """
        Allocate a new compute cluster.
        """
        # Allocate a UUID.
        service_uuid = self._new_service_uuid()
        service = self._get_service(compute_type)

        # Generate the data volumes. This basically defines which
        # directories on the host get mounted in the container. 
        plan = self._prepare_compute_environment(service_uuid = service_uuid, 
                                                 num_instances = num_instances, 
                                                 compute_type = compute_type, 
                                                 key_name = key_name,
                                                 layers = layers, 
                                                 args = args)

        # Get the entry point for the storage layer. 
        storage_entry = self._get_service_configuration(storage_uuid)

        # Allocate all the containers. 
        containers = self._start_containers(plan)

        # Generate a configuration dir.
        config_dirs, entry_point = self.config.generate_compute_configuration(service_uuid, 
                                                                              containers, 
                                                                              service, 
                                                                              args, 
                                                                              [storage_entry])

        # Now copy over the configuration.
        self._transfer_config(config_dirs)

        # Update the service configuration. 
        container_info = self._serialize_containers(containers)
        service = {'uuid':service_uuid, 
                   'containers':container_info, 
                   'class':'compute',
                   'type':compute_type,
                   'entry':entry_point,
                   'storage':storage_uuid, 
                   'status':'running'}
        self._update_service_configuration(service_uuid, service)
        return service_uuid, containers
        
    def _start_service(self,
                       uuid,
                       containers,
                       service_info): 
        if service_info['class'] != 'connector':
            service = self._get_service(service_info['type'])
            return service.start_service(containers, service_info['entry'], self.docker)
        else:
            storage_entry = service_info['storage']
            compute_entry = service_info['compute']
            services, backend_names = self._get_client_services(storage_entry, compute_entry)
            all_output = {}
            for service in services:
                output = service.start_service(containers, service_info['entry'], self.docker)
                if output:
                    all_output = dict(all_output.items() + output.items())
            return all_output

    def _restart_service(self,
                         uuid,
                         containers,
                         service_type):
        service_info = self._get_service_configuration(uuid, detailed=True)
        entry_point = service_info['entry']        
        if service_info['class'] != 'connector':
            service = self._get_service(service_type)
            return service.restart_service(containers, entry_point, self.docker)
        else:
            all_output = {}
            for backend in service_info['backends']:
                if 'client' in self.service[backend]:
                    service = self.service[backend]['client']
                    output = service.restart_service(containers, entry_point, self.docker)
                    if output:
                        all_output = dict(all_output.items() + output.items())
            return all_output

    def _stop_service(self,
                      uuid,
                      containers,
                      service_type):
        service_info = self._get_service_configuration(uuid, detailed=True)
        entry_point = service_info['entry']        
        if service_info['class'] != 'connector':
            service = self._get_service(service_type)
            service.stop_service(containers, entry_point, self.docker)
        else:
            for backend in service_info['backends']:
                if 'client' in self.service[backend]:
                    service = self.service[backend]['client']
                    service.stop_service(containers, entry_point, self.docker)
        
    def restart_containers(self, service_uuid, containers):
        """
        Restart an stopped storage cluster. This does not
        re-initialize the container. It just starts an empty
        container. 
        """
        self._restart_containers(containers)
        container_info = self._serialize_containers(containers)

        service = {'uuid':service_uuid, 
                   'containers':container_info, 
                   'status':'running'}
        self._update_service_configuration(service_uuid, service)
                        
    def allocate_storage(self, 
                         storage_type, 
                         key_name, 
                         num_instances=1,
                         layers=[], 
                         args=None,
                         replace=False):
        """
        Create a storage cluster and start a particular
        personality on that cluster. 
        """
        # Allocate a UUID.
        service_uuid = self._new_service_uuid()
        service = self._get_service(storage_type)

        # Generate the data volumes. This basically defines which
        # directories on the host get mounted in the container. 
        plan = self._prepare_storage_environment(service_uuid = service_uuid, 
                                                 num_instances = num_instances, 
                                                 storage_type = storage_type, 
                                                 layers = layers, 
                                                 key_name = key_name, 
                                                 args = args, 
                                                 replace = replace)

        # Allocate all the containers. 
        containers = self._start_containers(plan)

        # Generate a configuration dir.
        config_dirs, entry_point = self.config.generate_storage_configuration(service_uuid, 
                                                                              containers, 
                                                                              service, 
                                                                              args)

        # Now copy over the configuration.
        self._transfer_config(config_dirs)

        container_info = self._serialize_containers(containers)
        service = {'uuid':service_uuid, 
                   'containers':container_info, 
                   'class':'storage',
                   'type':storage_type,
                   'entry':entry_point,
                   'status':'running'}
        self._update_service_configuration(service_uuid, service)
        return service_uuid, containers

    def _get_default_conf(self):        
        """
        Get the default deployment conf file. 
        """
        return FERRY_HOME + '/data/conf/deploy_default.json'

    def _get_deploy_params(self, mode, conf):
        """
        Get the deployment configuration parameters. 
        """
        # First just find and read the configuration file. 
        if conf == 'default':
            conf = self._get_default_conf()

        # Read the configuration file.
        if os.path.exists(conf):
            with open(conf, 'r') as f: 
                j = json.loads(f.read())

                # Now find the right configuration.
                if mode in j:
                    j[mode]['_mode'] = mode
                    return j[mode]
        return None

    def deploy_stack(self, cluster_uuid, params=None):
        """
        Deploy an existing stack. 
        """
        containers = []
        cluster = self.cluster_collection.find_one( {'uuid':cluster_uuid} )
        if cluster:
            connector_uuids = cluster['connectors']
            for c in connector_uuids:
                connector_info = self._get_service_configuration(c, detailed=True)
                if connector_info:
                    containers.append(DockerInstance(connector_info['containers'][0]))

            self.deploy.deploy(cluster_uuid, containers, params)

            # Check if we need to try starting the
            # stack right away. 
            if params and 'start-on-create' in params:
                return True
        return False

    def manage_stack(self,
                     stack_uuid,
                     private_key, 
                     action):
        """
        Manage the stack.
        """
        status = 'running'
        if(action == 'snapshot'):        
            # The user wants to take a snapshot of the current stack. This
            # doesn't actually stop anything.
            self._snapshot_stack(stack_uuid)
        elif(action == 'stop'):
            if self.is_running(stack_uuid):
                self._stop_stack(stack_uuid)
                status = 'stopped'
                service_status = { 'uuid':stack_uuid, 'status':status }
                self._update_stack(stack_uuid, service_status)
        elif(action == 'rm'):
            # First need to check if the stack is stopped.
            if self.is_stopped(stack_uuid):
                self._purge_stack(stack_uuid)
                status = 'removed'
                service_status = { 'uuid':stack_uuid, 'status':status }
                self._update_stack(stack_uuid, service_status)
            else:
                return { 'uuid' : stack_uuid,
                         'status' : False,
                         'msg': 'Stack is running. Please stop first' }

        return { 'uuid' : stack_uuid,
                 'status' : True,
                 'msg': status }

    def fetch_stopped_backend(self, uuid):
        """
        Lookup the stopped backend info. 
        """
        cluster = self.cluster_collection.find_one( {'uuid':uuid} )
        if cluster:
            key = cluster['key']
            backends = []
            for i, uuid in enumerate(cluster['backends']['uuids']):
                storage_uuid = uuid['storage']
                storage_conf = self._get_service_configuration(storage_uuid, 
                                                               detailed=True)

                compute_confs = []
                if 'compute' in uuid:
                    for c in uuid['compute']:
                        compute_conf = self._get_service_configuration(c, detailed=True)
                        compute_confs.append(compute_conf)
                
                backends.append( {'storage' : storage_conf,
                                  'compute' : compute_confs} )
            return backends, key
        else:
            return None, None
            

    def fetch_snapshot_backend(self, snapshot_uuid):
        """
        Lookup the snapshot backend info. 
        """
        snapshot = self.cluster_collection.find_one( {'snapshot_uuid':snapshot_uuid} )
        if snapshot:
            return snapshot['backends']['backend']

    def fetch_deployed_backend(self, app_uuid, conf=None):
        """
        Lookup the deployed backend info. 
        """
        app = self.deploy.find( one = True,
                                spec = { 'uuid' : app_uuid },
                                conf = conf )
        stack = self.cluster_collection.find_one( {'uuid':app['cluster_uuid'] } )
        if stack:
            return stack['backends']['backend']

    def allocate_stopped_connectors(self, 
                                     app_uuid, 
                                     backend_info,
                                     conf = None):
        """
        Lookup the deployed application connector info and instantiate. 
        """
        connector_info = []
        connector_plan = []
        cluster = self.cluster_collection.find_one( {'uuid':app_uuid} )
        if cluster:
            for cuid in cluster['connectors']:
                # Retrieve the actual service information. This will
                # contain the container ID. 
                s = self._get_service_configuration(cuid, detailed=True)
                if s and 'containers' in s:
                    containers = [DockerInstance(j) for j in s['containers']]
                    connector_plan.append( { 'uuid' : cuid,
                                             'containers' : containers,
                                             'type' : s['type'], 
                                             'backend' : backend_info, 
                                             'start' : 'restart' } )
                    connector_info.append(cuid)
                    self.restart_containers(cuid, containers)
        return connector_info, connector_plan

    def allocate_deployed_connectors(self, 
                                     app_uuid, 
                                     key_name, 
                                     backend_info,
                                     conf = None):
        """
        Lookup the deployed application connector info and instantiate. 
        """
        connector_info = []
        connector_plan = []
        app = self.deploy.find( one = True,
                                spec = { 'uuid' : app_uuid },
                                conf = conf)
        if app:
            for c in app['connectors']:
                uuid, containers = self.allocate_connector(connector_type = c['type'],
                                                           key_name = key_name,  
                                                           backend = backend_info,
                                                           name = c['name'], 
                                                           args = c['args'],
                                                           ports = c['ports'].keys(),
                                                           image = c['image'])
                connector_info.append(uuid)
                connector_plan.append( { 'uuid' : uuid,
                                         'containers' : containers,
                                         'type' : c['type'], 
                                         'start' : 'start' } )
        return connector_info, connector_plan
                
    def allocate_snapshot_connectors(self, 
                                     snapshot_uuid, 
                                     key_name, 
                                     backend_info):
        """
        Lookup the snapshot connector info and instantiate. 
        """
        connector_info = []
        connector_plan = []
        snapshot = self.snapshot_collection.find_one( {'snapshot_uuid':snapshot_uuid} )
        if snapshot:
            for s in snapshot['snapshot_cs']:
                uuid, containers = self.allocate_connector(connector_type = s['type'],
                                                           key_name = key_name, 
                                                           backend = backend_info,
                                                           name = s['name'], 
                                                           args = s['args'],
                                                           ports = s['ports'].keys(),
                                                           image = s['image'])
                connector_info.append(uuid)
                connector_plan.append( { 'uuid' : uuid,
                                         'containers' : containers,
                                         'type' : s['type'], 
                                         'start' : 'start' } )
        return connector_info, connector_plan
                

    def _restart_connectors(self,
                            service_uuid, 
                            connectors, 
                            backend=None):
        """
        Restart a stopped connector with an existing storage service. 
        """
        # Initialize the connector and connect to the storage. 
        storage_entry = []
        compute_entry = []
        for b in backend:
            if b['storage']:
                storage_entry.append(self._get_service_configuration(b['storage']))
            if b['compute']:
                for c in b['compute']:
                    compute_entry.append(self._get_service_configuration(c))

        # Generate the environment variables that will be 
        # injected into the containers. 
        env_vars = self.config.generate_env_vars(storage_entry,
                                                 compute_entry)
        services, backend_names = self._get_client_services(storage_entry, compute_entry)
        entry_points = {}
        for service in services:
            config_dirs, entry_point = self.config.generate_connector_configuration(service_uuid, 
                                                                                    connectors, 
                                                                                    service,
                                                                                    storage_entry,
                                                                                    compute_entry,
                                                                                    connectors[0].args)
            # Merge all the entry points. 
            entry_points = dict(entry_point.items() + entry_points.items())

            # Now copy over the configuration.
            self._transfer_config(config_dirs)
            self._transfer_env_vars(connectors, env_vars)

        # Start the containers and update the state. 
        self._restart_service(service_uuid, connectors, connectors[0].service_type)
        container_info = self._serialize_containers(connectors)
        service = {'uuid':service_uuid, 
                   'containers':container_info, 
                   'backends':backend_names, 
                   'entry':entry_points,
                   'status':'running'}
        self._update_service_configuration(service_uuid, service)
                
    def allocate_connector(self,
                           connector_type, 
                           key_name, 
                           backend=None,
                           name=None, 
                           args=None,
                           ports=None, 
                           image=None):
        """
        Allocate a new connector and associate with an existing storage service. 
        """
        # Initialize the connector and connect to the storage. 
        storage_entry = []
        compute_entry = []
        if backend:
            for b in backend:
                if b['storage']:
                    storage_entry.append(self._get_service_configuration(b['storage']))
                if b['compute']:
                    for c in b['compute']:
                        compute_entry.append(self._get_service_configuration(c))

        # Generate the environment variables that will be 
        # injected into the containers. 
        env_vars = self.config.generate_env_vars(storage_entry,
                                                 compute_entry)

        # Allocate a UUID.
        service_uuid = self._new_service_uuid()
        plan = self._prepare_connector_environment(service_uuid = service_uuid, 
                                                   connector_type = connector_type, 
                                                   key_name = key_name, 
                                                   instance_type = image,
                                                   name = name,
                                                   ports = ports, 
                                                   args = args)
        containers = self._start_containers(plan)

        # Now generate the configuration files that will be
        # transferred to the containers. 
        entry_points = {}
        services, backend_names = self._get_client_services(storage_entry, compute_entry)
        for service in services:
            config_dirs, entry_point = self.config.generate_connector_configuration(service_uuid, 
                                                                                    containers, 
                                                                                    service,
                                                                                    storage_entry,
                                                                                    compute_entry,
                                                                                    args)
            # Merge all the entry points. 
            entry_points = dict(entry_point.items() + entry_points.items())

            # Now copy over the configuration.
            self._transfer_config(config_dirs)
            self._transfer_env_vars(containers, env_vars)

        # Update the connector state. 
        container_info = self._serialize_containers(containers)
        service_info = {'uuid':service_uuid, 
                        'containers':container_info, 
                        'backends':backend_names, 
                        'storage': storage_entry, 
                        'compute': compute_entry, 
                        'class':'connector',
                        'type':connector_type,
                        'entry':entry_points,
                        'uniq': name, 
                        'status':'running'}
        self._update_service_configuration(service_uuid, service_info)
        return service_uuid, containers

    def push_image(self, image, registry=None):
        """
        Push a local image to a remote registry.         
        """
        return self.docker.push(image, registry)

    def pull_image(self, image):
        """
        Pull a remote image to the local registry. 
        """
        return self.docker.pull(image)

    def login_registry(self):
        """
        Login to a remote registry.
        """
        return self.docker.login()

    def version(self):
        """
        Fetch the current docker version.
        """
        return self.docker.version()
