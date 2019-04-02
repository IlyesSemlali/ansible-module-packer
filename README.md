# Packer module for Ansible

## Requirements

This module works with the `openstack` client and the `neutron` clients. 

```shell
pip install python-openstackclient neutron
```

## Installation

In order to get this module working the packer.py file should be placed under one of these locations : 

 * /home/${USER}/.ansible/plugins/modules/action_plugins
 * /usr/share/ansible/plugins/modules/action_plugins
 * $ANSIBLE_LIBRARY/action_plugins

(As precised in the [official documentation](docs.ansible.com/ansible/latest/dev_guide/developing_locally.html) )

## Use it in a playbook

```yaml
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
```

For advanced users, you can use the `no_clean` parameter (set to true), in order to see how the packer file looks like in the ansible_tmp folder. 

## Supported features

 * provisionners
 * check_mode
 * diff_mode
 * Cloud provider : OpenStack (the only supported cloud provider for now)

## Work In Progress

Here are the features that are coming very soon: 

 * Verbosity options

## Contribute 

 * Any kind of contribution is welcome : Don't hesitate to send feedback when something is wrong or missing with this module. 

