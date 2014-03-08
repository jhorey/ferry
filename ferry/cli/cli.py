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
import StringIO
import os
import sys
import json
import logging
import requests
import re
from subprocess import Popen, PIPE
from prettytable import *
from ferry.options import CmdHelp
from ferry.install import Installer, FERRY_HOME

class CLI(object):
    def __init__(self):
        self.cmds = CmdHelp()
        self.cmds.description = "Development environment for big data applications"
        self.cmds.version = "0.1"
        self.cmds.usage = "ferry COMMAND [arg...]"
        self.cmds.add_option("-m", "--mode", "Deployment mode")
        self.cmds.add_option("-c", "--conf", "Deployment configuration")
        self.cmds.add_cmd("server", "Start all the servers")
        self.cmds.add_cmd("deploy", "Deploy a service to the cloud")
        self.cmds.add_cmd("help", "Print this help message")
        self.cmds.add_cmd("info", "Print version information")
        self.cmds.add_cmd("inspect", "Return low-level information on a service")
        self.cmds.add_cmd("install", "Install all the Ferry images")
        self.cmds.add_cmd("logs", "Copy over the logs to the host")
        self.cmds.add_cmd("ps", "List deployed and running services")
        self.cmds.add_cmd("rm", "Remove a service or snapshot")
        self.cmds.add_cmd("snapshot", "Take a snapshot")
        self.cmds.add_cmd("snapshots", "List all snapshots")
        self.cmds.add_cmd("ssh", "Connect to a client/connector")
        self.cmds.add_cmd("start", "Start a new service or snapshot")
        self.cmds.add_cmd("stop", "Stop a running service")
        self.cmds.add_cmd("quit", "Stop the Ferry servers")

        self.ferry_server = 'http://127.0.0.1:4000'
        self.default_user = 'root'
        self.installer = Installer()

    """
    Create a new stack. 
    """
    def _create_stack(self, stack_description, args):
        mode = self._parse_deploy_arg('mode', args, default='local')
        conf = self._parse_deploy_arg('conf', args, default='default')
        payload = { 'payload' : json.dumps(stack_description),
                    'mode' : mode, 
                    'conf' : conf }
        res = requests.post(self.ferry_server + '/create', data=payload)
        return str(res.text)

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
                            border=True, 
                            vrules=ALL, 
                            vertical_char=' ', 
                            junction_char=' ', 
                            padding_width=4)

    def _format_table_query(self, json_data):
        storage = []
        compute = []
        connectors = []
        status = []
        base = []
        time = []

        # Each additional row should include the actual data.
        for uuid in json_data.keys():
            for c in json_data[uuid]['connectors']:
                connectors.append(c)

            backends = json_data[uuid]['backends']
            for b in backends:
                if b['storage']:
                    storage.append(b['storage'])
                else:
                    storage.append(' ')

                if b['compute']:
                    compute.append(b['compute'])
                else:
                    compute.append(' ')

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
                            border=True, 
                            vrules=ALL, 
                            vertical_char=' ', 
                            junction_char=' ', 
                            padding_width=4)

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
        except requests.ConnectionError:
            logging.error("could not connect to ferry server")
            return 'could not connect to ferry server'

    def _list_snapshots(self):
        res = requests.get(self.ferry_server + '/snapshots')
        json_reply = json.loads(res.text)
        return self._format_snapshots_query(json_reply)

    def _format_stack_inspect(self, json_data):
        return json.dumps(json_data, 
                          sort_keys=True,
                          indent=2,
                          separators=(',',':'))
    """
    Inspect a specific stack. 
    """
    def _inspect_stack(self, stack_id):
        payload = { 'uuid':stack_id }
        res = requests.get(self.ferry_server + '/stack', params=payload)
        json_value = json.loads(str(res.text))
        return self._format_stack_inspect(json_value)

    """
    Copy over the logs. 
    """
    def _copy_logs(self, stack_id, to_dir):
        payload = {'uuid':stack_id,
                   'dir':to_dir}
        res = requests.get(self.ferry_server + '/logs', params=payload)
        json_value = json.loads(str(res.text))
        return self._format_stack_inspect(json_value)

    """
    Connector a specific client/connector via ssh. 
    """
    def _connect_stack(self, stack_id, connector_id):
        # Get the IP and default user information for this connector.
        payload = {'uuid':stack_id}
        res = requests.get(self.ferry_server + '/stack', params=payload)
        json_value = json.loads(str(res.text))

        connector_ip = None
        for cg in json_value['connectors']:
            if not connector_id:
                connector_ip = cg['entry']['ip']
                break
            elif connector_id == cg['uniq']:
                connector_ip = cg['entry']['ip']
                break
            else:
                logging.warning("no match: %s %s" % (connector_id, cg['uniq']))

        # Now form the ssh command. This just executes in the same shell. 
        if connector_ip:
            dest = '%s@%s' % (self.default_user, connector_ip)
            logging.warning("ssh %s" % dest)
            os.execv('/usr/bin/ssh', ['', dest])

    def _parse_deploy_arg(self, param, args, default):
        pattern = re.compile('--%s=(\w+)' % param)
        for a in args:
            m = pattern.match(a)
            if m and m.group(0) != '':
                return m.group(1)
        return default

    """
    Deploy the stack. 
    """        
    def _deploy_stack(self, stack_id, args):
        mode = self._parse_deploy_arg('mode', args, default='local')
        conf = self._parse_deploy_arg('conf', args, default='default')

        payload = { 'uuid' : stack_id,
                    'mode' : mode,
                    'conf' : conf }
        res = requests.post(self.ferry_server + '/deploy', data=payload)
        return res.text

    """
    Manage the stack. 
    """
    def _manage_stacks(self, stack_info):
        res = requests.post(self.ferry_server + '/manage/stack', data=stack_info)
        return str(res.text)        
        
    """
    Output the help message.
    """
    def _print_help(self):
        return self.cmds.print_help()

    """
    Output version information.
    """
    def _print_info(self):
        res = requests.get(self.ferry_server + '/version')

        s = self.cmds.description + '\n'
        s += "Version: %s\n" % self.cmds.version
        s += "Docker: %s\n" % res.text.strip()

        return s
        
    """
    Helper method to read a file.
    """
    def _read_file_arg(self, file_name):
        json_file = open(os.path.abspath(file_name), 'r')
        json_text = ''

        for line in json_file:
            json_text += line.strip()

        return json_text

    """
    This is the command dispatch table. 
    """
    def dispatch_cmd(self, cmd, args, options):
        if(cmd == 'start'):
            arg = args.pop(0)
            if os.path.exists(arg):
                json_string = self._read_file_arg(arg)
                json_arg = json.loads(json_string)
            else:
                # Check if the user wants to use one of the global plans.
                global_path = FERRY_HOME + '/plans/' + arg

                # Check if the user has passed in a file extension.
                # If not go ahead and add one. 
                n, e = os.path.splitext(global_path)
                if e == '':
                    global_path += '.json'

                if os.path.exists(global_path):
                    json_string = self._read_file_arg(global_path)
                    json_arg = json.loads(json_string)
                else:
                    json_arg = {}
            json_arg['_file'] = arg
            return self._create_stack(json_arg, args)
        elif(cmd == 'ps'):
            if len(args) > 0 and args[0] == '-a':
                opt = args.pop(0)
                return self._read_stacks(show_all=True, args = args)
            else:
                return self._read_stacks(show_all=False, args = args)
        elif(cmd == 'snapshots'):
            return self._list_snapshots()
        elif(cmd == 'install'):
            self.installer.install(args)
            return 'installed ferry'
        elif(cmd == 'inspect'):
            return self._inspect_stack(args[0])
        elif(cmd == 'logs'):
            return self._copy_logs(args[0], args[1])
        elif(cmd == 'server'):
            self.installer.start_web()
            return 'started ferry'
        elif(cmd == 'ssh'):
            stack_id = args[0]
            connector_id = None
            if len(args) > 1:
                connector_id = args[1]

            return self._connect_stack(stack_id, connector_id)
        elif(cmd == 'quit'):
            self.installer.stop_web()
            self.installer._stop_docker_daemon()
            return 'stopped ferry'
        elif(cmd == 'deploy'):
            stack_id = args.pop(0)
            return self._deploy_stack(stack_id, args)
        elif(cmd == 'info'):
            return self._print_info()
        elif(cmd == 'help'):
            return self._print_help()
        else:
            stack_info = {'uuid' : args[0],
                          'action' : cmd}
            return self._manage_stacks(stack_info)
    
def main(argv=None):
    # Set up the various logging facilities 
    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(logging.Formatter(fmt='%(asctime)s %(message)s', 
                                           datefmt='%m/%d/%Y %I:%M:%S %p'))
    # console.setLevel(logging.ERROR)
    console.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(console)
    root_logger.setLevel(logging.DEBUG)

    cli = CLI()
    if(sys.argv):
        if len(sys.argv) > 1:
            cli.cmds.parse_args(sys.argv)

            # Initialize the cli
            options = cli.cmds.get_options()

            # Execute the commands
            all_cmds = cli.cmds.get_cmds()

            if len(all_cmds) > 0:
                for c in all_cmds.keys():
                    msg = cli.dispatch_cmd(c, all_cmds[c], options)
                    print msg
                    return
    print cli._print_help()
