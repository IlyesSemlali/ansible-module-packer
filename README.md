# Ansible Module - Packer

## Description 

## Installation 

## Specs to be excpected shortly

 * Build images
 * Update images with the `packer fix` commmand
 * Ansible best practices


## How it works

This module copies a template file for each clouder on the remote host, then runs a packer validate to see if there any trouble.
It checks wether an image of that name already exists, gets it's ID and if needed it fixes it. 

It returns the ID of the image that has been created
