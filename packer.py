#!/usr/bin/python

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '0.1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: packer

short_description: Run Packer command to build images

version_added: "2.7"

description:
    - "This module runs packer command to build images on clouds"

options:
    name:
        description:
            - "The name of the image that will be built"
        required: true
    provider_username:
        description:
            - "Username needed to authenticate against specified provider"
        required: true
    provider_token:
        description:
            - "Token/Password needed to authenticate against specified provider"
        required: true
    provider_auth_url:
        description:
            - "URL needed to authenticate against specified provider"
        required: true
    tenant_id:
        description:
            - Tenant or project ID (needed for OpenStack)
        required: true
    base_image_id:
        description:
            - "Image ID from which packer will build"
        required: false
    base_image:
        description:
            - "Image name from which packer will build (base_image_id won't be used when this parameter is defined)"
        required: false
    flavor:
        description:
            - "Flavor used to build new image"
        required: true
    region:
        description:
            - "Region name where the image will be built"
        required: true
    network_name:
        description:
            - "Network need in order to update the image (netowrk_id won't be used when this parameter is defined)"
        required: false
    network_id:
        description:
            - "Network ID need in order to update the image"
        required: false
    ssh_username:
        description:
            - "User needed to provision the image that will be built"
        required: true
    update:
        description:
            - Wether to update an existing image or not
        required: false

author:
    - Ilyes Semlali (@IlyesSemlali)
'''

EXAMPLES = '''
# Pass in a message
- name: Build CentOS 7
  packer:
    name: MyCentos7
    region: 'REG1'
    base_image: 'Centos 7'
    flavor: "s1-2"
    network_name": 'Ext-Net'
    provider_auth_url": "https://auth.example.net/v2.0/",
    provider_token": "RjsFthr98PLnfuTNUNR3HqsxqKCv8RfN",
    provider_username": "UserName",
    ssh_username": "centos",
    tenant_id": "abef5abce681497a8ee5678b2df60ef6"
'''

RETURN = '''
image_id:
    description: Freshly built or updated image ID
    type: str
