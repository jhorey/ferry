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
import ferry.install
from ferry.install import Installer
from ferry.docker.manager import DockerManager
from ferry.docker.docker import DockerInstance
import os
import Queue
import sys
import threading2
import time
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop


# Initialize Flask
app = Flask(__name__)

# Initialize the storage driver
installer = Installer()
docker = DockerManager()

def _stack_worker():
    """
    Worker thread.
    """
    while(True):
        payload = _new_queue.get()

        if payload["_action"] == "new":
            _allocate_new_worker(payload["_uuid"], payload)
        elif payload["_action"] == "stopped":
            _allocate_stopped_worker(payload)
        elif payload["_action"] == "snapshotted":
            _allocate_snapshot_worker(payload["_uuid"], payload)
        elif payload["_action"] == "manage":
            _manage_stack_worker(payload["_uuid"], payload["_manage"], payload["_key"])
            
        time.sleep(2)

_new_queue = Queue.Queue()
_new_stack_worker = threading2.Thread(target=_stack_worker)
_new_stack_worker.daemon = True
_new_stack_worker.start()

def _allocate_backend_from_snapshot(cluster_uuid, payload, key_name):
    """
    Allocate the backend from a snapshot. 
    """
    snapshot_uuid = payload['_file']
    backends = docker.fetch_snapshot_backend(snapshot_uuid)

    if backends:
        return _allocate_backend(cluster_uuid = cluster_uuid,
                                 payload = None,
                                 key_name = key_name, 
                                 backends = backends,
                                 new_stack = True)

def _allocate_backend_from_stopped(payload):
    """
    Allocate the backend from a stopped service. 
    """
    app_uuid = payload['_file']
    backends, key_name = docker.fetch_stopped_backend(app_uuid)
    
    if backends:
        backend_info, backend_plan = _allocate_backend(cluster_uuid = app_uuid,
                                                       payload = None,
                                                       key_name = key_name, 
                                                       backends = backends,
                                                       uuid = app_uuid,
                                                       new_stack = False)
        return backend_info, backend_plan, key_name

def _fetch_num_instances(instance_arg):
    reply = {}
    try:
        reply['num'] = int(instance_arg)
    except ValueError:
        # This is an error so don't allocate anything. 
        reply['num'] = 0

    return reply

def _allocate_compute(cluster_uuid, computes, key_name, storage_uuid):
    """
    Allocate a new compute backend. This method assumes that every
    compute backend already has a specific instance count associated
    with it. After creating the compute backend, it sends back a list
    of all UUIDs that were created in the process. 
    """
    uuids = []
    compute_plan = []
    for c in computes:
        compute_type = c['personality']
        reply = _fetch_num_instances(c['instances'])
        num_instances = reply['num']
        c['instances'] = num_instances
        args = {}
        if 'args' in c:
            args = c['args']

        layers = []
        if 'layers' in c:
            layers = c['layers']

        compute_uuid, compute_containers = docker.allocate_compute(cluster_uuid = cluster_uuid,
                                                                   compute_type = compute_type,
                                                                   key_name = key_name,
                                                                   storage_uuid = storage_uuid, 
                                                                   args = args, 
                                                                   num_instances = num_instances,
                                                                   layers = layers)
        if compute_uuid:
            compute_plan.append( { 'uuid' : compute_uuid,
                                   'containers' : compute_containers,
                                   'type' : compute_type, 
                                   'start' : 'start' } )
            uuids.append( compute_uuid )
        else:
            # The manager could not allocate the compute backend
            # properly. Return a failure so that we can update the
            # status properly and cancel the stack.
            return None, None
    return uuids, compute_plan

def _restart_compute(cluster_uuid, computes):
    uuids = []
    compute_plan = []
    for c in computes:
        service_uuid = c['uuid']
        compute_type = c['type']

        # Transform the containers into proper container objects.
        compute_containers = c['containers']
        containers = [DockerInstance(j) for j in compute_containers] 

        uuids.append(service_uuid)
        compute_plan.append( { 'uuid' : service_uuid,
                               'containers' : containers,
                               'type' : compute_type, 
                               'start' : 'restart' } )
        docker.restart_containers(cluster_uuid, service_uuid, containers)
    return uuids, compute_plan

