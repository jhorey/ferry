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

import errno
import ferry
import grp
import json
import logging
import logging.config
import os
import os.path
import pwd
import requests
import re
import shutil
import StringIO
import sys
from termcolor import colored
import yaml
from requests.exceptions import ConnectionError
from ferry.table.prettytable import *
from ferry.options import CmdHelp
from ferry.install import Installer, FERRY_HOME, GUEST_DOCKER_REPO, DEFAULT_FERRY_APPS

class CLI(object):
    def __init__(self):
        self.cmds = CmdHelp()
        self.cmds.description = "Development environment for big data applications"
        self.cmds.version = ferry.__version__
        self.cmds.usage = "ferry COMMAND [arg...]"
        self.cmds.add_option("-c", "--conf", "Deployment configuration")
        self.cmds.add_option("-n", "--dns", "Use custom DNS")
        self.cmds.add_option("-l", "--log", "Log configuration file")
        self.cmds.add_option("-k", "--key", "Specify key directory")
        self.cmds.add_option("-m", "--mode", "Deployment mode")
        self.cmds.add_option("-u", "--upgrade", "Upgrade Ferry")
        self.cmds.add_option("-b", "--build", "Build Ferry default images")
        self.cmds.add_cmd("build", "Build a Dockerfile")
        self.cmds.add_cmd("clean", "Clean zombie Ferry processes")
        self.cmds.add_cmd("server", "Start all the servers")
        self.cmds.add_cmd("deploy", "Deploy a service to the cloud")
        self.cmds.add_cmd("help", "Print this help message")
        self.cmds.add_cmd("info", "Print version information")
        self.cmds.add_cmd("inspect", "Return low-level information on a service")
        self.cmds.add_cmd("install", "Install the Ferry images")
        self.cmds.add_cmd("login", "Login to Ferry servers")
        self.cmds.add_cmd("logs", "Copy over the logs to the host")
        self.cmds.add_cmd("ls", "View installed applications")
        self.cmds.add_cmd("ps", "List deployed and running services")
        self.cmds.add_cmd("pull", "Pull a remote image")
        self.cmds.add_cmd("push", "Push an image to a remote registry")
        self.cmds.add_cmd("rm", "Remove a service or snapshot")
        self.cmds.add_cmd("snapshot", "Take a snapshot")
        self.cmds.add_cmd("snapshots", "List all snapshots")
        self.cmds.add_cmd("ssh", "Connect to a client/connector")
        self.cmds.add_cmd("start", "Start a new service or snapshot")
        self.cmds.add_cmd("stop", "Stop a running service")
        self.cmds.add_cmd("quit", "Stop the Ferry servers")

        self.ferry_server = 'http://127.0.0.1:4000'
        self.default_user = 'root'
        self.installer = Installer(self)

    def _pull_image(self, image):
        """
        Pull a remote image to the local registry. 
        """
        try:
            payload = { 'image' : image } 
            res = requests.get(self.ferry_server + '/image', params=payload)
            return str(res.text)
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    def _pull_app(self, app):
        """
        Pull a local application to Ferry servers. 
        """
        # Now download the application description
        # from the Ferry servers. 
        account, key, server = self.installer.get_ferry_account()
        if account:
            # Read in the contents of the application and
            # generate the API key. 
            req = { 'action' : 'fetch',
                    'app' : app,
                    'account' : account }
            sig = self.installer.create_signature(json.dumps(req), key)
        try:
            payload = { 'id' : account,
                        'app' : app, 
                        'sig' : sig }
            res = requests.get(server + '/app', params=payload)
            status = json.loads(res.text)
            file_name = self.installer.store_app(app, status['ext'], status['content'])
            if file_name:
                content = self._read_app_content(file_name)
                images = self._get_user_images(content)
                for i in images:
                    self._pull_image(i)
                return app
            else:
                return "failed"
        except ConnectionError:
            logging.error("could not connect to application server")
            return "failed"

    def _pull(self, image):
        """
        Pull a remote application/image to the local registry. 
        """
        logging.warning("pulling "  + image)

        # Figure out if we're pushing a Ferry application or 
        # plain Docker image. 
        s = image.split("://")
        if len(s) > 1:
            proto = s[0]
            image = s[1]
        else:
            proto = "image"
            image = s[0]

        if proto == "image":
            return self._pull_image(image, registry)
        else:
            return self._pull_app(image)

    def _push_image(self, image, registry):
        """
        Push a local image to a remote registry. 
        """
        try:
            payload = { 'image' : image,
                        'server' : registry } 
            res = requests.post(self.ferry_server + '/image', data=payload)
            return str(res.text)
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    def _builtin_image(self, image):
        """
        Indicates whether the image is a pre-built Ferry image. 
        Right now we only verify the client images. 
        """
        return image in ["ferry/hadoop-client",
                         "ferry/spark-client",
                         "ferry/cassandra-client",
                         "ferry/openmpi-client"]

    def _get_user_images(self, content):
        """
        Get the user-defined images.
        """
        images = set()
        for c in content['connectors']:
            p = c['personality']
            if not self._builtin_image(p):
                images.add(p)
        return images

    def _read_app_content(self, file_path):
        """
        Read the content of the application. 
        """
        json_arg = None
        with open(file_path, "r") as f:
            n, e = os.path.splitext(file_path)
            if e == '.json':
                json_string = self._read_file_arg(file_path)
                json_arg = json.loads(json_string)
            elif e == '.yaml' or e == '.yml':
                yaml_file = open(file_path, 'r')
                json_arg = yaml.load(yaml_file)
        return json_arg

    def _push_app(self, app, registry):
        """
        Push a local application to Ferry servers. 
        """
        # First find all the images that need to
        # be pushed to the Docker registry. 
        content = self._read_app_content(app)
        if content:
            images = self._get_user_images(content)
            for i in images:
                self._push_image(i, registry)
        
        # Register the application in the Ferry database. 
        account, key, server = self.installer.get_ferry_account()
        if account:
            # Read in the contents of the application and
            # generate the API key. 
            with open(app, "r") as f:
                name = account + '/' + os.path.basename(app)
                name, ext = os.path.splitext(name)
                content = f.read()
                req = { 'action' : 'register',
                        'app' : name,
                        'account' : account }
                sig = self.installer.create_signature(json.dumps(req), key)

                try:
                    payload = { 'id' : account,
                                'app' : name, 
                                'ext' : ext, 
                                'content' : content,
                                'sig' : sig }
                    res = requests.post(server + '/app', data=payload)
                    status = json.loads(res.text)
                    if status['status'] == 'fail':
                        logging.error("failed to register app " + app)
                        return "Failed to register app " + app
                    else:
                        return status['name']
                except ConnectionError:
                    logging.error("could not connect to application server")
                    return "Could not register the application."
                except ValueError as e:
                    logging.error(str(e))
                    return "Registration server sent back unknown reply"
        else:
            logging.error("could not read account information")
            return "Could not read account information."

    def _push(self, image, registry):
        """
        Push a local appliation/image to a remote registry. 
        """
        logging.warning("pushing "  + image)

        # Figure out if we're pushing a Ferry application or 
        # plain Docker image. 
        s = image.split("://")
        if len(s) > 1:
            proto = s[0]
            image = s[1]
        else:
            proto = "image"
            image = s[0]

        if proto == "image":
            return self._push_image(image, registry)
        else:
            return self._push_app(image, registry)

    def _build(self, dockerfile):
        """
        Build a new local image. 
        """
        logging.warning("building "  + dockerfile)
        names = self.installer._get_image(dockerfile)
        name = names.pop().split("/")
        if len(name) == 1:
            repo = GUEST_DOCKER_REPO
            image = name[0]
        else:
            repo = name[0]
            image = name[1]

        build_dir = os.path.dirname(dockerfile)
        self.installer._compile_image(image, repo, build_dir, build=True)
        if len(names) > 0:
            self.installer._tag_images(image, repo, names)

    def _login(self):
        """
        Login to a remote registry
        """
        try:
            res = requests.post(self.ferry_server + '/login')
            return str(res.text)
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    def _create_stack(self, stack_description, args, private_key):
        """
        Create a new stack. 
        """
        mode = self._parse_deploy_arg('mode', args, default='local')
        conf = self._parse_deploy_arg('conf', args, default='default')
        payload = { 'payload' : json.dumps(stack_description),
                    'mode' : mode, 
                    'conf' : conf,
                    'key' : private_key }
        try:
            res = requests.post(self.ferry_server + '/create', data=payload)
            return True, str(res.text)
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return False, "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    def _ask_question(self, question_text):
        question = colored(question_text, 'red')
        prompt = colored(' >> ', 'green')
        return raw_input(question + prompt)

    def _format_apps_query(self, json_data):
        authors = []
        versions = []
        descriptions = []
        for app in json_data.keys():
            authors.append(json_data[app]['author'])
            versions.append(json_data[app]['version'])
            descriptions.append(json_data[app]['description'])            

        t = PrettyTable()
        t.add_column("App", json_data.keys())
        t.add_column("Author", authors)
        t.add_column("Version", versions)
        t.add_column("Description", descriptions)
        return t.get_string(sortby="App",
                            padding_width=2)
        
    def _format_snapshots_query(self, json_data):
        bases = []
        date = []
        for uuid in json_data.keys():
            bases.append(json_data[uuid]['base'])
            if 'snapshot_ts' in json_data[uuid]:
                date.append(json_data[uuid]['snapshot_ts'])
            else:
                date.append(' ')

        t = PrettyTable()
        t.add_column("UUID", json_data.keys())
        t.add_column("Base", bases)
        t.add_column("Date", date)
        return t.get_string(sortby="Date",
                            padding_width=2)

    def _format_table_query(self, json_data):
        storage = []
        compute = []
        connectors = []
        status = []
        base = []
        time = []

        # Each additional row should include the actual data.
        for uuid in json_data.keys():
            csstore = []
            bstore = []
            cstore = []

            for c in json_data[uuid]['connectors']:
                csstore.append(c)

            backends = json_data[uuid]['backends']
            for b in backends:
                if b['storage']:
                    bstore.append(b['storage'])
                else:
                    bstore.append(' ')

                if b['compute']:
                    cstore.append(b['compute'])
                else:
                    cstore.append(' ')
            storage.append(bstore)
            compute.append(cstore)
            connectors.append(csstore)

            status.append(json_data[uuid]['status'])
            base.append(json_data[uuid]['base'])
            time.append(json_data[uuid]['ts'])

        t = PrettyTable()
        t.add_column("UUID", json_data.keys())
        t.add_column("Storage", storage)
        t.add_column("Compute", compute)
        t.add_column("Connectors", connectors)
        t.add_column("Status", status)
        t.add_column("Base", base)
        t.add_column("Time", time)

        return t.get_string(sortby="UUID",
                            padding_width=2)

    def _stop_all(self, private_key):
        try:
            constraints = { 'status' : 'running' }
            payload = { 'constraints' : json.dumps(constraints) }
            res = requests.get(self.ferry_server + '/query', params=payload)
            stacks = json.loads(res.text)
            for uuid in stacks.keys():
                self._manage_stacks({'uuid' : uuid,
                                     'key' : private_key, 
                                     'action' : 'stop'})
        except ConnectionError:
            logging.error("could not connect to ferry server")
        
    def _read_stacks(self, show_all=False, args=None):
        try:
            res = requests.get(self.ferry_server + '/query')
            query_reply = json.loads(res.text)

            deployed_reply = {}
            if show_all:
                mode = self._parse_deploy_arg('mode', args, default='local')
                conf = self._parse_deploy_arg('conf', args, default='default')
                payload = { 'mode' : mode,
                            'conf' : conf }

                res = requests.get(self.ferry_server + '/deployed', params=payload)
                deployed_reply = json.loads(res.text)

            # Merge the replies and format.
            return self._format_table_query(dict(query_reply.items() + deployed_reply.items()))
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    def _list_apps(self):
        """
        List all installed applications including the built-in applications.
        """
        try:
            res = requests.get(self.ferry_server + '/apps')
            json_reply = json.loads(res.text)
            return self._format_apps_query(json_reply)
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    def _list_snapshots(self):
        """
        List all snapshots.
        """
        try:
            res = requests.get(self.ferry_server + '/snapshots')
            json_reply = json.loads(res.text)
            return self._format_snapshots_query(json_reply)
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    def _format_stack_inspect(self, json_data):
        return json.dumps(json_data, 
                          sort_keys=True,
                          indent=2,
                          separators=(',',':'))

    def _inspect_stack(self, stack_id):
        """
        Inspect a specific stack. 
        """
        payload = { 'uuid':stack_id }
        try:
            res = requests.get(self.ferry_server + '/stack', params=payload)
            return res.text
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    def _copy_logs(self, stack_id, to_dir):
        """
        Copy over the logs. 
        """
        payload = {'uuid':stack_id,
                   'dir':to_dir}
        try:
            res = requests.get(self.ferry_server + '/logs', params=payload)
            json_value = json.loads(str(res.text))
            return self._format_stack_inspect(json_value)
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    """
    Connector a specific client/connector via ssh. 
    """
    def _connect_stack(self, stack_id, connector_id, options):
        # Get the IP and default user information for this connector.
        payload = {'uuid':stack_id}
        try:
            res = requests.get(self.ferry_server + '/stack', params=payload)
            json_value = json.loads(str(res.text))
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

        connector_ip = None
        for cg in json_value['connectors']:
            if not connector_id:
                connector_ip = cg['entry']['ip']
                break
            elif connector_id == cg['uniq']:
                connector_ip = cg['entry']['ip']
                break

        # Now form the ssh command. This just executes in the same shell. 
        if connector_ip:
            private_key = self._get_ssh_key(options=options)
            key_opt = '-o StrictHostKeyChecking=no'
            host_opt = '-o UserKnownHostsFile=/dev/null'
            ident = '-i %s' % private_key
            dest = '%s@%s' % (self.default_user, connector_ip)
            cmd = "ssh %s %s %s %s" % (key_opt, host_opt, ident, dest)
            logging.warning(cmd)
            os.execv('/usr/bin/ssh', cmd.split())
        else:
            logging.warning("could not find connector %s" % connector_id)

    def _parse_deploy_arg(self, param, args, default):
        pattern = re.compile('--%s=(\w+)' % param)
        for a in args:
            m = pattern.match(a)
            if m and m.group(0) != '':
                return m.group(1)
        return default

    def _deploy_stack(self, stack_id, args):
        """
        Deploy the stack. 
        """
        mode = self._parse_deploy_arg('mode', args, default='local')
        conf = self._parse_deploy_arg('conf', args, default='default')

        payload = { 'uuid' : stack_id,
                    'mode' : mode,
                    'conf' : conf }
        try:
            res = requests.post(self.ferry_server + '/deploy', data=payload)
            return res.text
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."

    def _manage_stacks(self, stack_info):
        """
        Manage the stack. 
        """
        try:
            res = requests.post(self.ferry_server + '/manage/stack', data=stack_info)
            return str(res.text)        
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."
        
    def _print_help(self):
        """
        Output the help message.
        """
        return self.cmds.print_help()

    def _print_info(self):
        """
        Output version information.
        """
        try:
            res = requests.get(self.ferry_server + '/version')
            s = self.cmds.description + '\n'
            s += "Version: %s\n" % self.cmds.version
            s += "Docker: %s\n" % res.text.strip()

            return s
        except ConnectionError:
            logging.error("could not connect to ferry server")
            return "It appears Ferry servers are not running.\nType sudo ferry server and try again."
        
    def _read_file_arg(self, file_name):
        """
        Helper method to read a file.
        """
        json_file = open(os.path.abspath(file_name), 'r')
        json_text = ''

        for line in json_file:
            json_text += line.strip()

        return json_text

    def _get_ssh_key(self, options=None):
        if options and '-k' in options:
            return options['-k'][0]
        else:
            return ferry.install.DEFAULT_SSH_KEY

    def _find_installed_app(self, app):
        """
        Help find the path to the application. Check both the built-in
        global directory and the user-installed directory.
        """
        file_path = None
        for item in os.listdir(FERRY_HOME + '/data/plans/'):
            if app == os.path.splitext(item)[0]:
                return FERRY_HOME + '/data/plans/' + item

        if not file_path:
            for user in os.listdir(DEFAULT_FERRY_APPS):
                if os.path.isdir(DEFAULT_FERRY_APPS + '/' + user):
                    for item in os.listdir(DEFAULT_FERRY_APPS + '/' + user):
                        if app == user + '/' + os.path.splitext(item)[0]:
                            return DEFAULT_FERRY_APPS + '/' + user + '/' + item

    def _format_output(self, reply):
        output = reply['text'] + "\n"
        for c in reply['msgs'].keys():
            output += "%s: %s\n" % (c, reply['msgs'][c])
        return output

    def _start_stack(self, options, args):
        private_key = self._get_ssh_key(options=options)

        # Check if we need to build the image before running. 
        if '-b' in options:
            build_dir = options['-b'][0]
            self._build(build_dir + '/Dockerfile')

        # Try to figure out what application the user is staring.
        # This could be a new stack or an existing stopped stack. 
        arg = args.pop(0)
        json_arg = {}
        if not os.path.exists(arg):
            file_path = self._find_installed_app(arg)
        else:
            file_path = arg

        # Looks like the user is trying to start a brand
        # new application (specified by a filename). 
        if file_path and os.path.exists(file_path):
            file_path = os.path.abspath(file_path)
            json_arg = self._read_app_content(file_path)
            if not json_arg:
                logging.error("could not load file " + file_path)
                exit(1)
            else:
                # Check if there are any questions associated with
                # this application stack. If so, we should prompt the
                # user and include the answers. 
                if 'questions' in json_arg:
                    for q in json_arg['questions']:
                        question = q['question']
                        q['_answer'] = self._ask_question(question)

            json_arg['_file_path'] = file_path
        json_arg['_file'] = arg

        # Create the application stack and print
        # the status message.
        posted, reply = self._create_stack(json_arg, args, private_key)
        if posted:
            try:
                reply = json.loads(reply)
                if reply['status'] == 'failed':
                    return 'could not create application'
                else:
                    return self._format_output(reply)
            except ValueError as e:
                logging.error(reply)

    def dispatch_cmd(self, cmd, args, options):
        """
        This is the command dispatch table. 
        """
        if(cmd == 'start'):
            return self._start_stack(options, args)
        elif(cmd == 'ps'):
            if len(args) > 0 and args[0] == '-a':
                opt = args.pop(0)
                return self._read_stacks(show_all=True, args = args)
            else:
                return self._read_stacks(show_all=False, args = args)
        elif(cmd == 'snapshots'):
            return self._list_snapshots()
        elif(cmd == 'install'):
            msg = self.installer.install(args, options)
            self.installer._stop_docker_daemon()
            return msg
        elif(cmd == 'clean'):
            self.installer._force_stop_web()
            self.installer._stop_docker_daemon(force=True)
            return 'cleaned ferry'
        elif(cmd == 'inspect'):
            return self._inspect_stack(args[0])
        elif(cmd == 'logs'):
            return self._copy_logs(args[0], args[1])
        elif(cmd == 'server'):
            self.installer.start_web(options)
            return 'started ferry'
        elif(cmd == 'ssh'):
            stack_id = args[0]
            connector_id = None
            if len(args) > 1:
                connector_id = args[1]
            return self._connect_stack(stack_id, connector_id, options)
        elif(cmd == 'quit'):
            private_key = self._get_ssh_key(options=options)
            self._stop_all(private_key)
            self.installer.stop_web(private_key)
            self.installer._stop_docker_daemon()
            return 'stopped ferry'
        elif(cmd == 'deploy'):
            stack_id = args.pop(0)
            return self._deploy_stack(stack_id, args)
        elif(cmd == 'ls'):
            return self._list_apps()
        elif(cmd == 'info'):
            return self._print_info()
        elif(cmd == 'build'):
            return self._build(args[0])
        elif(cmd == 'pull'):
            return self._pull(args[0])
        elif(cmd == 'push'):
            image = args.pop(0)
            if len(args) > 0:
                registry = args.pop(0)
            else:
                registry = None
            return self._push(image, registry)
        elif(cmd == 'login'):
            return self._login()
        elif(cmd == 'help'):
            return self._print_help()
        else:
            # The user wants to perform some management function
            # over the stack. 
            private_key = self._get_ssh_key(options=options)
            stack_info = {'uuid' : args[0],
                          'key' : private_key, 
                          'action' : cmd}
            return self._manage_stacks(stack_info)
    
def main(argv=None):
    # Set up the various logging facilities 
    logging.config.fileConfig(FERRY_HOME + "/logging.conf")

    cli = CLI()
    if(sys.argv):
        if len(sys.argv) > 1:
            cli.cmds.parse_args(sys.argv)

            # Initialize the cli
            options = cli.cmds.get_options()
            if '-l' in options:
                logging.config.fileConfig(options['-l'][0])

            # Execute the commands
            all_cmds = cli.cmds.get_cmds()
            if len(all_cmds) > 0:
                for c in all_cmds.keys():
                    msg = cli.dispatch_cmd(c, all_cmds[c], options)
                    print msg
                    exit(0)
    print cli._print_help()
