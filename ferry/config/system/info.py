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
import sys
from subprocess import Popen, PIPE

def get_total_memory():
    """
    Get total memory of current system. 
    """
    cmd = "cat /proc/meminfo | grep  MemTotal | awk '{print $2}'"
    output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
    return int(output.strip()) / 1000

def get_free_memory():
    """
    Get free memory of current system. 
    """
    cmd = "cat /proc/meminfo | grep  MemFree | awk '{print $2}'"
    output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
    return int(output.strip()) / 1000

def get_num_cores():
    """
    Get total number of cores. 
    """
    cmd = "cat /proc/cpuinfo | grep cores | awk '{print $4}'"
    output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
    return int(output.strip())
