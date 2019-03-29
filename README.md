# Packer module for Ansible

## Work In Progress

Here are the features that are coming very soon: 

 * Deletion of the old images when the build is done correctly (with a retention parameter) - Still need to handle retention
 * Support for the check_mode (return image id if an image exists, fails when none were found)
 * Verbosity options
 * Diff

## Installation

### Manual installation 

In order to get this module working the packer.py file should be placed under one of these locations : 

 * /home/${USER}/.ansible/plugins/modules/action_plugins
 * TODO
 * TODO 
 * ...

## Use it in a playbook

## Supported features

## Limitations

When changing name, there might be an issue with the number of built images, and if you use the default state=present parameter, the image returned may not be the lase one. 

## Contribute 

 * Any kind of contribution is welcome : Don't hesitate to send feedback when something is wrong or missing with this module. 


