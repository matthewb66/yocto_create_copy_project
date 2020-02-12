#!/usr/bin/env python
#
# Modified import_manifest to (mode 1) extract components & versions from a BD project/version created from a Detect scan of a Yocto project, 
# then (mode 2) create a new project with manually added components which match the original.
#
# This script operates in 2 modes as follows:
# 1. Mode kblookup: Accept BD project & version, read list of components & versions from the project, producing an output list of BD URLs for KB components which match the component
#    name and version
# 2. Mode import: Accept BD project & version, seed file, project name and version - Read list of components & version from the input file in addition to a seed file of BD URLs
#    (produced by mode 1), find matching KB component & version and (if not already in project) add as manual component to specified project & version

import argparse
#import json
import logging
import re
from difflib import SequenceMatcher

from blackduck.HubRestApi import HubInstance

logging.basicConfig(filename='MRB_import_yocto_manifest.log',level=logging.DEBUG)

hub = HubInstance()

def get_kb_component(packagename):
    #print("DEBUG: processing package {}".format(packagename))
    packagename = packagename.replace(" ", "+")
    #packagename = packagename.replace("-", "+")
    req_url = hub.get_urlbase() + "/api/search/components?q=name:{}&limit={}".format(packagename, 20)
    try:
        response = hub.execute_get(req_url)
    except:
        logging.error("get_kb_component(): Exception trying to find KB matches")
        
    if response.status_code != 200:
        logging.error("Failed to retrieve KB matches, status code: {}".format(response.status_code))
    return response

def find_ver_from_compver(kburl, version):
    matchversion = ""
    
    component = hub.execute_get(kburl)            
    if component.status_code != 200:
        logging.error("Failed to retrieve component, status code: {}".format(component.status_code))
        return "", "", 0, "", ""
    bdcomp_sourceurl = component.json().get('url')
    if bdcomp_sourceurl:
        bdcomp_sourceurl = bdcomp_sourceurl.replace(';','')
    #
    # Request the list of versions for this component
    compname = component.json().get('name')
    respitems = component.json().get('_meta')
    links = respitems['links']
    vers_url = links[0]['href'] + "?limit=1000"
    kbversions = hub.execute_get(vers_url)           
    if kbversions.status_code != 200:
        logging.error("Failed to retrieve component, status code: {}".format(kbversions.status_code))
        return "", "", 0, "", ""

    localversion = version.replace('-','.')
    for kbversion in kbversions.json().get('items'):

        kbversionname = kbversion['versionName'].replace('-', '.')
        kbver_url = kbversion['_meta']['href']
        logging.debug("DEBUG: component = {} searchversion = {} kbver = {} kbverurl = {}".format(compname, version, kbversionname, kbver_url))
        if (kbversionname == localversion):
            # exact version string match
            matchversion = kbversion['versionName']
            matchstrength = 3
            break                

        # Need to look for partial matches
        seq = SequenceMatcher(None, kbversionname, localversion)
        match = seq.find_longest_match(0, len(kbversionname), 0, len(localversion))
        if (match.a == 0) and (match.b == 0) and (match.size == len(kbversionname)):
            # Found match of full kbversion at start of search_version
            if len(kbversionname) > len(matchversion):
                # Update if the kbversion is longer than the previous match
                matchversion = kbversion['versionName']
                matchstrength = 2
                logging.debug("Found component block 1 - version="+ matchversion)

        elif (match.b == 0) and (match.size == len(localversion)):
            # Found match of full search_version within kbversion
            # Need to check if kbversion has digits before the match (would mean a mismatch)
            mob = re.search('\d', kbversionname[0:match.a])
            if not mob and (len(kbversionname) > len(matchversion)):
                # new version string matches kbversion but with characters before and is longer than the previous match
                matchversion = kbversion['versionName']
                logging.debug("Found component block 2 - version="+ matchversion)
                if (match.a == 1) and (kbversionname.lower() == 'v' ):  # Special case of kbversion starting with 'v'
                    matchstrength = 3
                else:
                    matchstrength = 2

        elif (match.a == 0) and (match.b == 0) and (match.size > 2):
            # both strings match at start for more than 2 characters min
            # Need to try close numeric version match
            # - Get the final segment of searchversion & kbversion
            # - Match if 2 versions off?          
            if 0 <= match.size - localversion.rfind(".") <= 2:
                # common matched string length is after final .
                kbfinalsegment = kbversionname.split(".")[-1]
                localfinalsegment = localversion.split(".")[-1]
                if (kbfinalsegment.isdigit() and localfinalsegment.isdigit()):
                    # both final segments are numeric
                    logging.debug("kbfinalsegment = " + kbfinalsegment + " localfinalsegment = " + localfinalsegment + " matchversion = " + matchversion)
                    if abs(int(kbfinalsegment) - int(localfinalsegment)) <= 2:
                        # values of final segments are within 2 of each other
                        if len(kbversionname) >= len(matchversion):
                            # kbversion is longer or equal to matched version string 
                            matchversion = kbversion['versionName']
                            matchstrength = 1
                            logging.debug("Found component block 3 - version="+ matchversion)
                                  
    if matchversion != "":
        return compname, matchversion, matchstrength, bdcomp_sourceurl, kbver_url
    
    return "", "", 0, "", ""

