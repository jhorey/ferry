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

AWS_INSTANCE_INFO = {
    "t2.micro" : { "mem" : 1, "cores" : 1 },
    "t2.small" : { "mem" : 2, "cores" : 1 },
    "t2.medium" : { "mem" : 4, "cores" : 2 },
    "m3.medium" : { "mem" : 3.75, "cores" : 1 },
    "m3.large" : { "mem" : 7.5, "cores" : 2 },
    "m3.xlarge" : { "mem" : 15, "cores" : 4 },
    "m3.2xlarge" : { "mem" : 30, "cores" : 8 },
    "c3.large" : { "mem" : 3.75, "cores" : 2 },
    "c3.xlarge" : { "mem" : 7.5, "cores" : 4 },
    "c3.2xlarge" : { "mem" : 15, "cores" : 8 },
    "c3.4xlarge" : { "mem" : 30, "cores" : 16 },
    "c3.8xlarge" : { "mem" : 60, "cores" : 32 },
    "r3.large" : { "mem" : 15.25, "cores" : 2 },
    "r3.xlarge" : { "mem" : 30.5, "cores" : 4 },
    "r3.2xlarge" : { "mem" : 61, "cores" : 8 },
    "r3.4xlarge" : { "mem" : 122, "cores" : 16 },
    "r3.8xlarge" : { "mem" : 244, "cores" : 32 },
    "i2.xlarge" : { "mem" : 30.5, "cores" : 4 },
    "i2.2xlarge" : { "mem" : 61, "cores" : 8 },
    "i2.4xlarge" : { "mem" : 122, "cores" : 16 },
    "i2.8xlarge" : { "mem" : 244, "cores" : 32 },
    "g2.2xlarge" : { "mem" : 15, "cores" : 8 },
    "hs1.8xlarge" : { "mem" : 117, "cores" : 16 }
}

class System(object):
    def __init__(self):
        self.instance_type = "t2.small"

    def get_total_memory(self):
        """
        Get total memory of current system. 
        """
        if self.instance_type in AWS_INSTANCE_INFO:
            return AWS_INSTANCE_INFO[self.instance_type]["mem"] * 1024
        else:
            logging.warning("AWS system could not find " + self.instance_type)
            return 1024

    def get_free_memory(self):
        """
        Get free memory of current system. 
        """
        if self.instance_type in AWS_INSTANCE_INFO:
            return AWS_INSTANCE_INFO[self.instance_type]["mem"] * 1024
        else:
            return 1024

    def get_num_cores(self):
        """
        Get total number of cores. 
        """
        if self.instance_type in AWS_INSTANCE_INFO:
            return AWS_INSTANCE_INFO[self.instance_type]["cores"]
        else:
            return 1