def _allocate_backend(cluster_uuid,
                      payload,
                      key_name, 
                      backends=None,
                      replace=False,
                      uuid=None,
                      new_stack = True):
    """
    Allocate a brand new backend
    """
    if not backends:
        # We should find the backend information in the payload. 
        if 'backend' in payload:
            backends = payload['backend']
        else:
            backends = []

    # This is the reply we send back. The 'status' denotes whether
    # everything was created/started fine. The UUIDs are a list of 
    # tuples (storage, compute) IDs. The 'backends' just keeps track of
    # the backends we used for allocation purposes. 
    backend_info = { 'status' : 'ok', 
                     'uuids' : [],
                     'backend' : backends }
    storage_plan = []
    compute_plan = []
    compute_uuids = []

    # Go ahead and create the actual backend stack. If the user has passed in
    # an existing backend UUID, that means we should restart that backend. Otherwise
    # we create a fresh backend. 
    for b in backends:
        storage = b['storage']
        if new_stack:
            args = None
            if 'args' in storage:
                args = storage['args']
            storage_type = storage['personality']
            reply = _fetch_num_instances(storage['instances'])
            num_instances = reply['num']
            storage['instances'] = num_instances
            layers = []
            if 'layers' in storage:
                layers = storage['layers']

            storage_uuid, storage_containers = docker.allocate_storage(cluster_uuid = cluster_uuid,
                                                                       storage_type = storage_type, 
                                                                       key_name = key_name, 
                                                                       num_instances = num_instances,
                                                                       layers = layers,
                                                                       args = args,
                                                                       replace = replace)

            if storage_uuid:
                storage_plan.append( { 'uuid' : storage_uuid,
                                       'containers' : storage_containers,
                                       'type' : storage_type, 
                                       'start' : 'start' } )
            else:
                # The storage was not allocated properly. Change 
                # the status so that the stack can be properly cancelled. 
                backend_info["status"] = 'failed'
                return backend_info, None
        else:
            storage_uuid = storage['uuid']
            storage_type = storage['type']
            storage_containers = storage['containers']

            # Transform the containers into proper container objects.
            containers = [DockerInstance(j) for j in storage_containers]
            storage_plan.append( { 'uuid' : storage_uuid,
                                   'containers' : containers,
                                   'type' : storage_type, 
                                   'start' : 'restart' } )
            docker.restart_containers(cluster_uuid, storage_uuid, containers)
                                                  
        # Now allocate the compute backend. The compute is optional so
        # we should check if it even exists first. 
        compute_uuid = []
        if 'compute' in b:
            if not uuid:
                compute_uuid, plan = _allocate_compute(cluster_uuid = cluster_uuid,
                                                       computes = b['compute'], 
                                                       key_name = key_name, 
                                                       storage_uuid = storage_uuid) 

                if compute_uuid:
                    compute_uuids += compute_uuid
                    compute_plan += plan
                else:
                    # The storage was not allocated properly. Change 
                    # the status so that the stack can be properly cancelled. 
                    backend_info["status"] = 'failed'
                    return backend_info, None
            else:
                compute_uuid, plan = _restart_compute(cluster_uuid, b['compute'])
                compute_uuids += compute_uuid
                compute_plan += plan

        backend_info['uuids'].append( {'storage':storage_uuid,
                                       'compute':compute_uuid} )
    return backend_info, { 'storage' : storage_plan,
                           'compute' : compute_plan }

def _allocate_connectors(cluster_uuid, payload, key_name, backend_info):
    connector_info = []
    connector_plan = []
    if 'connectors' in payload:
        connectors = payload['connectors']
        for c in connectors:
            # Check number of instances.
            num_instances = 1
            if 'instances' in c:
                num_instances = int(c['instances'])

            # Check if this connector type has already been pulled
            # into the local index. If not, manually pull it. 
            connector_type = c['personality']
            if not installer._check_and_pull_image(connector_type):
                # We could not fetch this connetor. Instead of 
                # finishing, just return an error.
                return False, connector_info, None

            for i in range(num_instances):
                # Connector names are created by the user 
                # to help identify particular instances. 
                if 'name' in c:
                    connector_name = c['name']
                    if num_instances > 1:
                        connector_name = connector_name + "-" + str(i)
                else:
                    connector_name = None

                # Arguments are optional parameters defined by
                # the user and passed to the connectors.
                if 'args' in c:
                    args = c['args']
                else:
                    args = {}

                # The user can choose to expose ports on the connectors.
                if 'ports' in c:
                    ports = c['ports']
                else:
                    ports = []

                # Now allocate the connector. 
                uuid, containers = docker.allocate_connector(cluster_uuid = cluster_uuid,
                                                             connector_type = connector_type,
                                                             key_name = key_name, 
                                                             backend = backend_info, 
                                                             name = connector_name, 
                                                             args = args,
                                                             ports = ports)
                if uuid:
                    connector_plan.append( { 'uuid' : uuid,
                                             'containers' : containers,
                                             'type' : connector_type, 
                                             'start' : 'start' } )
                    connector_info.append(uuid)
                else:
                    # The manager could not allocate the connectors
                    # properly. Return a failure so that we can update the
                    # status properly and cancel the stack.
                    return False, [], connector_plan
                    
    return True, connector_info, connector_plan

