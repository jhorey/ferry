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

import base64
import ferry
import grp
import hashlib
import hmac
import json
import logging
import os
import os.path
import pwd
import re
import shutil
import stat
import struct
import sys
import time
import uuid
import yaml
from distutils import spawn
from ferry.ip.client import DHCPClient
from ferry.config.mongo.mongoconfig import *
from ferry.docker.fabric import DockerFabric
from string import Template
from subprocess import Popen, PIPE

def _get_download_url():
    if 'DOWNLOAD_URL' in os.environ:
        return os.environ['DOWNLOAD_URL']
    else:
        return "https://s3.amazonaws.com/opencore"
    
def _get_ferry_home():
    if 'FERRY_HOME' in os.environ:
        return os.environ['FERRY_HOME']
    else:
        return os.path.dirname(__file__)

def _get_docker_registry():
    if 'DOCKER_REGISTRY' in os.environ:
        return os.environ['DOCKER_REGISTRY']
    else:
        return None

def _get_ferry_dir(server):
    """
    Get the Ferry data directory. 
    For now we need to keep the client/server synched,
    (this is something we need to fix later). 
    """
    if 'FERRY_DIR' in os.environ:
        return os.environ['FERRY_DIR']
    else:
        # We need to figure out if this is being called
        # from the server or client. 
        if server:
            return '/var/lib/ferry'
        else:
            return os.environ['HOME'] + '/.ferry'

def _get_ferry_scratch():
    if 'FERRY_SCRATCH' in os.environ:
        scratch_dir = os.environ['FERRY_SCRATCH']
    else:
        scratch_dir = os.path.join(_get_ferry_dir(server=True), 'scratch')

    if not os.path.isdir(scratch_dir):
        os.makedirs(scratch_dir)

    return scratch_dir

def _get_ferry_user():
    uid = pwd.getpwnam("root").pw_uid
    gid = grp.getgrnam("docker").gr_gid
    return uid, gid
    
def _has_ferry_user():
    try:
        uid = pwd.getpwnam("root").pw_uid
        gid = grp.getgrnam("docker").gr_gid
    except KeyError:
        return False
    return True

def _supported_arch():
    return struct.calcsize("P") * 8 == 64

def _supported_lxc():
    output = Popen("(lxc-version 2>/dev/null || lxc-start --version) | sed 's/.* //'", stdout=PIPE, shell=True).stdout.read()

    # Ignore all non-numeric strings in the
    # versioning information. 
    cleaned = []
    tuples = output.strip().split(".")[:3]
    for t in tuples: 
        m = re.compile('(\d)*').match(t)
        if m and len(m.groups()) > 0 and m.group(1) != '':
            cleaned.append(m.group(1))
        else:
            cleaned.append(str(0))

    # We need our tuples to be exactly three values. If
    # there are more values, add a zero. 
    for i in range(3 - len(cleaned)):
        cleaned.append(0)

    # Now compare the tuples. We need at least version 0.7.5. This
    # assumes that lxc-version info is consistent across distributions
    # which may not be true...
    ver = tuple(map(int, cleaned))
    return ver > (0, 7, 5)

def _supported_python():
    return sys.version_info[0] == 2

def _touch_file(file_name, content, root=False):
    # Check if we need to create the parent dir.
    # first. If the parent dir. doesn't exist, then
    # "open" will throw an exception. 
    if not os.path.isdir(os.path.dirname(file_name)):
        os.makedirs(os.path.dirname(file_name))

    try:
        f = open(file_name, 'w+')
        f.write(content)
        f.close()

        os.chmod(file_name, 0664)
        if root:
            uid, gid = _get_ferry_user()
            os.chown(file_name, uid, gid)
    except IOError as e:
        logging.error("Could not create %s.\n" % file_name)

