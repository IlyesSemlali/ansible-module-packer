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
    state:
        description:
            - "State of the image addressed by ansible, present : build if image doesn't exist, update : build image and erase when successful, absent : deletes all images"
        default: present
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
    provisionners:
        description:
            - Provisionner and it's script to build the image
        requied: false
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

author:
    - Ilyes Semlali (@IlyesSemlali)
'''

EXAMPLES = '''
# Pass in a message
- name: Build CentOS 7
  packer:
    name: MyCentos7
    state: present
    region: 'REG1'
    base_image: 'Centos 7'
    flavor: "s1-2"
    network_name": 'Ext-Net'
    provider_auth_url": "https://auth.example.net/v2.0/",
    provider_token": "RjsFthr98PLnfuTNUNR3HqsxqKCv8RfN",
    provider_username": "UserName",
    ssh_username": "centos",
    tenant_id": "abef5abce681497a8ee5678b2df60ef6"
    provisionners:
      - type: "shell"
        script: "yum install -y nmap-ncat"
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
        try:
            images = self.get_item_from_json('Name', 'ID', self.params['name'], out)
        except:
            try:
                self.clean()
            except:
                pass
            self.fail_json(msg="Unable to get images from openstack client")
        if images:
            return images
        else:
            return []

    def get_images_by_name(self):
        openstack_cmd = Popen(['/usr/bin/openstack', 'image', 'list', '-f', 'json'],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.packer_env)
        out, err = openstack_cmd.communicate()

        try:
            assert openstack_cmd.returncode == 0
            return self.get_item_from_json('Name', 'ID', self.params['base_image'], out)[0]
        except:
            self.fail_json(msg="Error while getting image ID with Openstack client")

    def get_network_by_name(self):
        openstack_cmd = Popen(['/usr/bin/neutron', 'net-list', '-f', 'json'],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.packer_env)
        out, err = openstack_cmd.communicate()

        try:
            assert openstack_cmd.returncode == 0
            return self.get_item_from_json('name', 'id', self.params['network_name'], out)[0]
        except:
            self.fail_json(msg="Error while getting network ID with Openstack client")

    def make_temp_json(self, name):
        remote_tmp = os.path.expandvars(self._remote_tmp)
        if not os.path.isdir(remote_tmp):
            os.makedirs(remote_tmp)
        fd, path = mkstemp(prefix='ansible-' + name + '.', suffix='.json',
                    dir=remote_tmp
                )
        return fd, path

    def generate_packer_json(self):
        image_id = self.params['base_image_id'] if self.params['base_image_id'] else self.get_images_by_name()
        network_id = self.params['network_id'] if self.params['network_id'] else self.get_network_by_name()

        post_processors = [{
          "type": "manifest",
          "output": self.packer_manifest,
          "strip_path": 'true'
        }]

        if self.params['provisionners']:
            provisioners = self.params['provisionners']
        else:
            provisionners = [{}]

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
        if packer_cmd.returncode == 0:
            return True
        else:
            return None

    def write_packer_data(self):
        with open(self.packer_file, 'w') as f:
            f.write(self.packer_data)
        os.close(self.packer_fd)

    def clean(self):
        try:
            os.remove(self.packer_file)
            os.remove(self.packer_manifest)
        except:
            pass

    def build_image(self):
        # Support for check_mode
        if self.check_mode:
            self.diff['after'] == self.image_id
            return "01234567-89ab-cdef-1234-56789abcdef0"

        # Actual build
        try:
            assert self.packer_validate()
        except:
            self.fail_json(msg="Packer file validation failed")


        packer_cmd = Popen(['/usr/local/bin/packer', 'build', self.packer_file],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.packer_env)
        out, err = packer_cmd.communicate()

        try:
            assert packer_cmd.returncode == 0
            with open(self.packer_manifest, 'r') as manifest:
                data = json.load(manifest)
                os.close(self.manifest_fd)
            self.diff['after'] = data['builds'][0]['artifact_id']
            return data['builds'][0]['artifact_id']
        except:
            self.clean()
            self.fail_json(msg="Error while building image")

    def delete_old_images(self):
        if self.check_mode:
            return self.existing_images

        if self.params['state'] == "absent":
            self.image_id = ''

        deleted_images = []

        popen_args = ['/usr/bin/openstack', 'image', 'delete']
        for image in self.existing_images:
            popen_args.append(image)
            deleted_images.append(image)

        openstack_cmd = Popen(popen_args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.packer_env)
        out, err = openstack_cmd.communicate()


        try:
            assert openstack_cmd.returncode == 0
            for image in self.existing_images:
                self.diff['after'].remove(image)
            return deleted_images
        except:
            self.clean()
            self.fail_json(msg="Error while deleting images")

    def check_changes(self):
        # Code is inunderstandable and does not work, gotta get this out
        if set(self.diff['before']) != set(self.diff['after']):
            return True
        else:
            return False

    def __init__(self, argument_spec, bypass_checks=False, no_log=False,
                 check_invalid_arguments=None, mutually_exclusive=None, required_together=None,
                 required_one_of=None, add_file_common_args=False, supports_check_mode=True,
                 required_if=None):

        super(PackerModule,self).__init__(argument_spec, bypass_checks, no_log,
                 check_invalid_arguments, mutually_exclusive, required_together,
                 required_one_of, add_file_common_args, supports_check_mode,
                 required_if)

        self.packer_env = self.set_packer_env()
        self.existing_images = self.get_existing_images()
        self.image_id = ''
        self.manifest_fd, self.packer_manifest = self.make_temp_json('packer_manifest')
        self.packer_fd, self.packer_file = self.make_temp_json('packer')
        self.packer_data = str(self.generate_packer_json())

        # init both before and after, and create diff at each operation (build/delete)
        self.diff = {}
        self.diff['before'] = self.get_existing_images()
        self.diff['after'] = self.get_existing_images()

        if self.existing_images:
            self.image_id = self.get_existing_images()[0]

def main():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', default='present'),
        base_image=dict(type='str', required=False),
        base_image_id=dict(type='str', required=False),
        flavor=dict(type='str', required=True),
        network_id=dict(type='str', required=False),
        network_name=dict(type='str', required=False),
        ssh_username=dict(type='str', required=True),
        provisionners=dict(type='list', required=False),
        region=dict(type='str', required=True),
        tenant_id=dict(type='str', required=True),
        provider_username=dict(type='str', required=True),
        provider_token=dict(type='str', required=True),
        provider_auth_url=dict(type='str', required=False)
    )

    module = PackerModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False
    )

    module.write_packer_data()

    if module.params['state'] == 'present' and not module.image_id:
        module.image_id = module.build_image()
        try:
            module.diff['after'].append(module.image_id)
        except:
            pass

    elif module.params['state'] == 'updated':
        image_id = module.build_image()

        if module.image_id != '':
            deleted_images = module.delete_old_images()
            for image in deleted_images:
                module.diff['after'].remove(image)

        module.image_id = image_id
        module.diff['after'].append(image_id)

    elif module.params['state'] == 'absent':
        if module.image_id != '':
            deleted_images = module.delete_old_images()
            for image in deleted_images:
                module.diff['after'].remove(image)

    result['image_id'] = module.image_id

    if module._diff:
        result['diff'] = module.diff

    result['changed'] = module.check_changes()

    module.clean()
    module.exit_json(**result)

if __name__ == '__main__':
    main()

