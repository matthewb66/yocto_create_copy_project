# Synopsys Duplicate Yocto Project Script - yocto_create_copy_project.py
# INTRODUCTION

This script is provided under an OSS license as an example of how to manage Yocto projects.

It does not represent any extension of licensed functionality of Synopsys software itself and is provided as-is, without warranty or liability.

# BACKGROUND

Synopsys Detect v6.0.0+ supports the ability to ingest the dependency tree from a Bitbake build (by invoking `bitbake -g`) and importing components into a Black Duck project (for Yocto versions 2.0 and above). However, Bitbake uses non-standard OSS component external identifiers including the recipe number which are used to query the OpenEmbedded API to extract component names and create them in the Knowledgebase. This means that OSS components extracted from Bitbake are separate from the upstream components within the KB (where Yocto obtains the original OSS from) due to the OpenEmbedded non-standard naming, and consequently do not have vulnerabilities associated.

For example consider the component `xrandr/1:1.5.0-r0` reported by Bitbake within a Yocto Warrior project. This would be mapped to the KB component `OpenEmbedded/xrandr/1:1.5.0-r0` in the Black Duck project - the component having been ingested from the OpenEmbedded forge. However, the origin for this component version is actually from a different location and should reference the original `opensuse/libXrandr/1.5.0-1.1`.

The issue with the incorrect component ID in Bitbake is that vulnerabilities are mapped against the original component, and consequently are not automatically associated with the OpenEmbedded component within the Yocto project.

This script is designed to read components from a Black Duck project created by a Detect Bitbake dependency scan, creating manual components which map to the origin in a different Black Duck project. In this way, vulnerability data can be exposed for Yocto projects.

Note that it is planned to map all the OpenEmbedded components to the origins in the Black Duck KnowledgeBase to ensure that vulnerabilities are associated with the Yocto defined components, and that this script would not be required after this is complete.

# DESCRIPTION

The `yocto_create_copy_project.py` script references an existing Black Duck project created from a Bitbake build containing Yocto dependencies, creates a duplicate project (name and version specified) and adds components to the new project by matching the Yocto (OpenEmbedded) components to the original OSS components used for the Yocto build.

The objective is to map security vulnerabilities to a Yocto project - which is currently missing from the project created from the Bitbake dependencies.

It has 2 modes of operation which are required to be executed in sequence for each import activity.

The first mode (`kblookup`) reads the list of components from the input project/version to create an output file of KB lookup matches for the components, also reporting a list of non-matches. Note that the script stops at 500 input components in order to avoid a timeout of the API connection session (20 minutes). The script can be re-run on the same import project/version if more than 500 components need to be processed.

The output KB lookup file created by kblookup mode can then be reviewed and supplemented manually to replace or add components to ensure correct matches during the import phase.

The second mode (`import`) reads the input project/version and the KB match file to add manual components to the specified Black Duck project/version.

The following diagram explains the flow of data for the 2 modes:

