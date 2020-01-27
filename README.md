# Synopsys Duplicate Yocto Project Script - find_matching_KB_component_from_bom_yocto.py
# INTRODUCTION

This script is provided under an OSS license as an example of how to manage Yocto projects.

It does not represent any extension of licensed functionality of Synopsys software itself and is provided as-is, without warranty or liability.

# BACKGROUND

Synopsys Detect v6.0.0+ supports the ability to ingest the dependency tree from a Bitbake build (by invoking `bitbake -g`) and importing components into a Black Duck project. However, the OSS component external identifiers from Bitbake reference  internal names within the project including the recipe number.

Synopsys uses the OpenEmbedded API to extract component names and create them in the Knowledgebase, however these are currently separate from the upstream components from which Yocto obtain OSS and consequently do not have vulnerabilities associated.

For example consider the component `xrandr/1:1.5.0-r0` reported by Bitbake within a Yocto Warrior project. This would be mapped to the KB component `OpenEmbedded/xrandr/1:1.5.0-r0` in the Black Duck project - the component having been ingested from the OpenEmbedded forge. However, the origin for this component version is actually from a different location and should reference the original `xrandr/1.5.0`.

The issue with the incorrect component ID in Bitbake is that any vulnerabilities mapped against the original, and consequently are not automatically associated with the OpenEmbedded component within the Yocto project.

This script is designed to read components from a Black Duck project created by a Detect Bitbake dependency scan, creating manual components which map to the origin in a different Black Duck project. In this way, vulnerability data can be exposed for Yocto projects. Note that there is a plan 

# DESCRIPTION

The `find_matching_KB_component_from_bom_yocto.py` script references an existing Black Duck project created from a Bitbake build containing Yocto dependencies, creates a duplicate project (name and version specified) and copies the Yocto (OpenEmbedded) components across to the new project matching the original OSS components used for the Yocto versions.

The objective is to map security vulnerabilities to a Yocto project - which is currently missing from the Bitbake generated project.

The script uses 

# PREREQUISITES

Python 3 and the Black Duck https://github.com/blackducksoftware/hub-rest-api-python package must be installed and configured to enable the Python API scripts for Black Duck prior to using this script.

An API key for the Black Duck server must also be configured in the `.restconfig.json` file in the package folder.

# INSTALLATION

Install the hub-rest-api-python package:

    git clone https://github.com/blackducksoftware/hub-rest-api-python.git
    cd hub-rest-api-python
    pip3 install -r requirements.txt
    pip3 install .
    
Copy the `ignore_snippets.py` script into the `examples` sub-folder within `hub-rest-api-python`.

Configure the hub connection in the `.restconfig.json` file within `hub-rest-api-python` - example contents:

    {
      "baseurl": "https://myhub.blackducksoftware.com",
      "api_token": "YWZkOTE5NGYtNzUxYS00NDFmLWJjNzItYmYwY2VlNDIxYzUwOmE4NjNlNmEzLWRlNTItNGFiMC04YTYwLWRBBWQ2MDFlMjA0Mg==",
      "insecure": true,
      "debug": false
    }

# USAGE

The `ignore_snippets.py` script can be invoked as follows:

    usage: ignore_snippets.py [-h] [-s SCOREMIN] [-c COVERAGEMIN]
                               [-z SIZEMIN] [-l MATCHEDLINESMIN] [-r] [-u]
                               project_name version
                               
    Ignore (or unignore) snippets int he specified project/version using the supplied
    options. Running with no options apart from project and version will cause all
    snippets to be ignored.

    positional arguments:
        project_name          Black Duck project name
        version               Black Duck version name

    optional arguments:
        -h, --help            show this help message and exit
        -s SCOREMIN, --scoremin SCOREMIN
                              Minimum match score percentage value (hybrid value of
                              snippet match and likelihood that component can be
                              copied)
       -c COVERAGEMIN, --coveragemin COVERAGEMIN
                              Minimum matched lines percentage
       -z SIZEMIN, --sizemin SIZEMIN
                              Minimum source file size (in bytes)
       -l MATCHEDLINESMIN, --matchedlinesmin MATCHEDLINESMIN
                              Minimum number of matched lines from source file
       -r, --report          Report the snippet match values, do not
                              ignore/unignore
       -u, --unignore        Unignore matched snippets (undo ignore action)

# EXAMPLE EXECUTION

The example project/version (partisan-snippets/1.0) contains 4 unignored/unconfirmed snippets.

The --report option will list the snippet match values for all snippets (but will not ignore/unignore):

    python3 examples/MRB_ignore_snippets2.py partisan-snippets 1.0 --report
    
    File: myfile.erl (size = 7149)
        Block 1: matchScore = 37%, matchCoverage = 51%, matchedLines = 97 - Would be ignored
    File: partisan_acknowledgement_backend.erl (size = 3143)
        Block 1: matchScore = 42%, matchCoverage = 24%, matchedLines = 12 - Would be ignored
    File: partisan_analysis.erl (size = 42006)
        Block 1: matchScore = 35%, matchCoverage = 1%, matchedLines = 12 - Would be ignored
    File: partisan_app.erl (size = 1231)
        Block 1: matchScore = 54%, matchCoverage = 100%, matchedLines = 38 - Would be ignored

Running the script specifying just the project and version name will cause all snippets to be ignored:

    python3 examples/ignore_snippets.py partisan-snippets 1.0
    
    File: myfile.erl - Ignored
    File: partisan_acknowledgement_backend.erl - Ignored
    File: partisan_analysis.erl - Ignored
    File: partisan_app.erl - Ignored

Specifying the --unignore (or -u) option will cause all snippets to be UNignored:

    python3 examples/ignore_snippets.py partisan-snippets 1.0 --unignore
    
    File: myfile.erl - Unignored
    File: partisan_acknowledgement_backend.erl - Unignored
    File: partisan_analysis.erl - Unignored
    File: partisan_app.erl - Unignored
    
The following examples ignores snippets with a maximum coverage (matched line percentage) of 50% and a maximum matched line count of 20:

    python3 examples/MRB_ignore_snippets2.py partisan-snippets 1.0 -c 50 -l 20

    File: partisan_acknowledgement_backend.erl - Ignored
    File: partisan_analysis.erl - Ignored
