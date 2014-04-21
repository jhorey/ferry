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

class CmdHelp(object):
    def __init__(self):
        self.options = {}
        self.cmds = {}
        self.usage = ''
        self.description = ''

    def add_option(self, short_flag, long_flag, help):
        self.options[short_flag] = { 'short' : short_flag,
                                     'long' : long_flag,
                                     'help' : help,
                                     'args' : [] }

    def add_cmd(self, cmd, help):
        self.cmds[cmd] = { 'cmd' : cmd,
                           'help' : help,
                           'args' : [] }

    def _parse_values(self, i, args):
        values = []
        if i == len(args):
            return i - 1, values
        elif args[i] in self.options or args[i] in self.cmds:
            return i - 1, values
        elif i < len(args):
            values.append(args[i])
            j, v = self._parse_values(i + 1, args)

            if i + 1 == j:
                i = j
                values += v

        return i, values

    def _is_option(self, flag):
        if flag in self.options:
            return True
        else:
            for f in self.options.keys():
                if self.options[f]['long'] == flag:
                    return True
        return False

    def _get_canonical_option(self, flag):
        if flag in self.options:
            return flag
        else:
            for f in self.options.keys():
                if self.options[f]['long'] == flag:
                    return f

    def parse_args(self, args):
        i = 0
        while i < len(args):
            s = args[i].strip()
            if self._is_option(s):
                j, values = self._parse_values(i + 1, args)
                s = self._get_canonical_option(s)
                if len(values) > 0:
                    i = j
                    self.options[s]['args'] += values
                else:
                    i += 1
                    self.options[s]['args'].append(True)
            elif s in self.cmds:
                j, values = self._parse_values(i + 1, args)
                if len(values) > 0:
                    i = j
                    self.cmds[s]['args'] += values
                else:
                    i += 1
                    self.cmds[s]['args'].append(True)
            else:
                i += 1

    def get_cmds(self):
        ac = {}
        for c in self.cmds:
            a = self.cmds[c]['args']
            if len(a) > 0:
                ac[c] = a
        return ac

    def get_options(self):
        ac = {}
        for c in self.options:
            a = self.options[c]['args']
            if len(a) > 0:
                ac[c] = a
        return ac

    def print_help(self):
        help_string = 'Usage: ' + self.usage + '\n'
        help_string += '\n'
        help_string += self.description + '\n'
        help_string += '\n'

        help_string += 'Options:\n'

        for k in sorted(self.options.iterkeys()):
            cmd_string = '    {:10s} {:13s} {:10s}'.format(k, self.options[k]['long'], self.options[k]['help'])
            help_string += cmd_string + '\n'
        help_string += '\n'

        help_string += 'Commands:\n'
        for k in sorted(self.cmds.iterkeys()):
            cmd_string = '    {:10s} {:10s}'.format(k, self.cmds[k]['help'])
            help_string += cmd_string + '\n'

        return help_string