def find_ver_from_hits(hits, search_version):
    matchversion = ""
    matchstrength=0
    for hit in hits:
        #
        # Get component from URL
        comp_url = hit['component']
        compname, matchversion, matchstrength, bdcomp_sourceurl, bdcompver_url = find_ver_from_compver(comp_url, search_version)
        if matchstrength == 3:
            break

    if matchversion == "":
        return "", "", 0, "", "", ""
    else:
        return compname, matchversion, matchstrength, bdcomp_sourceurl, comp_url, bdcompver_url


def search_kbpackage(package):    
    response = get_kb_component(package)
    if response.status_code != 200:
        print("error")
        return ""
    
    respitems = response.json().get('items', [])
    logging.debug("{} items returned".format(respitems[0]['searchResultStatistics']['numResultsInThisPage']))
    if respitems[0]['searchResultStatistics']['numResultsInThisPage'] > 0:
        return respitems[0]['hits']
    else:
        return ""

def find_comp_from_kb(compstring, version, outkbfile, inkbfile, replace_strings):
    #
    # Try to find component in KB
    #
    end = False
    found_comp = ""
    found_version = ""
    comp_url = ""
    compver_url = ""
    source_url = ""
    max_matchstrength = 0

    #packagename = package.lower()
    if replace_strings:
        for repstr in replace_strings:
            compname = compstring.replace(repstr, '')
    else:
        compname = compstring
        
    origcomp = compname
    origver = version
    modver = re.sub(r"-r\d+", "", version)
    modver = re.sub(r"^\d:", "", modver)

    while end == False:
        logging.debug("find_comp_from_kb(): Searching for '{}'".format(compname))
        hits = search_kbpackage(compname)
        if hits:
            logging.debug("find_comp_from_kb(): Found matches for package {}".format(compname))
            temp_comp, temp_version, matchstrength, temp_srcurl, temp_compurl, temp_compverurl = find_ver_from_hits(hits, modver)
            if matchstrength == 3:
                end = True
            if matchstrength > max_matchstrength:
                max_matchstrength = matchstrength
                found_comp = temp_comp
                found_version = temp_version
                comp_url = temp_compurl
                compver_url = temp_compverurl
                source_url = temp_srcurl             
                
        if (end == False) and (len(compname) == len(origcomp)) and (compname.find("-") > -1):
            compnamecolons = compname.replace("-", "::")
            compnamecolons = compnamecolons.replace("_", "::")
            hits = search_kbpackage(compnamecolons)
            if hits:
                logging.debug("find_comp_from_kb(): Found matches for package {}".format(compnamecolons))
                temp_comp, temp_version, matchstrength, temp_srcurl, temp_compurl, temp_compverurl = find_ver_from_hits(hits, modver)
                if matchstrength == 3:
                    end = True    
                if matchstrength > max_matchstrength:
                    max_matchstrength = matchstrength
                    found_comp = temp_comp
                    found_version = temp_version
                    comp_url = temp_compurl
                    compver_url = temp_compverurl
                    source_url = temp_srcurl                

        if (end == False) and ((compname.find("-") > -1) or (compname.find("_") > -1)):
            #
            # Process component replacing - with spaces
            compnamespaces = compname.replace("-", " ")
            compnamespaces = compnamespaces.replace("_", " ")
            hits = search_kbpackage(compnamespaces)
            if hits:
                logging.debug("find_comp_from_kb(): Found matches for package {}".format(compnamespaces))
                temp_comp, temp_version, matchstrength, temp_srcurl, temp_compurl, temp_compverurl = find_ver_from_hits(hits, modver)
                if matchstrength == 3:
                    end = True
                if matchstrength > max_matchstrength:
                    max_matchstrength = matchstrength
                    found_comp = temp_comp
                    found_version = temp_version
                    comp_url = temp_compurl
                    compver_url = temp_compverurl
                    source_url = temp_srcurl             

        if end == False:
            #
            # Remove trailing -xxx from package name
            newcompname = compname.rsplit("-", 1)[0]
            if len(newcompname) == len(compname):
                #
                # No - found, try removing trailing .xxxx
                newcompname = compname.rsplit(".", 1)[0]
                if (len(newcompname) == len(compname)):
                    end = True
            compname = newcompname

    if max_matchstrength > 0:
        print(" - MATCHED '{}/{}' (sourceURL={})".format(found_comp, found_version, source_url))
        return "{};{};{};{};{};{};\n".format(compstring,found_comp,source_url,comp_url,version,compver_url)

    else:
        print(" - NO MATCH")
        return "{};;;NO MATCH;{};NO VERSION MATCH;\n".format(compstring, version)