![](https://github.com/matthewb66/import_manifest/blob/master/images/im_process_map.png)

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

The `yocto_create_copy_project.py` script must be invoked with one of the 2 modes kblookup or import as shown in the usage text below:

    usage: yocto_create_copy_project [-h] {kblookup,import} ...
	
    Import components from inpurt project and copy to output project/version

    positional arguments:
 	 {kblookup,import}  Choose operation mode
    kblookup         Process component list to find matching KB URLs & export to
                     file
    import           Import component list into specified Black Duck
                     project/version using KB URLs from supplied file

    optional arguments:
       -h, --help       show this help message and exit

## kblookup Mode

The `kblookup` mode requires an input project/version. An optional output KB Lookup File can be specified (if not specified the default filename `kblookup.out` will be used). Additionally, an input KB Lookup File can optionally be specified which will be used to reuse previous matches, and the `-a` (or `--append`) option would ensure that all entries from the input KB Lookup File are copied to the output KB Lookup file (without this option, only components found in the input project/version would be output).

Note that `kblookup` mode stops at 500 components in order to stop a timeout of the API connection session (20 minutes). The script can be re-run in `kblookup` mode appending to the output KB Lookup file as many times as necessary on the same input project/version to match more than 500 components provided the output KB Lookup file is specified as input (`-k kbfile`).

Usage for kblookup mode is:

    Usage: import_manifest kblookup [-h] [-k KBFILE] [-o OUTPUT] [-r REPLACE_PACKAGE_STRING] -p PROJECT -v VERSION [-a]

Further explanation of options for kblookup mode is provided below:

    -p PROJECT, --project PROJECT
                        REQUIRED Black Duck project name; if project does not exist (and API user has Global Project Creator permission) then a new project will be created.

    -v VERSION, --version VERSION
                        REQUIRED Black Duck version name; if version does not exist then new version will be created.

    -k KBFILE, --kbfile KBFILE
                        OPTIONAL input KB Lookup file which will be used to search for components. Should be specified when kblookup mode has been used previously on a project which has changed or a similar project and you want to reduce the scan time using existing matches. 

    -o OUTPUT, --output OUTPUT
                        OPTIONAL output KB Lookup File (if not specified then the default value of kblookup.out will be used). Should be used when the script has been used previously on this project which has changed, or a similar project and you want to reduce the scan time using existing matches. Note that the file name can be the same as the -k file option; the file will be read and appended to.

    -r REPLACE_PACKAGE_STRING, --replace_package_string REPLACE_PACKAGE_STRING
                        OPTIONAL string REPLACE_PACKAGE_STRING will be stripped from the input package names (can be specified multiple times)

    -a, --append
                        OPTIONAL If specified, all records from the input KB Lookup file (specified by -k) will be copied the output KB Lookup file specified by -o (kblookup.out by default). If this option is not specified, then only entries for components in the component list will be exported to the output KB Lookup file.

## import Mode

The `import` mode requires a component list file and a KB Lookup File to be specified and will lookup the components in the KB Lookup File to add new manual components to the specified Black Duck project/version (which can be created by the script if they do not already exist subject to permissions).

The full list of options in import mode can be displayed using the command:

    import_manifest.py import -h

The usage for import mode is:

    usage: import_manifest import [-h] -k KBFILE -p INPUT_PROJECT -v INPUT_VERSION -op OUTPUT_PROJECT -ov OUTPUT_VERSION

Further explanation of options for import mode:

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

Consider the project/version (`my_yocto_in/warrior`) contains the result of running Detect on a Yocto Warrior project with
components added as dependencies.

The first command to run will extract the components from the (`my_yocto_in/warrior`) project and create a kblookup file (`kblookup.yocto`):

    python3 yocto_create_copy_project.py kblookup -p my_yocto_in -v warrior -o kblookup.yocto

The second command will extract the components from the (`my_yocto_in/warrior`) project, create a new project
(`my_yocto_out/warrior`) and copy components across as original KB matches where found using the kblookup file from the first run:

    python3 yocto_create_copy_project.py import -p my_yocto_in -v warrior -k kblookup.yocto
        -op my_yocto_out -ov warrior

# USAGE AFTER RESCAN

If you rescan an existing project using Detect to export dependencies from Bitbake and updating an existing Black Duck project/version, then you can use the `yocto_create_copy_project.py` script to update the existing output project/version.

You would need to first rerun the `kblookup` mode on the input project/version, but specify the `-k kblookup.yocto` option to process the existing kblookup file from the previous run, for example:

    python3 yocto_create_copy_project.py kblookup -p my_yocto_in -v warrior -k kblookup.yocto -o kblookup.new

Then rerun `import` mode using the new kblookup file and specifying the `-d` (delete) option to remove components in the output project/version which no longer exist:

    python3 yocto_create_copy_project.py import -p my_yocto_in -v warrior -k kblookup.new
        -op my_yocto_out -ov warrior -d
