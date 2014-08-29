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

import logging
import re
from subprocess import Popen, PIPE
import time

def robust_com(cmd):
    # All the possible errors that might happen when
    # we try to connect via ssh. 
    route_closed = re.compile('.*No route to host.*', re.DOTALL)
    conn_closed = re.compile('.*Connection closed.*', re.DOTALL)
    refused_closed = re.compile('.*Connection refused.*', re.DOTALL)
    timed_out = re.compile('.*timed out*', re.DOTALL)
    permission = re.compile('.*Permission denied.*', re.DOTALL)
    while(True):
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        output = proc.stdout.read()
        err = proc.stderr.read()
        if route_closed.match(err) or conn_closed.match(err) or refused_closed.match(err) or timed_out.match(err) or permission.match(err):
            logging.warning("com error, trying again...")
            time.sleep(10)
        else:
            logging.warning("com msg: " + err)
            break
    return output, err
