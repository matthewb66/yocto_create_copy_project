# Synopsys Duplicate Yocto Project Script - yocto_create_copy_project.py
# INTRODUCTION

This script is provided under an OSS license as an example of how to manage Yocto projects.

It does not represent any extension of licensed functionality of Synopsys software itself and is provided as-is, without warranty or liability.

# BACKGROUND

Synopsys Detect v6.0.0+ supports the ability to ingest the dependency tree from a Bitbake build (by invoking `bitbake -g`) and importing components into a Black Duck project for Yocto projects 2.0 and above. However, the OSS component external identifiers from Bitbake reference internal names within the project including the recipe number.

Synopsys uses the OpenEmbedded API to extract component names and create them in the Knowledgebase, however these are currently separate from the upstream components from which Yocto obtain OSS due to the OpenEmbedded non-standard naming, and consequently do not have vulnerabilities associated.

For example consider the component `xrandr/1:1.5.0-r0` reported by Bitbake within a Yocto Warrior project. This would be mapped to the KB component `OpenEmbedded/xrandr/1:1.5.0-r0` in the Black Duck project - the component having been ingested from the OpenEmbedded forge. However, the origin for this component version is actually from a different location and should reference the original `opensuse/libXrandr/1.5.0-1.1`.

The issue with the incorrect component ID in Bitbake is that vulnerabilities are mapped against the original component, and consequently are not automatically associated with the OpenEmbedded component within the Yocto project.

This script is designed to read components from a Black Duck project created by a Detect Bitbake dependency scan, creating manual components which map to the origin in a different Black Duck project. In this way, vulnerability data can be exposed for Yocto projects.

Note that it is planned to map all the OpenEmbedded components to the origins in the Black Duck KnowledgeBase to ensure that vulnerabilities are associated with the Yocto defined components, and that this script would not be required after this is complete.

# DESCRIPTION

The `yocto_create_copy_project.py` script references an existing Black Duck project created from a Bitbake build containing Yocto dependencies, creates a duplicate project (name and version specified) and adds components to the new project by matching the Yocto (OpenEmbedded) components to the original OSS components used for the Yocto build.

The objective is to map security vulnerabilities to a Yocto project - which is currently missing from the project created from the bitbake dependencies.

The script uses a predefined lookup file which maps the bitbake components to their origins. This has been generated for specific Yocto project versions 2.0 and above (including jethro, thud and warrior); not all versions have been mapped and the lookup file will need to be updated for other versions.

# PREREQUISITES

Python 3 and the Black Duck https://github.com/blackducksoftware/hub-rest-api-python package must be installed and configured to enable the Python API scripts for Black Duck prior to using this script.

An API key for the Black Duck server must also be configured in the `.restconfig.json` file in the package folder.

# INSTALLATION

First install the `hub-rest-api-python` package:

    git clone https://github.com/blackducksoftware/hub-rest-api-python.git
    cd hub-rest-api-python
    pip3 install -r requirements.txt
    pip3 install .
    
Extract this GIT repo into a folder (`git clone https://github.com/matthewb66/yocto_create_copy_project`).

Configure the hub connection in the `.restconfig.json` file within the `yocto_create_copy_project` folder - example contents:

    {
      "baseurl": "https://myhub.blackducksoftware.com",
      "api_token": "YWZkOTE5NGYtNzUxYS00NDFmLWJjNzItYmYwY2VlNDIxYzUwOmE4NjNlNmEzLWRlNTItNGFiMC04YTYwLWRBBWQ2MDFlMjA0Mg==",
      "insecure": true,
      "debug": false
    }

# USAGE

The `yocto_create_copy_project.py` script can be invoked as follows:

    usage: python3 yocto_create_copy_project.py import [-h] -p PROJECT -v VERSION -k KBFILE -op
                              OUTPROJECT -ov OUTVERSION [-d]

    optional arguments:
        -h, --help          show this help message and exit
        -p PROJECT, --project PROJECT
                            Input BD project
        -v VERSION, --version VERSION
                            Input BD project version
        -k KBFILE, --kbfile KBFILE
                            Input file of KB component IDs and URLs matching
                            manifest components
        -op OUTPROJECT, --outproject OUTPROJECT
                            Output Black Duck project name
        -ov OUTVERSION, --outversion OUTVERSION
                            Output Black Duck version name
        -d, --delete        Delete existing manual components from the project -
                            if not specified then components will be added to the
                            existing list

# EXAMPLE EXECUTION

Consider the project/version (my_yocto_in/warrior) contains the result of running Detect on a Yocto Warrior project with
components added as dependencies.

Ensure that the script is invoked within the downloaded folder (where the lookup.yocto file exists).

The following command will extract the components from the (my_yocto_in/warrior) project, create a new project
(my_yocto_out/warrior) and copy the components across as original matches:

    python3 yocto_create_copy_project.py import -p my_yocto_in -v warrior -k kblookup.yocto
        -op my_yocto_out -ov warrior