def _allocate_connectors_from_snapshot(cluster_uuid, payload, key_name, backend_info):
    """
    Allocate the connectors from a snapshot. 
    """
    snapshot_uuid = payload['_file']
    return docker.allocate_snapshot_connectors(cluster_uuid,
                                               snapshot_uuid,
                                               key_name, 
                                               backend_info)

def _allocate_connectors_from_stopped(payload, backend_info, params=None):
    """
    Allocate the connectors from a stopped application. 
    """
    app_uuid = payload['_file']
    return docker.allocate_stopped_connectors(app_uuid,
                                              backend_info,
                                              params)

def _register_ip_addresses(backend_plan, connector_plan):
    """
    Helper function to register the hostname/IP addresses
    of all the containers. 
    """
    ips = []
    private_key = None
    for s in backend_plan['storage']:
        for c in s['containers']:
            if isinstance(c, dict):
                ips.append( [c['internal_ip'], c['external_ip'], c['hostname']] )
                private_key = c['privatekey']
            else:
                ips.append( [c.internal_ip, c.external_ip, c.host_name] )
                private_key = c.privatekey

    for s in backend_plan['compute']:
        for c in s['containers']:
            if isinstance(c, dict):
                ips.append( [c['internal_ip'], c['external_ip'], c['hostname']] )
            else:
                ips.append( [c.internal_ip, c.external_ip, c.host_name] )
    for s in connector_plan:
        for c in s['containers']:
            # This is slightly awkward. It is because when starting
            # a new stack, we get proper "container" objects. However,
            # when restarting we get dictionary descriptions. Should just
            # fix at the restart level! 
            if isinstance(c, dict):
                ips.append( [c['internal_ip'], c['external_ip'], c['hostname']] )
            else:
                ips.append( [c.internal_ip, c.external_ip, c.host_name] )

    # It's possible that the storage wasn't allocated
    # properly and so there's nothing to transfer. 
    if private_key:
        docker._transfer_ip(private_key, ips)

def _start_all_services(backend_plan, connector_plan):
    """
    Helper function to start both the backend and
    frontend. Depending on the plan, this will either
    do a fresh start or a restart on an existing cluster. 
    """

    # Make sure that all the hosts have the current set
    # of IP addresses. 
    _register_ip_addresses(backend_plan, connector_plan)

    # Now we need to start/restart all the services. 
    for s in backend_plan['storage']:
        if s['start'] == 'start':
            docker.start_service(s['uuid'], 
                                 s['containers'])
        else:
            docker._restart_service(s['uuid'], s['containers'], s['type'])

    for c in backend_plan['compute']:
        if c['start'] == 'start':
            docker.start_service(c['uuid'], c['containers'])
        else:
            docker._restart_service(c['uuid'], c['containers'], c['type'])

    # The connectors can optionally output msgs for the user.
    # Collect them so that we can display them later. 
    all_output = {}
    for c in connector_plan:
        if c['start'] == 'start':
            output = docker.start_service(c['uuid'], c['containers'])
            all_output = dict(all_output.items() + output.items())
        else:
            output = docker._restart_connectors(c['uuid'], c['containers'], c['backend'])
            all_output = dict(all_output.items() + output.items())
    return all_output

def _allocate_new(payload, key_name):
    """
    Helper function to allocate and start a new stack. 
    """

    # Check if there are any questions/answers in
    # this payload. If so, go ahead and resolve the answers. 
    if 'questions' in payload:
        values = docker.resolver.resolve(payload['questions'])
        payload = docker.resolver.replace(payload, values)

    # Now allocate the backend. This includes both storage and compute. 
    reply = {}
    uuid = docker.reserve_stack()
    payload["_action"] = "new"
    payload["_uuid"] = str(uuid)
    payload["_key"] = key_name
    _new_queue.put(payload)
    docker.register_stack(backends = { 'uuids':[] }, 
                          connectors = [], 
                          base = payload['_file'], 
                          cluster_uuid = uuid, 
                          status='building',
                          key = key_name,
                          new_stack=True)

    return json.dumps({ 'text' : str(uuid),
                        'status' : 'building' })