FERRY_HOME=_get_ferry_home()
DEFAULT_IMAGE_DIR=FERRY_HOME + '/data/dockerfiles'
DEFAULT_KEY_DIR=FERRY_HOME + '/data/key'
DEFAULT_SSH_KEY=DEFAULT_KEY_DIR + '/insecure_ferry_key.pem'
DEFAULT_DOCKER_LOGIN=os.environ['HOME'] + '/.ferry.docker'
DEFAULT_DOCKER_REPO='ferry'
GUEST_DOCKER_REPO='ferry-user'
DEFAULT_FERRY_OWNER='ferry:docker'
DOCKER_REGISTRY=_get_docker_registry()
DOCKER_CMD='docker-ferry'
DOCKER_SOCK='unix:////var/run/ferry.sock'
DOCKER_PID='/var/run/ferry.pid'
DOCKER_DIR=_get_ferry_dir(server=True)
DEFAULT_TEMPLATE_DIR=FERRY_HOME + '/data/templates'
DEFAULT_BUILTIN_APPS=FERRY_HOME + '/data/plans'
DEFAULT_FERRY_APPS=DOCKER_DIR + '/apps'
DEFAULT_MONGO_DB=DOCKER_DIR + '/mongo'
DEFAULT_MONGO_LOG=DOCKER_DIR + '/mongolog'
DEFAULT_REGISTRY_DB=DOCKER_DIR + '/registry'
DEFAULT_DOCKER_LOG=DOCKER_DIR + '/docker.log'

