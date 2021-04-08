#!/usr/bin/env bash

# getting started
python3 -m venv .venv
source .venv/bin/activate
pip install ace2[all]

# first time we install the packages we know about
# this connects to our public github page and gets the list of all the known packages
# it can also use the env var ACE_PACKAGE_URI to get a different custom list
ace2 package install --all

# we could also do this manually though
ace2 package install ace2 package install git@github.com:ace-ecosystem/ace2-modules.git
ace2 package install ace2 package install http://someserver.com/ace2-package.zip
ace2 package install ace2 package install /path/to/ace2-package.zip

# make sure all the packages are up to date
# this also updates all the modules
ace2 package update

# could also do this to just update modules (signatures and such)
ace2 module update

# now I can see what packages I have installed
ace2 package list

# and even see what modules I have available
ace2 module list

# and what services I can start
ace2 service list

# analyze something from the command line
# since we have not specified a core to use
# a temporary in-memory one is created and used
ace2 analyze ipv4 3.127.0.4

# analyze something with a specific analysis module
ace2 analyze ipv4 3.127.0.4 --module whois

#
# PARTICIPATING IN A CORE
#

# specify the core to connect to
export ACE_URI="https://ace2.local/"
export ACE_API_KEY="6a36ffce-507e-469f-8d68-39ca00fa9ccb"

# attach all the modules we have on this system to the remote core
# and start processing requests
ace2 service start manager

#
# REMOTE USAGE OF A CORE
#

# now this command uses the remote core
# since we have our env vars set up
ace2 analyze ipv4 3.127.0.4

# this lists the analysis modules of the remote core
ace2 module list

#
# PRODUCTION COMMANDS
# 

# start a production core system
docker-compose -f ace2-core.yml

# start containers that run the modules
docker-compose -f ace2-modules.yml
