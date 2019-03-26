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

class PackerModule(AnsibleModule):
    def set_packer_env(self):
        return {
                'OS_REGION_NAME': self.params['region'],
                'OS_AUTH_URL': self.params['provider_auth_url'],
                'OS_USERNAME': self.params['provider_username'],
                'OS_TENANT_ID': self.params['tenant_id'],
                'OS_PASSWORD': self.params['provider_token']
        }

    def get_item_from_json(self, name_key, id_key, value, json_document):
        items = []
        json_object = json.loads(json_document)
        for entry in json_object:
            entry_name = str(entry[name_key])
            entry_id = str(entry[id_key])
            if entry_name.translate(None, string.whitespace) == value.translate(None, string.whitespace):
                items.append(entry_id)
        return items

    def get_existing_images(self):
        openstack_cmd = Popen(['/usr/bin/openstack', 'image', 'list', '--private', '-f', 'json'],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.packer_env)
        out, err = openstack_cmd.communicate()
        return self.get_item_from_json('Name', 'ID', self.params['name'], out)

    def get_image_by_name(self):
        openstack_cmd = Popen(['/usr/bin/openstack', 'image', 'list', '-f', 'json'],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.packer_env)
        out, err = openstack_cmd.communicate()
        #TODO: if rc != 0 fail
        rc = openstack_cmd.returncode

        #TODO: if list empty, fail
        return self.get_item_from_json('Name', 'ID', self.params['base_image'], out)[0]

    def get_network_by_name(self):
        openstack_cmd = Popen(['/usr/bin/neutron', 'net-list', '-f', 'json'],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.packer_env)
        out, err = openstack_cmd.communicate()
        #TODO: if rc != 0 fail
        rc = openstack_cmd.returncode

        #TODO: if list empty, fail
        return self.get_item_from_json('name', 'id', self.params['network_name'], out)[0]

    def make_temp_json(self, name):
        remote_tmp = os.path.expandvars(self._remote_tmp)
        if not os.path.isdir(remote_tmp):
            os.makedirs(remote_tmp)
        fd, path = mkstemp(prefix='ansible-' + name + '.', suffix='.json',
                    dir=remote_tmp
                )
        return fd, path

    def generate_packer_json(self, packer_env, packer_manifest):
        image_id = self.params['base_image_id'] if self.params['base_image_id'] else self.get_image_by_name()
        network_id = self.params['network_id'] if self.params['network_id'] else self.get_network_by_name()

        post_processors = [{
          "type": "manifest",
          "output": packer_manifest,
          "strip_path": 'true'
        }]

        provisioners = [{ }]

        builders = [{
                "type": "openstack",
                "region": str(self.params['region']),
                "image_name": str(self.params['name']),
                "source_image": str(image_id),
                "flavor": str(self.params['flavor']),
                "insecure": "true",
                "ssh_ip_version": "4",
                "networks": [ str(network_id) ],
                "communicator": "ssh",
                "ssh_username": str(self.params['ssh_username']) }]

        data = {
                "builders": builders,
                "post-processors": post_processors
        }
        return json.dumps(data)

    def packer_validate(self):
        packer_cmd = Popen(['/usr/local/bin/packer', 'validate', self.packer_file],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.packer_env)
        out, err = packer_cmd.communicate()
        return packer_cmd.returncode

    def build_image(self):
        packer_cmd = Popen(['/usr/local/bin/packer', 'build', self.packer_file],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.packer_env)
        out, err = packer_cmd.communicate()
        rc = packer_cmd.returncode
        return out
    def delete_old_images(self,image_list):
        openstack_cmd = Popen(['/usr/bin/openstack', 'image', 'delete', image_list],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, env=packer_env)
        out, err = openstack_cmd.communicate()
        rc = openstack_cmd.returncode

        if rc == 0:
            return true
        else:
            return false


    def __init__(self, argument_spec, bypass_checks=False, no_log=False,
                 check_invalid_arguments=None, mutually_exclusive=None, required_together=None,
                 required_one_of=None, add_file_common_args=False, supports_check_mode=False,
                 required_if=None):

        super(PackerModule,self).__init__(argument_spec, bypass_checks, no_log,
                 check_invalid_arguments, mutually_exclusive, required_together,
                 required_one_of, add_file_common_args, supports_check_mode,
                 required_if)

        self.manifest_fd, self.packer_manifest = self.make_temp_json('packer_manifest')
        self.packer_fd, self.packer_file = self.make_temp_json('packer')
        self.packer_env = self.set_packer_env()
        self.packer_data = str(self.generate_packer_json(self.packer_env, self.packer_manifest))

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

    module = PackerModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    result = dict(
        changed=False
    )

    # TODO: Put module's logic inside PackerModule's class
    # Initiate packer environment and files
    with open(module.packer_file, 'w') as f:
        f.write(module.packer_data)
    os.close(module.packer_fd)

    if module.packer_validate() == 0:
        result['output'] = module.build_image()
    else:
        exit(1)

    with open(module.packer_manifest, 'r') as manifest:
        data = json.load(manifest)
    os.close(module.manifest_fd)
    os.remove(module.packer_file)
    os.remove(module.packer_manifest)

    result['image_id'] = data['builds'][0]['artifact_id']
    result['bmah'] = module.get_existing_images()
    module.exit_json(**result)

if __name__ == '__main__':
    main()