def add_kbfile_entry(outkbfile, line):
    try:
        ofile = open(outkbfile, "a+")
    except:
        logging.error("append_kbfile(): Failed to open file {} for read".format(outkbfile))
        return

    ofile.write(line)
    ofile.close()
    
def update_kbfile_entry(outkbfile, package, version, compurl, kbverurl):
    #
    # Append version strings to kbfile entry
    #
    # FIELDS:
    # 1 = Local component name;
    # 2 = KB component name;
    # 3 = KB component source URL;
    # 4 = KB component URL;
    # 
    # OPTIONAL:
    # 5 = Local component version string
    # 6 = KB Component version URL
    # (Repeated as often as matched)
    try:
        ofile = open(outkbfile, "r")
    except:
        logging.error("update_kbfile(): Failed to open file {} for read".format(outkbfile))
        return

    lines = ofile.readlines()
    ofile.close()

    try:
        ofile = open(outkbfile, "w")
    except:
        logging.error("update_kbfile(): Failed to open file {} for write".format(outkbfile))
        return
    
    for line in lines:
        elements = line.split(";")
        compname = elements[0]
        thiscompurl = elements[3]
        if compname != package:
            ofile.write(line)
        else:
            if compurl != thiscompurl:
                ofile.write(line)
            else:
                ofile.write("{}{};{};\n".format(line.rstrip(), version, kbverurl))
                logging.debug("update_kbfile(): updated kbfile line with '{};{};'".format(version, kbverurl))
            
    ofile.close()
    return

def import_kbfile(kbfile, outfile):
    #
    # If outfile is not "" then copy kbfile to outfile
    #
    # FIELDS:
    # 1 = Local component name;
    # 2 = KB component name;
    # 3 = KB component source URL;
    # 4 = KB component URL;
    # 
    # OPTIONAL:
    # 5 = Local component version string
    # 6 = KB Component version URL
    # (Repeated as often as matched)
    
    kblookupdict = {}
    kbverdict = {}
    output = False
    try:
        kfile = open(kbfile, "r")
    except:
        logging.error("import_kbfile(): Failed to open file {} ".format(kbfile))
        return kblookupdict, kbverdict
    
    print("Using KB match list input file {}".format(kbfile))
    if outfile != "" and outfile != kbfile:
        output = True
        try:
            ofile = open(outfile, "a+")
            print("Will write to KB match list output file {}".format(outfile))
        except:
            logging.error("import_kbfile(): Failed to open file {} ".format(outfile))
            return "",""
    
    lines = kfile.readlines()
    
    count = 0
    for line in lines:
        elements = line.split(";")
        compname = elements[0]
        kbcompurl = elements[3]
        if kbcompurl != "NO MATCH":
	        kblookupdict.setdefault(compname, []).append(kbcompurl)
        index = 4
        while index < len(elements) - 1:
            kbverdict[compname + "/" + elements[index]] = elements[index+1]
            index += 2
        count += 1
        if output:
            ofile.write(line)
    
    kfile.close
    if output:
        ofile.close()
        
    print("Processed {} entries from {}".format(count, kbfile))
    return kblookupdict, kbverdict

