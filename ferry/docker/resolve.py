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
import yaml

class DefaultResolver(object):

    def resolve(self, questions):
        """
        For each question, map the answer to a parameter value. 
        """
        values = {}
        for q in questions:
            values[q['param']] = q['_answer']
        return values

    def replace(self, payload, values):
        for b in payload['backend']:
            # Check the storage.             
            if b['storage']['instances'] in values.keys():
                b['storage']['instances'] = values[b['storage']['instances']]

                
            # Check the compute. 
            for c in b['compute']:
                if c['instances'] in values.keys():
                    c['instances'] = values[c['instances']]

        return payload