class Installer(object):
    def __init__(self, cli=None):
        self.network = DHCPClient()
        self.fabric = DockerFabric(bootstrap=True)
        self.mongo = MongoInitializer()
        self.mongo.fabric = self.fabric
        self.mongo.template_dir = DEFAULT_TEMPLATE_DIR + '/mongo/'
        self.cli = cli

    def get_ferry_account(self):
        """
        Read in the remote Ferry DB account information. Used
        for registering applications. 
        """
        with open(ferry.install.DEFAULT_DOCKER_LOGIN, 'r') as f:
            args = yaml.load(f)
            args = args['ferry']
            if all(k in args for k in ("user","key","server")):
                return args['user'], args['key'], args['server']
        return None, None, None

    def create_signature(self, request, key):
        """
        Generated a signed request.
        """
        return hmac.new(key, request, hashlib.sha256).hexdigest()

    def store_app(self, app, ext, content):
        """
        Store the application in the global directory. 
        """
        try:
            # We may need to create the parent directory
            # if this is the first time an application from this user
            # is downloaded. 
            file_name = os.path.join(DEFAULT_FERRY_APPS, app + ext)
            os.makedirs(os.path.dirname(file_name))
            with open(file_name, "w") as f:
                f.write(content)
            return file_name
        except IOError as e:
            logging.error(e)
            return None
        except OSError as os:
            logging.error(os)
            return None

    def _clean_rules(self):
        """
        Get rid of all the forwarding rules. 
        """
        self.network.clean_rules()

    def install(self, args, options):
        # Check if the host is actually 64-bit. If not raise a warning and quit.
        if not _supported_arch():
            return 'Your architecture appears to be 32-bit.\nOnly 64-bit architectures are supported at the moment.'

        if not _supported_python():
            return 'You appear to be running Python3.\nOnly Python2 is supported at the moment.'

        if not _supported_lxc():
            return 'You appear to be running an older version of LXC.\nOnly versions > 0.7.5 are supported.'

        if not _has_ferry_user():
            return 'You do not appear to have the \'docker\' group configured. Please create the \'docker\' group and try again.'

        # Create the various directories.
        try:
            if not os.path.isdir(DOCKER_DIR):
                os.makedirs(DOCKER_DIR)
                self._change_permission(DOCKER_DIR)
        except OSError as e:
            logging.error("Could not install Ferry.\n") 
            logging.error(e.strerror)
            sys.exit(1)

        # Make sure that the Ferry keys have the correct
        # ownership & permission. 
        self._check_and_change_ssh_keyperm()

        # Start the Ferry docker daemon. If it does not successfully
        # start, print out a msg. 
        logging.warning("all prerequisites met...")
        start, msg = self._start_docker_daemon(options)
        if not start:
            logging.error('ferry docker daemon not started')
            return msg

        # Normally we don't want to build the Dockerfiles,
        # but sometimes we may for testing, etc. 
        build = False
        if options and '-b' in options:
            build = True

        if options and '-u' in options:
            if len(options['-u']) > 0 and options['-u'][0] != True:
                logging.warning("performing select rebuild (%s)" % str(options['-u']))
                self.build_from_list(options['-u'], 
                                     DEFAULT_IMAGE_DIR,
                                     DEFAULT_DOCKER_REPO, build, recurse=False)
            else:
                logging.warning("performing forced rebuild")
                self.build_from_dir(DEFAULT_IMAGE_DIR, DEFAULT_DOCKER_REPO, build)
        else:
            # We want to be selective about which images
            # to rebuild. Useful if one image breaks, etc. 
            to_build = self.check_images(DEFAULT_IMAGE_DIR,
                                         DEFAULT_DOCKER_REPO)
            if len(to_build) > 0:
                logging.warning("performing select rebuild (%s)" % str(to_build))
                self.build_from_list(to_build, 
                                     DEFAULT_IMAGE_DIR,
                                     DEFAULT_DOCKER_REPO, build)

        # Check that all the images were built.
        not_installed = self._check_all_images()
        if len(not_installed) == 0:
            return 'installed ferry'
        else:
            logging.error('images not built: ' + str(not_installed))
            return 'Some images were not installed. Please type \'ferry install\' again.'

    def _check_all_images(self):
        not_installed = []
        images = ['mongodb', 'ferry-base', 'hadoop-base', 'hadoop', 'hadoop-client',
                  'hive-metastore', 'gluster', 'openmpi', 'openmpi-client', 'cassandra', 'cassandra-client', 
                  'titan', 'spark']
        for i in images:
            if not self._check_image_installed("%s/%s" % (DEFAULT_DOCKER_REPO, i)):
                not_installed.append(i)
        return not_installed

    def _check_and_pull_image(self, image_name):
        if not self._check_image_installed(image_name):
            self._pull_image(image_name, on_client=False)

        return self._check_image_installed(image_name)

    def _check_image_installed(self, image_name):
        cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' inspect %s 2> /dev/null' % image_name
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
        if output.strip() == '[]':
            return False
        else:
            return True

    def _transfer_config(self, config_dirs):
        """
        Transfer the configuration to the containers. 
        """
        for c in config_dirs:
            container = c[0]
            from_dir = c[1]
            to_dir = c[2]
            self.fabric.copy([container], from_dir, to_dir)

    def _read_public_key(self, private_key):
        s = private_key.split("/")
        p = os.path.splitext(s[len(s) - 1])[0]
        return p

    def _check_and_change_ssh_keyperm(self):
        os.chmod(DEFAULT_SSH_KEY, 0600)
        uid, gid = _get_ferry_user()
        os.chown(DEFAULT_SSH_KEY, uid, gid)

    def start_web(self, options=None, clean=False):
        start, msg = self._start_docker_daemon(options)
        if not clean and not start:
            # We are trying to start the web services but the Docker
            # daemon won't start. If we're cleaning, it's not a big deal. 
            logging.error(msg) 
            sys.exit(1)

        # Check if the ssh key permission is properly set. 
        self._check_and_change_ssh_keyperm()

        # Check if the user-application directory exists.
        # If not, create it. 
        try:
            if not os.path.isdir(DEFAULT_FERRY_APPS):
                os.makedirs(DEFAULT_FERRY_APPS)
                self._change_permission(DEFAULT_FERRY_APPS)
        except OSError as e:
            logging.error("Could not create application directory.\n") 
            logging.error(e.strerror)
            sys.exit(1)

        # Check if the Mongo directory exists yet. If not
        # go ahead and create it. 
        try:
            if not os.path.isdir(DEFAULT_MONGO_DB):
                os.makedirs(DEFAULT_MONGO_DB)
                self._change_permission(DEFAULT_MONGO_DB)
            if not os.path.isdir(DEFAULT_MONGO_LOG):
                os.makedirs(DEFAULT_MONGO_LOG)
                self._change_permission(DEFAULT_MONGO_LOG)
        except OSError as e:
            logging.error("Could not start ferry servers.\n") 
            logging.error(e.strerror)
            sys.exit(1)

        # Check if the Mongo image is built.
        if not self._check_image_installed('%s/mongodb' % DEFAULT_DOCKER_REPO):
            logging.error("Could not start ferry servers.\n") 
            logging.error("MongoDB images not found. Try executing 'ferry install'.")
            sys.exit(1)

        # Check if there are any other Mongo instances runnig.
        self._clean_web()

        # Start the Mongo server. Create a new configuration and
        # manually start the container. 
        private_key = self.cli._get_ssh_key(options)
        volumes = { DEFAULT_MONGO_LOG : self.mongo.container_log_dir,
                    DEFAULT_MONGO_DB : self.mongo.container_data_dir }
        mongoplan = {'image':'ferry/mongodb',
                     'type':'ferry/mongodb', 
                     'keydir': { '/service/keys' : DEFAULT_KEY_DIR },
                     'keyname': self._read_public_key(private_key), 
                     'privatekey': private_key, 
                     'volumes':volumes,
                     'volume_user':DEFAULT_FERRY_OWNER, 
                     'ports':[],
                     'exposed':self.mongo.get_exposed_ports(1), 
                     'hostname':'ferrydb',
                     'netenable':True, 
                     'args': 'trust'
                     }
        mongoconf = self.mongo.generate(1)
        mongoconf.uuid = 'fdb-' + str(uuid.uuid4()).split('-')[0]
        mongobox = self.fabric.alloc([mongoplan])[0]
        if not mongobox:
            logging.error("Could not start MongoDB image")
            sys.exit(1)

        ip = mongobox.internal_ip
        _touch_file('/tmp/mongodb.ip', ip, root=True)

        # Once the container is started, we'll need to copy over the
        # configuration files, and then manually send the 'start' command. 
        s = { 'container':mongobox,
              'data_dev':'eth0', 
              'data_ip':mongobox.internal_ip, 
              'manage_ip':mongobox.internal_ip,
              'host_name':mongobox.host_name,
              'type':mongobox.service_type,
              'args':mongobox.args }
        config_dirs, entry_point = self.mongo.apply(mongoconf, [s])
        self._transfer_config(config_dirs)
        self.mongo.start_service([mongobox], entry_point, self.fabric)

        # Set the MongoDB env. variable. 
        my_env = os.environ.copy()
        my_env['MONGODB'] = ip

        # Sleep a little while to let Mongo start receiving.
        time.sleep(2)

        # Start the DHCP server
        logging.warning("starting dhcp server")
        cmd = 'gunicorn -t 3600 -b 127.0.0.1:5000 -w 1 ferry.ip.dhcp:app &'
        Popen(cmd, stdout=PIPE, shell=True, env=my_env)
        time.sleep(2)

        # Reserve the Mongo IP.
        self.network.reserve_ip(ip)

        # Start the Ferry HTTP servers
        logging.warning("starting http servers on port 4000 and mongo %s" % ip)
        cmd = 'gunicorn -e FERRY_HOME=%s -t 3600 -w 3 -b 127.0.0.1:4000 ferry.http.httpapi:app &' % FERRY_HOME
        Popen(cmd, stdout=PIPE, shell=True, env=my_env)

    def _force_stop_web(self):
        logging.warning("stopping docker http servers")
        cmd = 'pkill -f gunicorn'
        Popen(cmd, stdout=PIPE, shell=True)

    def stop_web(self, key):
        # Shutdown the mongo instance
        if os.path.exists('/tmp/mongodb.ip'):
            f = open('/tmp/mongodb.ip', 'r')
            ip = f.read().strip()
            f.close()

            cmd = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i %s root@%s /service/sbin/startnode stop' % (key, ip)
            logging.warning(cmd)
            output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
            logging.warning(output)
            cmd = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i %s root@%s /service/sbin/startnode halt' % (key, ip)
            logging.warning(cmd)
            output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
            logging.warning(output)
            os.remove('/tmp/mongodb.ip')

        # Kill all the gunicorn instances. 
        logging.warning("stopping http servers")
        cmd = 'ps -eaf | grep httpapi | awk \'{print $2}\' | xargs kill -15'
        Popen(cmd, stdout=PIPE, shell=True)
        cmd = 'ps -eaf | grep ferry.ip.dhcp | awk \'{print $2}\' | xargs kill -15'
        Popen(cmd, stdout=PIPE, shell=True)

    def _clean_web(self):
        docker = DOCKER_CMD + ' -H=' + DOCKER_SOCK
        cmd = docker + ' ps | grep ferry/mongodb | awk \'{print $1}\' | xargs ' + docker + ' stop '
        logging.warning("cleaning previous mongo resources")
        logging.warning(cmd)
        child = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        child.stdout.read()
        child.stderr.read()

    def _copytree(self, src, dst):
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

    def _change_permission(self, location):
        uid, gid = _get_ferry_user()
        os.chown(location, uid, gid)

        if os.path.isdir(location):        
            os.chmod(location, 0774)
            for entry in os.listdir(location):
                self._change_permission(os.path.join(location, entry))
        else:
            # Check if this file has a file extension. If not,
            # then assume it's a binary.
            s = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH
            if len(location.split(".")) == 1:
                s |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            os.chmod(location, s)

    """
    Check if the dockerfiles are already built. 
    """
    def check_images(self, image_dir, repo):
        if self._docker_running():
            build_images = []
            for f in os.listdir(image_dir):
                dockerfile = image_dir + '/' + f + '/Dockerfile'
                image_names = self._check_dockerfile(dockerfile, repo)
                if len(image_names) > 0:
                    build_images += image_names
            return build_images
        else:
            logging.error("ferry daemon not started")

    """
    Build the docker images
    """
    def build_from_list(self, to_build, image_dir, repo, build=False, recurse=True):
        if self._docker_running():
            built_images = {}
            for f in os.listdir(image_dir):
                logging.warning("transforming dockerfile")
                self._transform_dockerfile(image_dir, f, repo)

            for f in os.listdir("/tmp/dockerfiles/"):
                dockerfile = '/tmp/dockerfiles/' + f + '/Dockerfile'
                images = self._get_image(dockerfile)
                intersection = [i for i in images if i in to_build]
                if len(intersection) > 0:
                    image = images.pop(0)
                    logging.warning("building image " + image)
                    self._build_image(image, dockerfile, repo, built_images, recurse=recurse, build=build)

                    if len(images) > 0:
                        logging.warning("tagging images " + image)
                        self._tag_images(image, repo, images)

            # After building everything, get rid of the temp dir.
            shutil.rmtree("/tmp/dockerfiles")
        else:
            logging.error("ferry daemon not started")

    """
    Build the docker images
    """
    def build_from_dir(self, image_dir, repo, build=False):
        if self._docker_running():
            built_images = {}
            for f in os.listdir(image_dir):
                self._transform_dockerfile(image_dir, f, repo)
            for f in os.listdir("/tmp/dockerfiles/"):
                dockerfile = "/tmp/dockerfiles/" + f + "/Dockerfile"
                images = self._get_image(dockerfile)
                image = images.pop(0)
                self._build_image(image, dockerfile, repo, built_images, recurse=True, build=build)

                if len(images) > 0:
                    logging.warning("tagging images " + image)
                    self._tag_images(image, repo, images)

            # After building everything, get rid of the temp dir.
            # shutil.rmtree("/tmp/dockerfiles")
        else:
            logging.error("ferry daemon not started")

    def _docker_running(self):
        return os.path.exists('/var/run/ferry.sock')

    def _check_dockerfile(self, dockerfile, repo):
        not_installed = []
        images = self._get_image(dockerfile)
        for image in images:
            qualified = DEFAULT_DOCKER_REPO + '/' + image
            cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' inspect ' + qualified + ' 2> /dev/null'
            output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
            if output.strip() == '[]':
                not_installed.append(image)
        return not_installed

    def _transform_dockerfile(self, image_dir, f, repo):
        if not os.path.exists("/tmp/dockerfiles/" + f):
            shutil.copytree(image_dir + '/' + f, '/tmp/dockerfiles/' + f)
    
        out_file = "/tmp/dockerfiles/" + f + "/Dockerfile"
        out = open(out_file, "w+")
        uid, gid = _get_ferry_user()
        download_url = _get_download_url()
        changes = { "USER" : repo,
                    "DOWNLOAD_URL" : download_url,
                    "DOCKER" : gid }
        for line in open(image_dir + '/' + f + '/Dockerfile', "r"):
            s = Template(line).substitute(changes)
            out.write(s)
        out.close()

    def _build_image(self, image, f, repo, built_images, recurse=False, build=False):
        base = self._get_base(f)
        if recurse and base != "ubuntu:14.04":
            image_dir = os.path.dirname(os.path.dirname(f))
            dockerfile = image_dir + '/' + base + '/Dockerfile'
            self._build_image(base, dockerfile, repo, built_images, recurse, build)

        if not image in built_images:
            if base == "ubuntu:14.04":
                self._pull_image(base)

            built_images[image] = True
            self._compile_image(image, repo, os.path.dirname(f), build)

    def _get_image(self, dockerfile):
        names = []
        for l in open(dockerfile, 'r'):
            if l.strip() != '':
                s = l.split()
                if len(s) > 0:
                    if s[0].upper() == 'NAME':
                        names.append(s[1].strip())
        return names

    def _get_base(self, dockerfile):
        base = None
        for l in open(dockerfile, 'r'):
            s = l.split()
            if len(s) > 0:
                if s[0].upper() == 'FROM':
                    base = s[1].strip().split("/")
                    return base[-1]
        return base

    def _continuous_print(self, process, on_client=True):
        while True:
            try:
                out = process.stdout.read(15)
                if out == '':
                    break
                else:
                    if on_client:
                        sys.stdout.write(out)
                        sys.stdout.flush()
                    else:
                        logging.warning("downloading image...")
            except IOError as e:
                logging.warning(e)

        try:
            errmsg = process.stderr.readline()
            if errmsg and errmsg != '':
                logging.warning(errmsg)
            else:
                logging.warning("downloaded image!")
        except IOError:
            pass

    def _pull_image(self, image, tag=None, on_client=True):
        if not tag:
            cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' pull %s' % image
        else:
            cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' pull %s:%s' % (image, tag)

        logging.warning(cmd)
        child = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        self._continuous_print(child, on_client=on_client)

        # Now tag the image with the 'latest' tag. 
        if tag and tag != 'latest':
            cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' tag' + ' %s:%s %s:%s' % (image, tag, image, 'latest')
            logging.warning(cmd)
            Popen(cmd, stdout=PIPE, shell=True)
        
    def _compile_image(self, image, repo, image_dir, build=False):
        # Now build the image. 
        if build:
            cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' build --rm=true -t' + ' %s/%s %s' % (repo, image, image_dir)
            logging.warning(cmd)
            child = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
            self._continuous_print(child)

            # Now tag the image. 
            cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' tag' + ' %s/%s %s/%s:%s' % (repo, image, repo, image, ferry.__version__)
            logging.warning(cmd)
            child = Popen(cmd, stdout=PIPE, shell=True)
        else:
            # Just pull the image from the public repo. 
            image_name = "%s/%s" % (repo, image)
            self._pull_image(image_name, tag=ferry.__version__)

    def _tag_images(self, image, repo, alternatives):
        for a in alternatives:
            cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' tag' + ' %s/%s:%s %s/%s:%s' % (repo, image, ferry.__version__, repo, a, ferry.__version__)
            logging.warning(cmd)
            child = Popen(cmd, stdout=PIPE, shell=True)
            cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' tag' + ' %s/%s:latest %s/%s:latest' % (repo, image, repo, a)
            logging.warning(cmd)
            child = Popen(cmd, stdout=PIPE, shell=True)

    def _clean_images(self):
        cmd = DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' | grep none | awk \'{print $1}\' | xargs ' + DOCKER_CMD + ' -H=' + DOCKER_SOCK + ' rmi'
        Popen(cmd, stdout=PIPE, shell=True)

    def _is_parent_dir(self, pdir, cdir):
        pdirs = pdir.split("/")
        cdirs = cdir.split("/")

        # Parent directory can never be longer than
        # the child directory. 
        if len(pdirs) > len(cdirs):
            return False
            
        for i in range(0, len(pdirs)):
            # The parent directory shoudl always match
            # the child directory. Ignore the start and end
            # blank spaces caused by "split". 
            if pdirs[i] != "" and pdirs[i] != cdirs[i]:
                return False

        return True

    def _is_running_btrfs(self):
        logging.warning("checking for btrfs")
        cmd = 'cat /etc/mtab | grep btrfs | awk \'{print $2}\''
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
        if output.strip() != "":
            dirs = output.strip().split("\n")
            for d in dirs:
                if self._is_parent_dir(d, DOCKER_DIR):
                    return True
        return False
        
    def _start_docker_daemon(self, options=None):
        # Check if the docker daemon is already running
        try:
            if not self._docker_running():
                bflag = ''
                if self._is_running_btrfs():
                    logging.warning("using btrfs backend")
                    bflag = ' -s btrfs'

                # Explicitly supply the DNS.
                if options and '-n' in options:
                    logging.warning("using custom dns")
                    dflag = ''
                    for d in options['-n']:
                        dflag += ' --dns %s' % d
                else:
                    logging.warning("using public dns")
                    dflag = ' --dns 8.8.8.8 --dns 8.8.4.4'

                # We need to fix this so that ICC is set to false. 
                icc = ' --icc=true'
                cmd = 'nohup ' + DOCKER_CMD + ' -d' + ' -H=' + DOCKER_SOCK + ' -g=' + DOCKER_DIR + ' -p=' + DOCKER_PID + dflag + bflag + icc + ' 1>%s  2>&1 &' % DEFAULT_DOCKER_LOG
                logging.warning(cmd)
                Popen(cmd, stdout=PIPE, shell=True)

                # Wait a second to let the docker daemon do its thing.
                time.sleep(2)
                return True, "Ferry daemon running on /var/run/ferry.sock"
            else:
                return False, "Ferry appears to be already running. If this is an error, please type \'ferry clean\' and try again."
        except OSError as e:
            logging.error("could not start docker daemon.\n") 
            logging.error(e.strerror)
            sys.exit(1)

    def _stop_docker_daemon(self, force=False):
        if force or self._docker_running():
            logging.warning("stopping docker daemon")
            cmd = 'pkill -f docker-ferry'
            Popen(cmd, stdout=PIPE, shell=True)
            try:
                os.remove('/var/run/ferry.sock')
            except OSError:
                pass

    def _get_gateway(self):
        cmd = "LC_MESSAGES=C ifconfig drydock0 | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}'"
        gw = Popen(cmd, stdout=PIPE, shell=True).stdout.read().strip()

        cmd = "LC_MESSAGES=C ifconfig drydock0 | grep 'inet addr:' | cut -d: -f4 | awk '{ print $1}'"
        netmask = Popen(cmd, stdout=PIPE, shell=True).stdout.read().strip()
        mask = map(int, netmask.split("."))
        cidr = 1
        if mask[3] == 0:
            cidr = 8
        if mask[2] == 0:
            cidr *= 2

        return "%s/%d" % (gw, 32 - cidr)