def find_compver_from_compurl(package, kburl, search_version):
    compname, matchversion, matchstrength, bdcomp_sourceurl, bd_verurl = find_ver_from_compver(kburl, search_version)
    if matchstrength > 0:
        return bd_verurl, bdcomp_sourceurl
    else:
        return "NO VERSION MATCH", ""
    
def add_comp_to_bom(bdverurl, kbverurl, compver):
    
    posturl = bdverurl + "/components"
    custom_headers = {
            'Content-Type':'application/vnd.blackducksoftware.bill-of-materials-6+json'
    }
    
    postdata =  {
            "component" : kbverurl,
            "componentPurpose" : "import_manifest: imported ",
            "componentModified" : False,
            "componentModification" : "Original component = " + compver
    }
    
    #print("POST command - posturl = {} postdata = {}".format(posturl, postdata, custom_headers))
    response = hub.execute_post(posturl, postdata, custom_headers)
    if response.status_code == 200:
        print(" - Component added")
        logging.debug("Component added {}".format(kbverurl))
    else:
        print(" - Component NOT added (Probably duplicate)")
        logging.error("Component NOT added {}".format(kbverurl))

def del_comp_from_bom(projverurl, compurl):
#CURLURL="${HUBURL}/api/v1/releases/${PROJVERID}/component-bom-entries"
#[{"entityKey":{"entityId":"76a3c684-639b-4675-ac98-fbec8847539b","entityType":"RL"}}]
#curl $CURLOPTS -X DELETE -H "Accept: application/json" -H "Content-type: application/json" --header "Authorization: Bearer $TOKEN" "${CURLURL//[\"]}" \
#-d "[{\"entityKey\":{\"entityId\":\"${KBVERID}\",\"entityType\":\"RL\"}}]"

#https://hubeval39.blackducksoftware.com/api/projects/e5de5955-67c1-4b03-911b-5f87f4a0a367/versions/586a2bc7-a1a3-4c58-993d-4d1ba6fa301b/components/339bcb81-ac9a-43f3-b293-8f20a84b79ed/versions/f2e2358c-3e41-43ba-bb6c-e2089c4424b5
#https://hubeval39.blackducksoftware.com/api/components/55da34b1-ebc5-4bc3-8440-e38c95bf5145/versions/83e168cb-75c6-481a-80a3-f5aaaf8ea7c0
    
    #response = hub.execute_delete(compurl)

    #delurl = "/".join(projverurl.split("/")[:2]) + "/api/v1/releases/" + projverurl.split("/")[7] + "/component-bom-entries"
    #kbverid = compurl.split("/")[7]
    #postdata =  { "entityKey":{"entityId":kbverid,"entityType":"RL"}}
    
    response = hub.execute_delete(compurl)
    if response.status_code == 200:
        logging.debug("Component deleted {}".format(compurl))
        return True
    else:
        logging.error("Component NOT deleted {}".format(compurl))
        return False

def manage_project_version(proj, ver):
    bdproject = hub.get_project_by_name(proj)
    if not bdproject:
        resp = hub.create_project(proj, ver)
        if resp.status_code != 201:
            logging.debug("Cannot create project {}".format(proj))
            return None, None
        
        print("Created project '{}'".format(proj))
        bdproject = hub.get_project_by_name(proj)
    else:
        print("Opening project '{}'".format(proj))        
        
    bdversion = hub.get_version_by_name(bdproject, ver)
    if not bdversion:
        resp = hub.create_project_version(bdproject, ver)
        if resp.status_code != 201:
            logging.debug("Cannot create version {}".format(ver))
            return None, None
        print("Created version '{}'".format(ver))
        bdversion = hub.get_version_by_name(bdproject, ver)
    else:
        print("Opening version '{}'".format(ver))
    return bdproject, bdversion