def _cancel_stack(uuid, backend_info, connector_info, base):
    logging.info("canceling stack...")
    docker.cancel_stack(uuid, backend_info, connector_info)
    docker.register_stack(backends = { 'uuids':[] }, 
                          connectors = [], 
                          base = base, 
                          cluster_uuid = uuid, 
                          status='failed', 
                          new_stack=False)

def _allocate_new_worker(uuid, payload):
    """
    Helper function to allocate and start a new stack. 
    """
    reply = {}
    key_name = payload['_key']
    logging.info("creating backend...")
    backend_info, backend_plan = _allocate_backend(cluster_uuid = uuid,
                                                   payload = payload, 
                                                   key_name = key_name,
                                                   replace=True,
                                                   new_stack=True)
    # Check if the backend status was ok, and if so,
    # go ahead and allocate the connectors. 
    reply['status'] = backend_info['status']
    if backend_info['status'] == 'ok':
        logging.info("creating connectors...")
        success, connector_info, connector_plan = _allocate_connectors(cluster_uuid = uuid,
                                                                       payload = payload, 
                                                                       key_name = key_name, 
                                                                       backend_info = backend_info['uuids'])

        if success:
            logging.info("starting services...")
            output = _start_all_services(backend_plan, connector_plan)
            docker.register_stack(backends = backend_info, 
                                  connectors = connector_info, 
                                  base = payload['_file'], 
                                  key = key_name,
                                  cluster_uuid = uuid, 
                                  status='running', 
                                  output = output,
                                  new_stack=False)
            reply['text'] = str(uuid)
            reply['msgs'] = output
        else:
            # One or more connectors was not instantiated properly. 
            logging.info("cancelling services...")
            _cancel_stack(uuid, backend_info, connector_info, payload['_file'])
            reply['status'] = 'failed'
    else:
        _cancel_stack(uuid, backend_info, [], payload['_file'])
        reply['status'] = 'failed'

    return json.dumps(reply)

def _allocate_stopped(payload):
    uuid = payload['_file']
    stack = docker.get_stack(uuid)
    payload["_action"] = "stopped"
    payload["_key"] = stack['key']
    _new_queue.put(payload)
    docker.register_stack(backends = stack['backends'], 
                          connectors = stack['connectors'],
                          base = stack['base'],
                          cluster_uuid = uuid,
                          status='restarting', 
                          key = stack['key'],
                          new_stack = False)
    return json.dumps({'status' : 'building',
                       'text' : str(uuid)})

def _allocate_stopped_worker(payload):
    """
    Helper function to allocate and start a stopped stack. 
    """
    uuid = payload['_file']
    stack = docker.get_stack(uuid)
    logging.info("creating backend...")
    backend_info, backend_plan, key_name = _allocate_backend_from_stopped(payload = payload)
                                                                          
    if backend_info['status'] == 'ok':
        logging.info("creating connectors...")
        connector_info, connector_plan = _allocate_connectors_from_stopped(payload = payload, 
                                                                           backend_info = backend_info['uuids'])
        logging.info("starting services...")
        output = _start_all_services(backend_plan, connector_plan)
        docker.register_stack(backends = backend_info,
                              connectors = connector_info,
                              base = stack['base'],
                              cluster_uuid = uuid,
                              status='running', 
                              output = output,
                              key = stack['key'],
                              new_stack = False)
        return json.dumps({'status' : 'ok',
                           'text' : str(uuid),
                           'msgs' : output})
    else:
        return json.dumps({'status' : 'failed'})

def _allocate_snapshot(payload, key_name):
    """
    Helper function to allocate and start a snapshot.
    """
    uuid = docker.reserve_stack()
    payload["_action"] = "snapshotted"
    payload["_uuid"] = str(uuid)
    payload["_key"] = key_name
    _new_queue.put(payload)
    docker.register_stack(backends = { 'uuids':[] }, 
                          connectors = [], 
                          base = payload['_file'], 
                          cluster_uuid = uuid, 
                          status='building',
                          key = key_name,
                          new_stack=True)
    return json.dumps({ 'text' : str(uuid),
                        'status' : 'building' })

def _allocate_snapshot_worker(uuid, payload):
    """
    Helper function to allocate and start a snapshot.
    """
    key_name = payload['_key']
    backend_info, backend_plan = _allocate_backend_from_snapshot(cluster_uuid = uuid,
                                                                 payload = payload,
                                                                 key_name = key_name)
    if backend_info['status'] == 'ok':
        connector_info, connector_plan = _allocate_connectors_from_snapshot(cluster_uuid = uuid,
                                                                            payload = payload, 
                                                                            key_name = key_name,                                                                            
                                                                            backend_info = backend_info['uuids'])
        output = _start_all_services(backend_plan, connector_plan)
        docker.register_stack(backends = backend_info, 
                              connectors = connector_info, 
                              base = payload['_file'],
                              cluster_uuid = uuid,
                              status='running', 
                              output = output,
                              key = key_name,
                              new_stack = True)
        return json.dumps({'status' : 'ok',
                           'text' : str(uuid),
                           'msgs' : output })
    else:
        return json.dumps({'status' : 'failed'})


