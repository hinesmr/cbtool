#!/usr/bin/env python
#/*******************************************************************************
# Copyright (c) 2012 IBM Corp.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#/*******************************************************************************
#--------------------------------- START CB API --------------------------------

from sys import path, argv
from time import sleep

import fnmatch
import os
import pwd

home = os.environ["HOME"]
username = pwd.getpwuid(os.getuid())[0]

api_file_name = "/tmp/cb_api_" + username
if os.access(api_file_name, os.F_OK) :    
    try :
        _fd = open(api_file_name, 'r')
        _api_conn_info = _fd.read()
        _fd.close()
    except :
        _msg = "Unable to open file containing API connection information "
        _msg += "(" + api_file_name + ")."
        print _msg
        exit(4)
else :
    _msg = "Unable to locate file containing API connection information "
    _msg += "(" + api_file_name + ")."
    print _msg
    exit(4)

_path_set = False

for _path, _dirs, _files in os.walk(os.path.abspath(path[0] + "/../")):
    for _filename in fnmatch.filter(_files, "code_instrumentation.py") :
        if _path.count("/lib/auxiliary") :
            path.append(_path.replace("/lib/auxiliary",''))
            _path_set = True
            break
    if _path_set :
        break

from lib.api.api_service_client import *

_msg = "Connecting to API daemon (" + _api_conn_info + ")..."
print _msg
api = APIClient(_api_conn_info)

#---------------------------------- END CB API ---------------------------------

if len(argv) < 2 :
        print "./" + argv[0] + " <cloud_name>"
        exit(1)

cloud_name = argv[1]

try :
    _error = False

    _update_interval = 5
    
    _total_vms_on_the_cloud = 10
    _initial_provision_load = .6
    _variable_provision_load = .8
    
    _total_run_time = 600

    _start_time = time()

    _msg = "Attaching all VMCs...."
    print _msg
    _key = "all_vmcs_attached"
    print _key + '=' + api.vmcattach(cloud_name, "all")["all_vmcs_attached"]
    
    _msg = "Changing the experiment identifier..."
    print _msg
    print api.expid(cloud_name, "loadrange")

    _msg = "Deploying the initial Vapp Submitter that will be used to take the"
    _msg += " to a predefined minimum provision load level..."
    print (_msg)

    _actual_initial_provision_load = int(_total_vms_on_the_cloud * _initial_provision_load)
    _actual_variable_provision_load  = int(_total_vms_on_the_cloud * _variable_provision_load)

    api.patternalter(cloud_name, "simplenw", "max_ais", str(_actual_initial_provision_load))
    api.patternalter(cloud_name, "simplenw", "iait", "10")

    # These VMs are "immortal" :-)
    api.patternalter(cloud_name, "simplenw", "lifetime", "100000")    

    _vapps_name = api.appdrsattach(cloud_name, "simplenw")["name"]

    _msg = "VApp Submitter \"" + _vapps_name + "\" deployed. Will now wait until"
    _msg += " the number of VMs provisioned reaches "
    _msg += str(int(_total_vms_on_the_cloud * _initial_provision_load)) + "...."
    print _msg

    _provisioned_vms = int(api.stats(cloud_name)[2][3][2][1])

    while _provisioned_vms < int(_actual_initial_provision_load) :
        _current_time = int(time() - _start_time)
        _msg = "Number of provisioned VMs is " + str(_provisioned_vms) 
        _msg += " after " + str(_current_time) + " seconds"
        print _msg
        sleep(_update_interval)
        _provisioned_vms = int(api.stats(cloud_name)[2][3][2][1])

    _msg = "Number of VMs deployed is equal the minimum provision load ("
    _msg += str(_actual_initial_provision_load) + ")."
    _msg += " Stopping the first VappSubmmiter (" + _vapps_name + ") and "
    _msg += "deploying a second to implement a variable provisioning load..."
    print _msg

    api.appdrsdetach(cloud_name, _vapps_name)

    api.patternalter(cloud_name, "simplenw", "max_ais", str(_actual_variable_provision_load - _actual_initial_provision_load))
    # Here we want a burst of long-lived (but not "immortal" VMs
    api.patternalter(cloud_name, "simplenw", "iait", "5")
    api.patternalter(cloud_name, "simplenw", "lifetime", "80")

    _vapps_name = api.appdrsattach(cloud_name, "simplenw")["name"]

    while _current_time < _total_run_time :
        _provisioned_vms = int(api.stats(cloud_name)[2][3][2][1])

        while _provisioned_vms < int(_actual_variable_provision_load) :
            _current_time = int(time() - _start_time)
            _msg = "Number of provisioned VMs is " + str(_provisioned_vms) 
            _msg += " after " + str(_current_time) + " seconds"
            print _msg
            sleep(_update_interval)
            _provisioned_vms = int(api.stats(cloud_name)[2][3][2][1])    

        _msg = "Number of VMs deployed is equal the maximum provision load ("
        _msg += str(_actual_variable_provision_load) + ")."
        _msg += " Stopping the second VappSubmmiter (" + _vapps_name + ") and "
        _msg += "waiting for some VMs to be naturally removed..."
        print _msg
        
        api.statealter(cloud_name, _vapps_name, "stopped")

        for _obj in api.stateshow(cloud_name) :
            if _obj["name"] == _vapps_name :
                print _obj["name"] + " is " + _obj["state"]
    
        while _provisioned_vms > int(_actual_initial_provision_load) :
            _current_time = int(time() - _start_time)
            _msg = "Number of provisioned VMs is " + str(_provisioned_vms) 
            _msg += " after " + str(_current_time) + " seconds"
            print _msg
            sleep(_update_interval)
            _provisioned_vms = int(api.stats(cloud_name)[2][3][2][1])
    
        _msg = "Number of VMs deployed is equal the minimum provision load ("
        _msg += str(_actual_initial_provision_load) + ") again."
        _msg += " Re-activating the second VappSubmmiter (" + _vapps_name + ") and "
        _msg += "waiting for some VMs to be provisioned again..."
        print _msg

        api.statealter(cloud_name, _vapps_name, "attached")

        for _obj in api.stateshow(cloud_name) :
            if _obj["name"] == _vapps_name :
                print _obj["name"] + " is " + _obj["state"]

except APIException, obj :
    error = True
    print "API Problem (" + str(obj.status) + "): " + obj.msg

except APINoSuchMetricException, obj :
    error = True
    print "API Problem (" + str(obj.status) + "): " + obj.msg

except KeyboardInterrupt :
    print "Aborting this VM."

except Exception, msg :
    error = True
    print "Problem during experiment: " + str(msg)

finally :
        if _error :
            exit(1)
        else :
            exit(0)