def read_project(proj, ver):
    inproject = hub.get_project_by_name(proj)
    if not inproject:
        return None

    inversion = hub.get_version_by_name(inproject, ver)
    if not inversion:
	    return None

    bom_components = hub.get_version_components(inversion)

    return bom_components

#
# Main Program
            
parser = argparse.ArgumentParser(description='Process or import component list into project/version', prog='import_manifest')

subparsers = parser.add_subparsers(help='Choose operation mode', dest='command')
# create the parser for the "kblookup" command
parser_g = subparsers.add_parser('kblookup', help='Process component list to find matching KB URLs & export to file')
parser_g.add_argument('-p', '--project', help='BD project', required=True)
parser_g.add_argument('-v', '--version', help='BD project version', required=True)
parser_g.add_argument('-k', '--kbfile', help='Input file of KB component IDs matching manifest components')
parser_g.add_argument('-o', '--output', help='Output file of KB component IDs matching manifest components (default "kblookup.out")', default='kblookup.out')
parser_g.add_argument('-r', '--replace_package_string', help='Replace (remove) string in input package name', action='append')
parser_g.add_argument('-a', '--append', help='Append new KB URLs to the KB Lookup file specified in -k', action='store_true')

# create the parser for the "import" command
parser_i = subparsers.add_parser('import', help='Import component list into specified Black Duck project/version using KB URLs from supplied file')
parser_i.add_argument('-p', '--project', help='BD project', required=True)
parser_i.add_argument('-v', '--version', help='BD project version', required=True)
parser_i.add_argument('-k', '--kbfile', help='Input file of KB component IDs and URLs matching manifest components', required=True)
parser_i.add_argument('-op', '--outproject', help='Black Duck project name',required=True)
parser_i.add_argument('-ov', '--outversion', help='Black Duck version name',required=True)
parser_i.add_argument('-d', '--delete', help='Delete existing manual components from the project - if not specified then components will be added to the existing list', action='store_true')


#parser.add_argument("version")
args = parser.parse_args()

kblookupdict = {}   # Dict of package names from kbfile with matching array of component URLs for each
kbverdict = {}      # Dict of package/version strings with single component version URL for each
manualcomplist = [] # List of manually added components for optional deletion if -d specified

if not args.command:
    parser.print_help()
    exit
    
if args.command == 'kblookup':
    if args.kbfile:
        if args.append:
            kblookupdict, kbverdict = import_kbfile(args.kbfile, args.output)
            print("Using input kblookup file {} - will append ...".format(args.kbfile))
        else:
            kblookupdict, kbverdict = import_kbfile(args.kbfile, "")
            print("Using input kblookup file {} ...".format(args.kbfile))
    #
    # Process components to find matching KB URLs - output to componentlookup.csv
    components = read_project(args.project, args.version)
    
    print("")
    print("Will output to kbfile {}".format(args.output))
    print("Processing input project/version {}/{} ...".format(args.project, args.version))
    processed_comps = 0
    for comp in components['items']:
        package = comp['componentName']
        version = comp['componentVersionName']
        
        print("Manifest Component = '{}/{}'".format(package, version), end = "")

        if package in kblookupdict:
            #
            # Found primary package name in kbfile
            if kblookupdict[package][0] == "NO MATCH":
                print("- NO MATCH in input KB File")
                continue
            logging.debug("Found package {} in kblookupdict".format(package))
            #
            # Check if package/version is defined in KB Lookup file 
            packverstr = package + "/" + version
            if packverstr in kbverdict:
                # Found in KB ver URL list - Nothing to do
                logging.debug("Found component {} version {} in kbverdict - URL {}".format(package, version, kbverdict[packverstr]))
                kbverurl = kbverdict[packverstr]
                print(" - already MATCHED in input KB file")
            else:
                #
                # Loop through component URLs to check for component version
                foundkbversion = False

                for kburl in kblookupdict[package]:
                    kbverurl, srcurl = find_compver_from_compurl(package, kburl, version)
                    processed_comps += 1
                    if kbverurl != "NO VERSION MATCH":
                        print(" - MATCHED '{}/{}' (sourceURL={})".format(package, version, srcurl))
                        #
                        # KB version URL found
                        kbverdict[package + "/" + version] = kbverurl
                        update_kbfile_entry(args.output, package, version, kblookupdict[package][0], kbverurl)
                        processed_comps += 1

                        foundkbversion = True
                        break
                if foundkbversion == False:
                    #
                    # No version match - need to add NO VERSION MATCH string to kbfile
                    update_kbfile_entry(args.output, package, version, kblookupdict[package][0], "NO VERSION MATCH")
                    continue # move to next component
        else:
            processed_comps += 1
            newkbline = find_comp_from_kb(package, version, args.output, args.kbfile, args.replace_package_string)
            add_kbfile_entry(args.output, newkbline)
            
        if processed_comps > 500:
            print("500 components processed - terminating. Please rerun with -k option to append to kbfile")
            exit()
    exit()