'''

import re
import json
import os
import string
from string import maketrans
from subprocess import Popen, PIPE
from ansible.module_utils.basic import AnsibleModule
from tempfile import mkstemp, mkdtemp
from ansible.plugins import AnsiblePlugin
from ansible.plugins.lookup import LookupBase
from ansible.plugins.lookup import config

def get_item_from_json(name_key,id_key,value,json_document):
    json_object = json.loads(json_document)
    for entry in json_object:
        entry_name = str(entry[name_key])
        entry_id = str(entry[id_key])
        if entry_name.translate(None, string.whitespace) == value.translate(None, string.whitespace):
            return entry_id
    return ""

#def get_existing_image(module):
#    openstack_cmd = Popen(['/usr/bin/openstack', 'image', 'list', '--private', '-f', 'json',
#            '--os-username', module.params['provider_username'],
#            '--os-auth-url', module.params['provider_auth_url'],
#            '--os-password', module.params['provider_token'],
#            '--os-project-id', module.params['tenant_id'],
#            '--os-region-name', module.params['region']
#        ], stdin=PIPE, stdout=PIPE, stderr=PIPE)
#    out, err = openstack_cmd.communicate()
#    return get_item_from_json('Name', module.params['name'], out)

def get_image_by_name(module):
    openstack_cmd = Popen(['/usr/bin/openstack', 'image', 'list', '-f', 'json',
            '--os-username', module.params['provider_username'],
            '--os-auth-url', module.params['provider_auth_url'],
            '--os-password', module.params['provider_token'],
            '--os-project-id', module.params['tenant_id'],
            '--os-region-name', module.params['region']
        ], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    out, err = openstack_cmd.communicate()
    return get_item_from_json('Name', 'ID', module.params['base_image'], out)

def get_network_by_name(module):
    openstack_cmd = Popen(['/usr/bin/neutron', 'net-list', '-f', 'json',
            '--os-username', module.params['provider_username'],
            '--os-auth-url', module.params['provider_auth_url'],
            '--os-password', module.params['provider_token'],
            '--os-project-id', module.params['tenant_id'],
            '--os-region-name', module.params['region']
        ], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    out, err = openstack_cmd.communicate()
    rc = openstack_cmd.returncode

#    if rc == 0:
    return get_item_from_json('name', 'id', module.params['network_name'], out)

def make_temp_json(module,name):
    remote_tmp = os.path.expandvars(module._remote_tmp)
    if not os.path.isdir(remote_tmp):
        os.makedirs(remote_tmp)
    fd, path = mkstemp(prefix='ansible-' + name + '.', suffix='.json',
                dir=remote_tmp
            )
    return fd, path

def generate_packer_json(module,packer_manifest):
    image_id = module.params['base_image_id'] if module.params['base_image_id'] else get_image_by_name(module)
    network_id = module.params['network_id'] if module.params['network_id'] else get_network_by_name(module)

    post_processors = [{
      "type": "manifest",
      "output": packer_manifest,
      "strip_path": 'true'
    }]

    provisioners = [{ }]

    builders = [{
            "type": "openstack",
            "region": str(module.params['region']),
            "image_name": str(module.params['name']),
            "source_image": str(image_id),
            "flavor": str(module.params['flavor']),
            "insecure": "true",
            "ssh_ip_version": "4",
            "networks": [ str(network_id) ],
            "communicator": "ssh",
            "ssh_username": str(module.params['ssh_username']) }]

    data = {
            "builders": builders,
            "post-processors": post_processors
    }
    return json.dumps(data)

def set_packer_env(module):
    return {
            'OS_REGION_NAME': module.params['region'],
            'OS_AUTH_URL': module.params['provider_auth_url'],
            'OS_USERNAME': module.params['provider_username'],
            'OS_TENANT_ID': module.params['tenant_id'],
            'OS_PASSWORD': module.params['provider_token']
    }

def packer_validate(module, packer_env, packer_file, packer_manifest):
    packer_cmd = Popen(['/usr/local/bin/packer', 'validate', packer_file ],
            stdin=PIPE, stdout=PIPE, stderr=PIPE, env=packer_env)
    out, err = packer_cmd.communicate()
    return packer_cmd.returncode

def build_image(module, packer_env, packer_file, packer_manifest):
    packer_cmd = Popen(['/usr/local/bin/packer', 'build', packer_file ],
            stdin=PIPE, stdout=PIPE, stderr=PIPE, env=packer_env)
    out, err = packer_cmd.communicate()
    rc = packer_cmd.returncode

#def delete_old_image():

def main():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        base_image=dict(type='str', required=False),
        base_image_id=dict(type='str', required=False),
        flavor=dict(type='str', required=True),
        network_id=dict(type='str', required=False),
        network_name=dict(type='str', required=False),
        ssh_username=dict(type='str', required=True),
        region=dict(type='str', required=True),
        tenant_id=dict(type='str', required=True),
        provider_username=dict(type='str', required=True),
        provider_token=dict(type='str', required=True),
        provider_auth_url=dict(type='str', required=False)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    result = dict(
        changed=False
    )

    # Initiate packer environment and files
    manifest_fd, packer_manifest = make_temp_json(module,'packer_manifest')
    packer_data = str(generate_packer_json(module,packer_manifest))
    packer_fd, packer_file = make_temp_json(module,'packer')
    packer_env = set_packer_env(module)

    with open(packer_file, 'w') as f:
        f.write(packer_data)
    os.close(packer_fd)

    if packer_validate(module, packer_env, packer_file, packer_manifest) == 0:
        build_image(module, packer_env, packer_file, packer_manifest)
    else:
        exit(1)

    with open(packer_manifest) as manifest:
        data = json.load(manifest)
    os.close(manifest_fd)
    os.remove(packer_file)
    os.remove(packer_manifest)

    result['image_id'] = data['builds'][0]['artifact_id']

    module.exit_json(**result)

if __name__ == '__main__':
    main()
