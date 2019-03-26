# Packer module for Ansible

## Work In Progress

Here are the features that are coming very soon: 

 * Deletion of the old images when the build is done correctly (with a retention parameter)
 * Validation of the json produced before running the build
 * Support for the check_mode (does nothing if an image exists, fails when none were found)
 * Support for the state arg (present, build if image doesn't exist, update build image and erase when successful)
