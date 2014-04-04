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

import json
import logging
from flask import Flask, request
from ferry.docker.manager import DockerManager

# Initialize Flask
app = Flask(__name__)

# Initialize the storage driver
docker = DockerManager()

"""
Generate a filesystem status in JSON format. 
"""
class AllocationResponse(object):
    # Codes to indicate status
    NOT_EXISTS    = 0
    BUILDING      = 1
    READY         = 2
    SHUTTING_DOWN = 3
    SHUT_DOWN     = 4
    TERMINATING   = 5
    TERMINATED    = 6

    def __init__(self):
        self.uuid = None
        self.status = self.NOT_EXISTS
        self.num_instances = 0
        self.type = None

    """
    Return the JSON response. 
    """
    def json(self):
        json_data = {}
        # json_data['uuid'] = str(self.uuid)
        # json_data['status'] = str(self.status)
        # json_data['instances'] = str(self.num_instances)
        # json_data['type'] = str(self.num_instances)

        return json.dumps(json_data, sort_keys=True)

"""
Fetch the current information for a particular filesystem. 
"""
@app.route('/storage', methods=['GET'])
def query_storage():
    status = AllocationResponse()
    status.uuid = request.args['uuid']
    status.status = status.NOT_EXISTS

    # Get the time the storage cluster was created, 
    # along with basic usage information. 
    info = storage.query_storage(status.uuid)
    if info != None:
        status.status = info

    # Return the JSON reply.
    return status.json()


"""
Fetch the current docker version
"""
@app.route('/version', methods=['GET'])
def get_version():
    return docker.version()

"""
Allocate the backend from a snapshot. 
"""
def _allocate_backend_from_snapshot(payload):
    snapshot_uuid = payload['_file']
    backends = docker.fetch_snapshot_backend(snapshot_uuid)
    return _allocate_backend(payload = None,
                             backends = backends)

"""
Allocate the backend from a deployment. 
"""
def _allocate_backend_from_deploy(payload, params=None):
    app_uuid = payload['_file']
    backends = docker.fetch_deployed_backend(app_uuid, params)
    
    if backends:
        return _allocate_backend(payload = None,
                                 backends = backends)

"""
Allocate the backend from a stopped service. 
"""
def _allocate_backend_from_stopped(payload):
    app_uuid = payload['_file']
    backends = docker.fetch_stopped_backend(app_uuid)
    
    if backends:
        return _allocate_backend(payload = None,
                                 backends = backends,
                                 uuid = app_uuid)

"""
Allocate fresh compute backend. 
"""
def _allocate_compute(computes, storage_uuid):
    uuids = []
    for c in computes:
        compute_type = c['personality']
        num_instances = c['instances']

        args = {}
        if 'args' in c:
            args = c['args']

        layers = []
        if 'layers' in c:
            layers = c['layers']

        compute_uuid = docker.allocate_compute(compute_type = compute_type,
                                               storage_uuid = storage_uuid, 
                                               args = args, 
                                               num_instances = num_instances,
                                               layers = layers)
        uuids.append(compute_uuid)
    return uuids

def _restart_compute(computes):
    uuids = []
    for c in computes:
        service_uuid = c['uuid']
        containers = c['containers']
        compute_type = c['type']
        uuids.append(docker.restart_compute(service_uuid,
                                            containers, 
                                            compute_type))
    return uuids

"""
Allocate a brand new backend
"""
def _allocate_backend(payload,
                      backends=None,
                      replace=False,
                      uuid=None):
    if not backends:
        if 'backend' in payload:
            backends = payload['backend']
        else:
            backends = []

    backend_info = { 'uuids' : [],
                     'backend' : backends }
    for b in backends:
        storage = b['storage']

        args = None
        if 'args' in storage:
            args = storage['args']

        # Now create the storage. 
        if not uuid:
            storage_type = storage['personality']
            num_instances = int(storage['instances'])
            layers = []
            if 'layers' in storage:
                layers = storage['layers']
            storage_uuid = docker.allocate_storage(storage_type = storage_type, 
                                                   num_instances = num_instances,
                                                   layers = layers,
                                                   args = args,
                                                   replace = replace)
        else:
            service_uuid = storage['uuid']
            containers = storage['containers']
            storage_type = storage['type']
            storage_uuid = docker.restart_storage(service_uuid,
                                                  container_info = containers,
                                                  storage_type = storage_type)
                                                  
        # Now get the compute information
        compute_uuids = []
        if 'compute' in b:
            if not uuid:
                compute_uuids = _allocate_compute(b['compute'], storage_uuid)
            else:
                compute_uuids = _restart_compute(b['compute'])

        backend_info['uuids'].append( {'storage':storage_uuid,
                                       'compute':compute_uuids} )
    return backend_info

def _allocate_connectors(payload, backend_info):
    connector_info = []
    if 'connectors' in payload:
        connectors = payload['connectors']
        for c in connectors:
            connector_type = c['personality']

            # Connector names are created by the user 
            # to help identify particular instances. 
            connector_name = None
            if 'name' in c:
                connector_name = c['name']

            args = {}
            if 'args' in c:
                args = c['args']

            ports = []
            if 'ports' in c:
                ports = c['ports']

            connector_info.append(docker.allocate_connector(connector_type = connector_type,
                                                            backend = backend_info, 
                                                            name = connector_name, 
                                                            args = args,
                                                            ports = ports))
    return connector_info

