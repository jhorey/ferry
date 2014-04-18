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
from pymongo import MongoClient
from sets import Set
from ferry.install import *
from ferry.docker.docker        import DockerInstance
from ferry.docker.fabric        import DockerFabric
from ferry.docker.configfactory import ConfigFactory
from ferry.docker.deploy        import DeployEngine

class DockerManager(object):
    SSH_PORT = 22

    def __init__(self):
        # Generate configuration.
        self.config = ConfigFactory()

        # Service mappings
        self.service = {
            'openmpi' : { 
                'server' : self.config.mpi,
                'client' : self.config.mpi_client },
            'yarn': { 
                'server' : self.config.yarn,
                'client' : self.config.hadoop_client },
            'gluster': { 
                'server' : self.config.gluster },
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
                'client' : self.config.hadoop_client}
            }

        # Docker tools
        self.docker = DockerFabric()
        self.deploy = DeployEngine(self.docker)

        # Initialize the state. 
        self._init_state_db()
        self._clean_state_db()

    """
    Contact the state database. 
    """
    def _init_state_db(self):
        self.mongo = MongoClient(os.environ['MONGODB'], 27017, connectTimeoutMS=6000)

        self.cluster_collection = self.mongo['state']['clusters']
        self.service_collection = self.mongo['state']['services']
        self.snapshot_collection = self.mongo['state']['snapshots']

    """
    Remove all the services that are "terminated". 
    """
    def _clean_state_db(self):
        self.cluster_collection.remove( {'status':'removed'} )

    def _serialize_containers(self, containers):
        info = []
        for c in containers:
            info.append(c.json())
        return info

    """
    Update the service configuration. 
    """
    def _update_service_configuration(self, service_uuid, service_info):
        service = self.service_collection.find_one( {'uuid':service_uuid} )
        if not service:
            self.service_collection.insert( service_info )
        else:
            self.service_collection.update( {'uuid' : service_uuid},
                                            {'$set': service_info} )
    """
    Get the storage information. 
    """
    def _get_service_configuration(self, service_uuid, detailed=False):
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
            return self.service[service_type]['server']
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
                    client_services.add(self.service[storage['type']]['client'])
                service_names.append(storage['type'])
        for compute in compute_entry:
            if compute['type'] in self.service:
                if 'client' in self.service[compute['type']]:
                    client_services.add(self.service[compute['type']]['client'])
                service_names.append(compute['type'])
        return client_services, service_names

    """
    Helper method to copy directories. shutil fails if the 
    destination already exists. 
    """
    def _copytree(src, dst):
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

    """
    Inspect a deployed stack. 
    """
    def inspect_deployed(self, uuid, registry):
        json_reply = {}

        # Need to inspect the registry to make sure
        # that all the images are available. 

        return json.dumps(json_reply, 
                          sort_keys=True,
                          indent=2,
                          separators=(',',':'))

    """
    Inspect a running stack. 
    """
    def inspect_stack(self, stack_uuid):
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

        return json.dumps(json_reply, 
                          sort_keys=True,
                          indent=2,
                          separators=(',',':'))

    """
    Query the available snapshots. 
    """
    def query_snapshots(self, constraints=None):
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
    
    """
    Query the available stacks. 
    """
    def query_stacks(self, constraints=None):
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

    """
    Query the deployed applications. 
    """
    def query_deployed(self, conf=None):
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

    """
    Allocate new UUIDs. 
    """
    def _new_service_uuid(self):
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

    """
    Determine if the supplied UUID is a valid snapshot. 
    """
    def is_snapshot(self, snapshot_uuid):
        v = self.snapshot_collection.find_one( {'snapshot_uuid':snapshot_uuid} )
        if v:
            return True
        else:
            return False

    """
    Check if the application status
    """
    def _confirm_status(self, uuid, status):
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

    """
    Check if the UUID is of a deployed application. 
    """
    def is_deployed(self, uuid, conf=None):
        v = self.deploy.find( one=True, 
                              spec = {'uuid':uuid},
                              conf = conf )
        if v:
            return True
        else:
            return False

    """
    Get the base image of this cluster. 
    """
    def get_base_image(self, uuid):
        cluster = self.cluster_collection.find_one( {'uuid':uuid} )
        if cluster:
            return cluster['base']
        return None

    """
    Create a new data directory
    """
    def _new_data_dir(self, service_uuid, storage_type, storage_id):
        # Check the location of the scratch directory. If not defined
        # use the current directory
        if 'FERRY_SCRATCH' in os.environ:
            scratch_dir = os.environ['FERRY_SCRATCH'] + '/'
        else:
            scratch_dir = ''

        # First check if this data directory already exists. If so,
        # go ahead and delete it (this will hopefully get rid of all xattr stuff)
        new_dir = scratch_dir + 'tmp/%s/data_%s' % (service_uuid, storage_type + '_' + str(storage_id))
        return self._create_dir(new_dir, replace=True)

    """
    Create a new log directory
    """
    def _new_log_dir(self, service_uuid, storage_type, storage_id, replace = False):
        # Check the location of the scratch directory. If not defined
        # use the current directory
        if 'FERRY_SCRATCH' in os.environ:
            scratch_dir = os.environ['FERRY_SCRATCH'] + '/'
        else:
            scratch_dir = ''

        # First check if this data directory already exists. If so,
        # go ahead and delete it (this will hopefully get rid of all xattr stuff)
        new_dir = scratch_dir + 'tmp/%s/log_%s' % (service_uuid, storage_type + '_' + str(storage_id))
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

    """
    Read the directory containing the key we should use. 
    """
    def _read_key_dir(self):
        f = open(ferry.install.DEFAULT_DOCKER_KEY, 'r')
        k = f.read().strip().split("://")
        # return { k[1] : '/service/keys' }
        return { '/service/keys' : k[1]  }

    """
    Prepare the environment for storage containers.
    """
    def _prepare_storage_environment(self, 
                                     service_uuid, 
                                     num_instances, 
                                     storage_type, 
                                     layers,
                                     args = None,
                                     replace = False):
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
                              'keys': self._read_key_dir(), 
                              'ports':ports,
                              'exposed':exposed, 
                              'hostname':host_name,
                              'args':args}
            plan['localhost']['containers'].append(container_info)
            i += 1

        return plan

    """
    Prepare the environment for compute containers.
    """
    def _prepare_compute_environment(self, 
                                     service_uuid, 
                                     num_instances, 
                                     compute_type,
                                     layers, 
                                     args = None):
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
                              'keys': self._read_key_dir(), 
                              'type':t, 
                              'ports':ports,
                              'exposed':exposed, 
                              'hostname':host_name,
                              'args':args}
            plan['localhost']['containers'].append(container_info)
            i += 1
        return plan

    """
    Fetch the instance type. If the UUID is not associated with a running
    service, then just use the raw image. Otherwise, look for a snapshot image. 
    """
    def _get_instance_image(self, instance_type, uuid=None):
        s = instance_type.split('/')
        if len(s) == 1:
            instance_type = DEFAULT_DOCKER_REPO + '/' + instance_type
        return instance_type

    """
    Prepare the environment for connector containers.
    """
    def _prepare_connector_environment(self, 
                                       service_uuid, 
                                       connector_type, 
                                       instance_type=None,
                                       name=None, 
                                       ports=[],
                                       args=None):
        plan = {'localhost':{'containers':[]}}

        # Determine the instance type from the connector type. 
        if not instance_type:
            instance_type = self._get_instance_image(connector_type)

        if not name:
            host_name = "client-%s" % str(service_uuid)
        else:
            host_name = name
        container_info = { 'image':instance_type,
                           'keys': self._read_key_dir(), 
                           'volumes':{},
                           'type':connector_type, 
                           'ports':ports,
                           'exposed':[], 
                           'hostname':host_name,
                           'name':name, 
                           'args':args}

        plan['localhost']['containers'].append(container_info)
        return plan

    """
    Transfer the configuration to the containers. 
    """
    def _transfer_config(self, config_dirs):
        for c in config_dirs:
            container = c[0]
            from_dir = c[1]
            to_dir = c[2]
            logging.warning("transfer config %s -> %s" % (from_dir, to_dir))
            self.docker.copy([container], from_dir, to_dir)

    """
    Transfer these environment variables to the containers.
    Since the user normally interacts with these containers by 
    logging in (via ssh), we must place these variables in the profile. 
    """
    def _transfer_env_vars(self, containers, env_vars):
        for k in env_vars.keys():
            self.docker.cmd(containers, 
                            "echo export %s=%s >> /etc/profile" % (k, env_vars[k]))
    """
    Start the containers on the specified environment
    """
    def _start_containers(self, plan):
        return self.docker.alloc(plan['localhost']['containers']);

    """
    Restart the stopped containers. 
    """
    def _restart_containers(self, container_info):
        return self.docker.restart(container_info)

    """
    Register the set of services under a single cluster identifier. 
    """
    def register_stack(self, backends, connectors, base, uuid=None):
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
            self.cluster_collection.insert( cluster )
        else:
            self._update_stack(uuid, cluster)

        return cluster_uuid

    """
    Helper method to update a cluster's status. 
    """
    def _update_stack(self, cluster_uuid, state):
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

    """
    Stop a running cluster.
    """
    def _stop_stack(self, cluster_uuid):
        connectors, compute, storage = self._get_cluster_instances(cluster_uuid)
        for c in connectors:
            self._stop_service(c['uuid'], c['instances'], c['type'])
        for c in compute:
            self._stop_service(c['uuid'], c['instances'], c['type'])
        for s in storage:
            self._stop_service(s['uuid'], s['instances'], s['type'])

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
    
    """
    Take a snapshot of an existing stack. 
    """
    def _snapshot_stack(self, cluster_uuid):
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

    """
    Restart an stopped compute cluster.
    """
    def restart_compute(self, service_uuid, container_info, compute_type):
        containers = self._restart_containers(container_info)
        container_info = self._serialize_containers(containers)

        service = {'uuid':service_uuid, 
                   'containers':container_info, 
                   'status':'running'}
        self._update_service_configuration(service_uuid, service)

        self._restart_service(service_uuid, containers, compute_type)
        return service_uuid        

    """
    Allocate a new compute cluster.
    """
    def allocate_compute(self,
                         compute_type, 
                         storage_uuid,
                         args, 
                         num_instances=1,
                         layers=[]):
        # Allocate a UUID.
        service_uuid = self._new_service_uuid()
        service = self._get_service(compute_type)

        # Generate the data volumes. This basically defines which
        # directories on the host get mounted in the container. 
        plan = self._prepare_compute_environment(service_uuid, num_instances, compute_type, layers, args)

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
        for k in self._read_key_dir().keys():
            keydir = k

        container_info = self._serialize_containers(containers)
        service = {'uuid':service_uuid, 
                   'containers':container_info, 
                   'class':'compute',
                   'keys': keydir, 
                   'type':compute_type,
                   'entry':entry_point,
                   'storage':storage_uuid, 
                   'status':'running'}
        self._update_service_configuration(service_uuid, service)

        # After the docker instance start, we need to start the
        # actual storage service (gluster, etc.). 
        self._start_service(service_uuid, containers, compute_type, entry_point)
        return service_uuid
        
    def _start_service(self,
                       uuid,
                       containers,
                       service_type,
                       entry_point, 
                       service=None):
        if not service:
            service = self._get_service(service_type)
        service.start_service(containers, entry_point, self.docker)

    def _restart_service(self,
                         uuid,
                         containers,
                         service_type):
        service_info = self._get_service_configuration(uuid, detailed=True)
        entry_point = service_info['entry']        
        if service_info['class'] != 'connector':
            service = self._get_service(service_type)
            service.restart_service(containers, entry_point, self.docker)
        else:
            for backend in service_info['backends']:
                if 'client' in self.service[backend]:
                    service = self.service[backend]['client']
                    service.restart_service(containers, entry_point, self.docker)

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
    """
    Restart an stopped storage cluster.
    """
    def restart_storage(self, service_uuid, container_info, storage_type):
        containers = self._restart_containers(container_info)
        container_info = self._serialize_containers(containers)

        service = {'uuid':service_uuid, 
                   'containers':container_info, 
                   'status':'running'}
        self._update_service_configuration(service_uuid, service)

        self._restart_service(service_uuid, containers, storage_type)
        return service_uuid        
                        
    """
    Create a storage cluster and start a particular
    personality on that cluster. 
    """
    def allocate_storage(self, 
                         storage_type, 
                         num_instances=1,
                         layers=[], 
                         args=None,
                         replace=False):
        # Allocate a UUID.
        service_uuid = self._new_service_uuid()
        service = self._get_service(storage_type)

        # Generate the data volumes. This basically defines which
        # directories on the host get mounted in the container. 
        plan = self._prepare_storage_environment(service_uuid, num_instances, storage_type, layers, args, replace)

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

        # After the docker instance start, we need to start the
        # actual storage service (gluster, etc.). 
        self._start_service(service_uuid, containers, storage_type, entry_point)
        return service_uuid

    """
    Get the default deployment conf file. 
    """
    def _get_default_conf(self):        
        return FERRY_HOME + '/data/conf/deploy_default.json'

    """
    Get the deployment configuration parameters. 
    """
    def _get_deploy_params(self, mode, conf):
        # First just find and read the configuration file. 
        if conf == 'default':
            conf = self._get_default_conf()

        # Read the configuration file.
        if os.path.exists(conf):
            f = open(conf, 'r').read()
            j = json.loads(f)

            # Now find the right configuration.
            if mode in j:
                j[mode]['_mode'] = mode
                return j[mode]

        return None

    """
    Deploy an existing stack. 
    """
    def deploy_stack(self, cluster_uuid, params=None):
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
    """
    Manage the stack.
    """
    def manage_stack(self,
                     stack_uuid,
                     action):
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

    """
    Lookup the stopped backend info. 
    """
    def fetch_stopped_backend(self, uuid):
        cluster = self.cluster_collection.find_one( {'uuid':uuid} )
        if cluster:
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
            return backends
            

    """
    Lookup the snapshot backend info. 
    """
    def fetch_snapshot_backend(self, snapshot_uuid):
        snapshot = self.cluster_collection.find_one( {'snapshot_uuid':snapshot_uuid} )
        if snapshot:
            return snapshot['backends']['backend']

    """
    Lookup the deployed backend info. 
    """
    def fetch_deployed_backend(self, app_uuid, conf=None):
        app = self.deploy.find( one = True,
                                spec = { 'uuid' : app_uuid },
                                conf = conf )
        stack = self.cluster_collection.find_one( {'uuid':app['cluster_uuid'] } )
        if stack:
            return stack['backends']['backend']

    """
    Lookup the deployed application connector info and instantiate. 
    """
    def allocate_stopped_connectors(self, 
                                     app_uuid, 
                                     backend_info,
                                     conf = None):
        connector_info = []
        cluster = self.cluster_collection.find_one( {'uuid':app_uuid} )
        if cluster:
            for cuid in cluster['connectors']:
                # Retrieve the actual service information. This will
                # contain the container ID. 
                s = self._get_service_configuration(cuid, detailed=True)
                if s and 'containers' in s:
                    connector_info.append(self._restart_connectors(cuid, s['containers'], backend_info))
        return connector_info

    """
    Lookup the deployed application connector info and instantiate. 
    """
    def allocate_deployed_connectors(self, 
                                     app_uuid, 
                                     backend_info,
                                     conf = None):
        connector_info = []
        app = self.deploy.find( one = True,
                                spec = { 'uuid' : app_uuid },
                                conf = conf)
        if app:
            for c in app['connectors']:
                connector_info.append(self.allocate_connector(connector_type = c['type'],
                                                              backend = backend_info,
                                                              name = c['name'], 
                                                              args = c['args'],
                                                              ports = s['ports'].keys(),
                                                              image = c['image']))
        return connector_info
                
    """
    Lookup the snapshot connector info and instantiate. 
    """
    def allocate_snapshot_connectors(self, 
                                     snapshot_uuid, 
                                     backend_info):
        connector_info = []
        snapshot = self.snapshot_collection.find_one( {'snapshot_uuid':snapshot_uuid} )
        if snapshot:
            for s in snapshot['snapshot_cs']:
                connector_info.append(self.allocate_connector(connector_type = s['type'],
                                                              backend = backend_info,
                                                              name = s['name'], 
                                                              args = s['args'],
                                                              ports = s['ports'].keys(),
                                                              image = s['image']))
        return connector_info
                

    """
    Restart a stopped connector with an existing storage service. 
    """
    def _restart_connectors(self,
                            service_uuid, 
                            container_info, 
                            backend=None):
        # Initialize the connector and connect to the storage. 
        storage_entry = []
        compute_entry = []
        for b in backend:
            if b['storage']:
                storage_entry.append(self._get_service_configuration(b['storage']))
            if b['compute']:
                for c in b['compute']:
                    compute_entry.append(self._get_service_configuration(c))

        # Start the connectors.
        connector_type = container_info[0]['type']
        args = container_info[0]['args']
        connectors = self._restart_containers(container_info)

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
                                                                                    args)
            # Merge all the entry points. 
            entry_points = dict(entry_point.items() + entry_points.items())

            # Now copy over the configuration.
            self._transfer_config(config_dirs)
            self._transfer_env_vars(connectors, env_vars)

        # Start the containers and update the state. 
        self._restart_service(service_uuid, connectors, connector_type)
        container_info = self._serialize_containers(connectors)
        service = {'uuid':service_uuid, 
                   'containers':container_info, 
                   'backends':backend_names, 
                   'entry':entry_points,
                   'status':'running'}
        self._update_service_configuration(service_uuid, service)
        return service_uuid
                
    """
    Allocate a new connector and associate with an existing storage service. 
    """
    def allocate_connector(self,
                           connector_type, 
                           backend=None,
                           name=None, 
                           args=None,
                           ports=None, 
                           image=None):
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
            logging.warning("USING CONNECTOR SERVICE: " + str(service))
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

            # Start the connector personality. 
            self._start_service(service_uuid, containers, connector_type, entry_point, service)

        # Update the connector state. 
        container_info = self._serialize_containers(containers)
        service_info = {'uuid':service_uuid, 
                        'containers':container_info, 
                        'backends':backend_names, 
                        'class':'connector',
                        'type':connector_type,
                        'entry':entry_points,
                        'uniq': name, 
                        'status':'running'}
        self._update_service_configuration(service_uuid, service_info)
        return service_uuid

    """
    Fetch the current docker version.
    """
    def version(self):
        return self.docker.version()