@app.route('/storage', methods=['GET'])
def query_storage():
    """
    Fetch the current information for a particular filesystem. 
    """
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

@app.route('/version', methods=['GET'])
def get_version():
    """
    Fetch the current docker version
    """
    return docker.version()

@app.route('/login', methods=['POST'])
def login_registry():
    """
    Login to a remote registry. 
    """
    if docker.login_registry():
        return "success"
    else:
        return "fail"

@app.route('/image', methods=['POST'])
def push_image():
    """
    Push a local image to a remote registry. 
    """
    image = request.form['image']
    if 'server' in request.form:
        registry = request.form['server']
    else:
        registry = None
    if docker.push_image(image, registry):
        return "success"
    else:
        return "fail"

@app.route('/image', methods=['GET'])
def pull_image():
    """
    Pull a remote image to the local registry. 
    """
    image = request.args['image']
    if docker.pull_image(image):
        return "success"
    else:
        return "fail"
    
@app.route('/create', methods=['POST'])
def allocate_stack():
    """
    Create some new storage infrastructure
    """
    payload = json.loads(request.form['payload'])
    key_name = request.form['key']

    # Check whether the user wants to start from fresh or
    # start with a snapshot.
    if docker.is_stopped(payload['_file']):
        return _allocate_stopped(payload)
    elif docker.is_snapshot(payload['_file']):
        return _allocate_snapshot(payload, key_name)
    elif '_file_path' in payload:
        return _allocate_new(payload, key_name)
    else:
        return "Could not start " + payload['_file']

@app.route('/quit', methods=['POST'])
def quit():
    """
    Quit any backend services that may be running. 
    """
    docker.quit()
    return ""

@app.route('/query', methods=['GET'])
def query_stacks():
    """
    Query the stacks.
    """
    if 'constraints' in request.args:
        constraints = json.loads(request.args['constraints'])
        return docker.query_stacks(constraints)
    else:
        return docker.query_stacks()

@app.route('/snapshots', methods=['GET'])
def snapshots():
    """
    Query the snapshots
    """
    return docker.query_snapshots()

@app.route('/apps', methods=['GET'])
def apps():
    """
    Get list of installed applications.
    """
    if 'app' in request.args:
        app = request.args['app']
    else:
        app = None

    return docker.query_applications(app)

@app.route('/images', methods=['GET'])
def images():
    """
    Get list of installed Docker images.
    """
    return docker.query_images()

@app.route('/stack', methods=['GET'])
def inspect():
    """
    Inspect a particular stack.
    """
    uuid = request.args['uuid']
    resp = docker.inspect_stack(uuid)
    if resp:
        return resp
    elif docker.is_installed(uuid):
        return docker.inspect_installed(uuid)
    else:
        # Try to see if this is an active service.
        service = docker._get_service_configuration(uuid, detailed=True)
        if service:
            service_info = docker._get_inspect_info(uuid)
            return json.dumps(service_info,
                              sort_keys=True,
                              indent=2,
                              separators=(',',':'))
    return "could not inspect " + str(uuid)

@app.route('/logs', methods=['GET'])
def logs():
    """
    Copy over logs
    """
    stack_uuid = request.args['uuid']
    to_dir = request.args['dir']
    return docker.copy_logs(stack_uuid, to_dir)

@app.route('/manage/stack', methods=['POST'])
def manage_stack():
    """
    Manage the stacks.
    """
    payload = { "_uuid" : request.form['uuid'],
                "_manage" : request.form['action'],
                "_key" : request.form['key'],
                "_action" : "manage" }
    _new_queue.put(payload)
    return ""

def _manage_stack_worker(uuid, action, private_key):
    """
    Manage the stacks.
    """
    reply = docker.manage_stack(stack_uuid = uuid, 
                                private_key = private_key,
                                action = action)

@app.before_request
def before_request():
    context = {
        'url': request.path,
        'method': request.method,
        'ip': request.environ.get("REMOTE_ADDR")
    }
    logging.debug("%(method)s from %(ip)s for %(url)s", context)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

if __name__ == '__main__':
    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(port=int(sys.argv[2]),
                       address=sys.argv[1])
    IOLoop.instance().start()