"""
Allocate the connectors from a snapshot. 
"""
def _allocate_connectors_from_snapshot(payload, backend_info):
    snapshot_uuid = payload['_file']
    return docker.allocate_snapshot_connectors(snapshot_uuid,
                                               backend_info)

"""
Allocate the connectors from a deployment. 
"""
def _allocate_connectors_from_deploy(payload, backend_info, params=None):
    app_uuid = payload['_file']
    return docker.allocate_deployed_connectors(app_uuid,
                                               backend_info,
                                               params)

"""
Allocate the connectors from a stopped application. 
"""
def _allocate_connectors_from_stopped(payload, backend_info, params=None):
    app_uuid = payload['_file']
    return docker.allocate_stopped_connectors(app_uuid,
                                              backend_info,
                                              params)

"""
Helper function to allocate and start a stopped stack. 
"""
def _allocate_stopped(payload):
    base = docker.get_base_image(payload['_file'])
    backend_info = _allocate_backend_from_stopped(payload)
    connector_info = _allocate_connectors_from_stopped(payload, backend_info['uuids'])

    # Update the stack. 
    uuid = docker.register_stack(backends = backend_info,
                                 connectors = connector_info,
                                 base = base,
                                 uuid = payload['_file'])

    # Return the UUID. 
    return str(uuid)

"""
Helper function to allocate and start a new stack. 
"""
def _allocate_new(payload):
    backend_info = _allocate_backend(payload, replace=True)
    connector_info = _allocate_connectors(payload, backend_info['uuids'])

    # Register the new cluster. 
    uuid = docker.register_stack(backend_info, connector_info, payload['_file'])

    # Return the UUID. 
    return str(uuid)

"""
Helper function to allocate and start a snapshot.
"""
def _allocate_snapshot(payload):
    status = AllocationResponse()
    backend_info = _allocate_backend_from_snapshot(payload)
    connector_info = _allocate_connectors_from_snapshot(payload, 
                                                        backend_info['uuids'])

    # Register the new cluster. 
    uuid = docker.register_stack(backend_info, connector_info, payload['_file'])

    # Return the UUID. 
    return str(uuid)

"""
Helper function to allocate and start a deployed application. 
"""
def _allocate_deployed(payload, params=None):
    backend_info = _allocate_backend_from_deploy(payload, params)
    connector_info = _allocate_connectors_from_deploy(payload, 
                                                      backend_info['uuids'],
                                                      params)

    # Register the new cluster. 
    uuid = docker.register_stack(backend_info, connector_info, payload['_file'])

    # Return the UUID. 
    return str(uuid)

"""
Create some new storage infrastructure
"""
@app.route('/create', methods=['POST'])
def allocate_stack():
    payload = json.loads(request.form['payload'])
    mode = request.form['mode']
    conf = request.form['conf']
    params = docker._get_deploy_params(mode, conf)

    # Check whether the user wants to start from fresh or
    # start with a snapshot.
    if docker.is_stopped(payload['_file']):
        return _allocate_stopped(payload)
    elif docker.is_snapshot(payload['_file']):
        return _allocate_snapshot(payload)
    elif docker.is_deployed(payload['_file'], params):
        return _allocate_deployed(payload, params)
    elif '_file_path' in payload:
        return _allocate_new(payload)
    else:
        return "Could not start " + payload['_file']

"""
Query the deployed applications.
"""
@app.route('/deployed', methods=['GET'])
def query_deployed():
    mode = request.args['mode']
    conf = request.args['conf']
    params = docker._get_deploy_params(mode, conf)

    return docker.query_deployed(params)

"""
Query the stacks.
"""
@app.route('/query', methods=['GET'])
def query_stacks():
    if 'constraints' in request.args:
        constraints = json.loads(request.args['constraints'])
        return docker.query_stacks(constraints)
    else:
        return docker.query_stacks()
"""
Query the snapshots
"""
@app.route('/snapshots', methods=['GET'])
def snapshots():
    return docker.query_snapshots()

"""
Inspect a particular stack.
"""
@app.route('/stack', methods=['GET'])
def inspect():
    uuid = request.args['uuid']
    return docker.inspect_stack(uuid)

"""
Copy over logs
"""
@app.route('/logs', methods=['GET'])
def logs():
    stack_uuid = request.args['uuid']
    to_dir = request.args['dir']
    return docker.copy_logs(stack_uuid, to_dir)

"""
"""
@app.route('/deploy', methods=['POST'])
def deploy_stack():
    stack_uuid = request.form['uuid']
    mode = request.form['mode']
    conf = request.form['conf']

    # Deploy the stack and check if we need to
    # automatically start the stack as well. 
    params = docker._get_deploy_params(mode, conf)
    if docker.deploy_stack(stack_uuid, params):
        _allocate_deployed( { '_file' : stack_uuid } )

"""
Manage the stacks.
"""
@app.route('/manage/stack', methods=['POST'])
def manage_stack():
    stack_uuid = request.form['uuid']
    stack_action = request.form['action']
    reply = docker.manage_stack(stack_uuid, stack_action)

    # Format the message to make more sense.
    if reply['status']:
        return reply['msg'] + ' ' + reply['uuid']
    else:
        return reply['msg']
