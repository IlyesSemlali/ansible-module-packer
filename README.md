# Packer module for Ansible

## Work In Progress

Here are the features that are coming very soon: 

 * Deletion of the old images when the build is done correctly (with a retention parameter) - Still need to handle retention
 * Validation of the json produced before running the build - GOOD
 * Support for the check_mode (return image id if an image exists, fails when none were found)
 * Support for the state arg (present : build if image doesn't exist, update : build image and erase when successful, absent : deletes all images)

## Installation

## Use it in a playbook

## Supported features

## Limitations

## Contribute 

 * Any kind of contribution is welcome : Don't hesitate to send feedback when something is wrong or missing with this module. 