if args.command == 'import':
    if args.kbfile:
        kblookupdict, kbverdict = import_kbfile(args.kbfile, "")
    
    bdproject, bdversion = manage_project_version(args.outproject, args.outversion) 
    if not bdversion:
        print("Cannot create output version {}".format(args.outversion))
        exit()
    bdversion_url = bdversion['_meta']['href']
         
    outcomponents = hub.get_version_components(bdversion)
    print("Found {} existing components in output project".format(outcomponents['totalCount']))
    if args.delete:
        count = 0
        logging.debug("Looking through the components for project {}, version {}.".format(args.project, args.version))
        for component in outcomponents['items']:
            if component['matchTypes'][0] == 'MANUAL_BOM_COMPONENT':
                manualcomplist.append(component['componentVersion'])
                count += 1
        print("Found {} manual components".format(count))
      
    print("Reading input project '{}/{}'".format(args.project, args.version))
    incomponents = read_project(args.project, args.version)
    
    print("")
    print("Processing component list from input project ...")  
    for comp in incomponents['items']:
        package = comp['componentName']
        version = comp['componentVersionName']
        modver = re.sub(r"-r\d+", "", version)
        modver = re.sub(r"^\d:", "", modver)

        print("Original component = '{}/{}'".format(package, version), end="")
        logging.debug("Manifest component to add = '{}/{}'".format(package, version))
        kbverurl = ""
        if package in kblookupdict:
            #
            # Check if package/version is in kbverdict 
            packstr = package + "/" + version
            if packstr in kbverdict:
                #
                # Component version URL found in kbfile 
               logging.debug("Compver found in kbverdict packstr = {}, kbverdict[packstr] = {}".format(packstr, kbverdict[packstr]))
               kbverurl = kbverdict[packstr]
            else:
                #
                # No match of component version in kbfile version URLs
                for kburl in kblookupdict[package]:
                    #
                    # Loop through component URLs from kbfile
                    #if kburl == "NO MATCH":
                    #	continue
                    kbverurl, srcurl = find_compver_from_compurl(package, kburl, modver)
                    if kbverurl != "NO VERSION MATCH":
                        break
            if kbverurl != "NO VERSION MATCH":
                #
                # Component does not exist in project
                logging.debug("Component found in project - packstr = {}".format(packstr))
                add_comp_to_bom(bdversion_url, kbverurl, package + "/" + version)
                if kbverurl in manualcomplist:
                    manualcomplist.delete(kbverurl)
            else:
            	# Copy component from inproject to outproject
                print(" - No KB match from lookup file - Will copy component from original project", end="")
                kbverurl = comp['componentVersion']
                add_comp_to_bom(bdversion_url, kbverurl, package + "/" + version)

        else:
            print (" - No KB match from lookup file - Will copy component from original project", end="")
            kbverurl = comp['componentVersion']
            add_comp_to_bom(bdversion_url, kbverurl, package + "/" + version)
    
    if args.delete:
        print("Unused components not deleted - not available until version 2019.08 which supports the required API")
    #    count = 0
    #    for compver in manualcomplist:
    #        del_comp_from_bom(bdversion_url, compver)
    #        count += 1
    #    print("Deleted {} existing manual components".format(count))