#!/usr/bin/env python3

import argparse
import configparser
import os
import os.path
import sys
import json
from json import JSONEncoder

class Package:
    def __init__(self):
        self.package_name = None
        self.package_version = None
        self.recipe_name = None
        self.license_string = None
        self.licenses = []

class JsonPackage:
    def __init__(self):
        self.name = None
        self.version = None
        self.license = None
        self.licenseText = None

class JsonPackageEncoder(JSONEncoder):
    def default(self, object):
        if isinstance(object, JsonPackage):
            return object.__dict__
        else:
            return json.JSONEncoder.default(self, object)

class ConfigObject:
    def __init__(self):
        self.section_name = None
        self.chosen_license = None
        self.license_files = None
        self.additional_files = None
        self.skip_license_count_check = False

    def __init__(self, package):
        self.section_name = "{}_{}_{}".format(package.package_name, package.recipe_name, package.package_version)
        self.chosen_license = None
        self.license_files = None
        self.additional_files = None
        self.skip_license_count_check = False
    
    @staticmethod
    def packageToSectionName(package):
        return "{}_{}_{}".format(package.package_name, package.recipe_name, package.package_version)

class Licenses:
    def __init__(self):
        self.licenses = {} # dict
        self.recipes = {} # dict
        self.packages = [] # list
        self.packages_filtered = [] # list
        self.json_packages = [] # list
        self.config_file = None
        self.config = None
        self.builddir = None
        self.tmpdir = None

    def initConfig(self):
        if self.config_file is None:
            # use default config file in build-dir if no config file path was given
            self.config_file = os.path.join(self.builddir, "license-parser.ini")
        if self.config is None:
            self.config = configparser.ConfigParser()
            self.config.read(self.config_file)


    def readConfigFile(self, package):
        self.initConfig()
        self.config.read(self.config_file)

        section_name = ConfigObject.packageToSectionName(package)
        if section_name in self.config:
            section = self.config[section_name]
            new_config_object = ConfigObject(package)
            new_config_object.section_name = section_name
            new_config_object.chosen_license = section.get('ChosenLicense', None)
            new_config_object.license_files = json.loads(section.get('LicenseFiles', '[]'))
            new_config_object.additional_files = json.loads(section.get('AdditionalFiles', '[]'))
            new_config_object.skip_license_count_check = section.getboolean('SkipLicenseCountCheck')

            return new_config_object
        return None

    def updateConfigFile(self, config_object):
        self.initConfig()
        if not isinstance(config_object, ConfigObject):
            raise

        if not config_object.section_name in self.config:
            self.config.add_section(config_object.section_name)

        self.config[config_object.section_name]['ChosenLicense'] = config_object.chosen_license if config_object.chosen_license is not None else ""
        self.config[config_object.section_name]['LicenseFiles'] = json.dumps(config_object.license_files)
        self.config[config_object.section_name]['AdditionalFiles'] = json.dumps(config_object.additional_files)
        self.config[config_object.section_name]['SkipLicenseCountCheck'] = "yes" if config_object.skip_license_count_check else "no"

        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def printHeadline(self, text):
        print("")
        print("####################")
        print(text)
        print("####################")
        print("")

    def userChoice(self, package):
        print("--------------------")
        print("!!! License CHOICE for package '{}' !!!".format(package.package_name))
        print("--------------------")
        licenses = [l.strip() for l in package.license_string.split('|')]
        chosen_license = None

        for i, l in enumerate(licenses):
            print("{}: {}".format(i, l))

        conf_object = self.readConfigFile(package)

        if (conf_object is None) or (conf_object.chosen_license is None) or (conf_object.chosen_license == ""):
            print("")
            index = int(input("Choice (number): "))
            print("")

            # TODO handle invalid input
            chosen_license = licenses[index].strip()

            # store the decision
            if conf_object is None:
                conf_object = ConfigObject(package)
            conf_object.chosen_license = chosen_license
            self.updateConfigFile(conf_object)
        else:
            print("")
            print("Using license decision from config-file: '{}' !!!".format(conf_object.chosen_license))
            print("")
            chosen_license = conf_object.chosen_license
            # sanity check: make sure license choice from file is in list of possible licenses
            if not chosen_license in licenses:
                print("!!! Error: License choice from config is invalid!")
                print("")
                raise

        return chosen_license

    def parseManifest(self, manifest):
        self.printHeadline("Parsing manifest file...")

        # get build directory from environment variable if not given via argument
        if self.builddir is None:
            self.builddir = os.getenv('BUILDDIR')
            if self.builddir is None:
                print("!!! Error: Build directory not set. Init build environment first (run setToolchain)")
                print("")
                raise

        # get tmp directory from environment variable if not given via argument
        if self.tmpdir is None:
            self.tmpdir = os.getenv('TMPDIR')
            if self.tmpdir is None:
                print("!!! Error: TMP directory not set. Init build environment first (run setToolchain)")
                print("")
                raise

        # Initialise a package object
        package = Package()
        with open(manifest) as file:
            for line in file:
                if line == "\n":
                    # New package, add current package to list
                    self.packages.append(package)

                    # init new object for next package
                    package = Package()

                else:
                    # parse content of current package
                    tmp = line.split(': ')
                    if tmp[0] == "PACKAGE NAME":
                        package.package_name = tmp[1].strip()
                    elif tmp[0] == "PACKAGE VERSION":
                        package.package_version = tmp[1].strip()
                    elif tmp[0] == "RECIPE NAME":
                        package.recipe_name = tmp[1].strip()
                    elif tmp[0] == "LICENSE":
                        # need to resolve multiple choice licenses
                        package.license_string = tmp[1].strip()
                        if ("|" in package.license_string) and ("&" in package.license_string):
                            # should not happen, bail out with an exception
                            raise
                        elif "|" in package.license_string:
                            # require user input on multiple choice licenses
                            chosen_license = self.userChoice(package)
                            package.licenses.append(chosen_license)

                        elif "&" in package.license_string:
                            # multiple licenses
                            package.licenses = [l.strip() for l in tmp[1].strip().split('&')]                             
                        else:
                            package.licenses.append(package.license_string)                        

        #
        # packages are now parsed
        #
             
        # group by recipe
        for package in self.packages:
            if not self.recipes.get(package.recipe_name):
                self.recipes[package.recipe_name] = [package]
            else:
                self.recipes[package.recipe_name].append(package)

        # group by license
        for package in self.packages:
            for license in package.licenses:
                if not self.licenses.get(license):
                    self.licenses[license] = [package]
                else:
                    self.licenses[license].append(package)
        
        # merge packages by recipe-name if they have the exact same license and version
        self.printHeadline("Merging recipes...")
        for recipe, packages in self.recipes.items():

            # at this point we already sorted out multiple-choice licenses (|, OR)
            # so the licenses-list will either contain exactly 1 or a list of used licenses
            # merge the license-lists to get all needed licenses for a recipe
            all_licenses = []
            for licpack in packages:
                all_licenses.extend(licpack.licenses)
            all_licenses = list(set(all_licenses)) # remove duplicates by converting to set and back

            # sanity checking
            for sanitypack in packages:
                if ("|" in sanitypack.license_string) and (len(all_licenses) != 1):
                    raise
                if ("&" in sanitypack.license_string) and (len(all_licenses) <= 1):
                    raise

            if all(allpack1.package_version == packages[0].package_version for allpack1 in packages) and all(all(singlelic in all_licenses for singlelic in allpack2.licenses) for allpack2 in packages):

                p = Package()
                p.package_name = recipe
                p.recipe_name = recipe
                p.package_version = packages[0].package_version
                p.license_string = packages[0].license_string
                p.licenses = packages[0].licenses

                if len(packages) > 1:
                    print("Merging {} packages with identical recipe-name ({}), version and license".format(len(packages), recipe))
                    for printpack in packages:
                        print(" - {}, {}, {}".format(printpack.package_name, printpack.package_version, printpack.license_string))
                    print('')
                else:
                    # sanity check, make sure package_name == recipe_name
                    if packages[0].package_name != recipe:
                        print("Replacing package_name '{}' with recipe_name '{}'".format(packages[0].package_name, recipe))
                        print('')

                # remove separate packages from package-list
                for package in packages:
                    self.packages.remove(package)
                # and add merged package instead
                self.packages.append(p)

        # filter packages
        self.printHeadline("Filtering packages...")
        for package in self.packages:
            # we are normally not interested in proprietary (own) packages
            if len(package.licenses) == 1 and package.licenses[0] == "CLOSED":
                print("Removing package '{}' - Reason: license type 'CLOSED'".format(package.package_name))
                continue
            # we are not interested in package-groups (a package-group is just a yocto-specific grouping mechanism)
            if package.package_name.startswith("packagegroup"):
                print("Removing package '{}' - Reason: 'packagegroups' are not relevant".format(package.package_name))
                continue

            # add rest of the packages to the filtered list
            self.packages_filtered.append(package)
 
        # collect license files
        self.printHeadline("Collecting license files for packages...")
        for package in self.packages_filtered:

            conf_object = self.readConfigFile(package)

            if conf_object is None:
                conf_object = ConfigObject(package)
                self.updateConfigFile(conf_object)
            
            # sanity check. number of license files in config-file must match the number of licenses
            num_lic_files_in_config = len(conf_object.license_files) if not conf_object.license_files is None else 0
            if (len(package.licenses) > num_lic_files_in_config) or ((num_lic_files_in_config > 0) and not all(os.path.isfile(os.path.join(self.tmpdir, lfp)) for lfp in conf_object.license_files)):
                print("Package: {}".format(package.package_name))
                print("----------------------------------------")              
                print("")
                print("License files from config: ")
                if not conf_object.license_files is None:
                    for i, l in enumerate(conf_object.license_files):
                        print("  {}: {}".format(i, l))
                else:
                    print("  None")
                print("")
                if conf_object.skip_license_count_check:
                    print("!!! Warning: Not enough license files defined in config or files are non-existent")
                    print("")
                    print("!!! ATTENTION: License count mismatch is ignored because 'SkipLicenseCountCheck' is set! MAKE SURE THAT THIS IS WHAT YOU INTENDED TO DO!!!")
                    print("")
                else:
                    print("!!! Error: Not enough license files defined in config or files are non-existent")
                    print("")
                    self.showLicenseFiles(package)
                    print("")
                    raise
        
    
    def showLicenseFiles(self, package):
        lic_dir_path = os.path.join(self.tmpdir, "deploy/licenses/", package.recipe_name)
        print("Package licenses: ")
        for i, l in enumerate(package.licenses):
            print("  {}: {}".format(i, l))
        print("")
        print("License file directory: {}".format(lic_dir_path))
        print("")
        print("Files in directory: ")
        for i, l in enumerate(os.listdir(lic_dir_path)):
            print("  {}: {}".format(i, l))
        # look for   recipeinfo  LICENSE(.*)  LICENSES  README.*   COPYING.*


    def generateLicenseJson(self, outfile):
        # generate JSON packages
        self.printHeadline("Generating license JSON file... ({} packages)".format(len(self.packages_filtered)))
        for package in self.packages_filtered:
            json_package = JsonPackage()
            
            json_package.name = package.package_name
            json_package.version = package.package_version
            json_package.license = " & ".join(package.licenses)
            
            # read config file to get list of license-text files
            conf_object = self.readConfigFile(package)

            if conf_object is None:
                # at this point there must be a valid entry in the config file for each package, if not: raise exception
                print("!!! Error: No config section for package {} in config file".format(package.package_name))
                print("")
                raise
            
            lic_text = ""

            if not conf_object.additional_files is None:
                for add_file_entry in conf_object.additional_files:
                    add_file_path = os.path.join(self.tmpdir, add_file_entry)
                    with open(add_file_path, 'r') as add_file:
                        add_file_content = add_file.read()
                        lic_text += add_file_content
                    lic_text += """

================================================================================

"""

            if not conf_object.license_files is None:
                for lic_file_entry in conf_object.license_files:
                    lic_file_path = os.path.join(self.tmpdir, lic_file_entry)
                    with open(lic_file_path, 'r') as lic_file:
                        lic_file_content = lic_file.read()
                        lic_text += lic_file_content
                    lic_text += """

================================================================================

"""

            json_package.licenseText = lic_text

            self.json_packages.append(json_package)

        # and write them to output file
        with open(outfile, 'w') as of:
            json.dump(self.json_packages, of, cls=JsonPackageEncoder, indent=4)

        print("Done!")
        print("")


    def printLicenses(self):
        # print list of all used licenses
        self.printHeadline("License list ({} licenses)".format(len(self.licenses)))
        for license, packages in self.licenses.items():
            print(license)
        print(" ")

        # print packages for each license (packages with multiple licenes will be printed multiple times)
        self.printHeadline("License/package list (may contain package duplicates if package has multiple licenses)")
        for license, packages in self.licenses.items():
            print("License '{}':".format(license))
            print("--------------------")
            for package in packages:
                print("  - {}".format(package.package_name))
            print(" ")


    def printRecipes(self):
        # print packages for each recipe
        self.printHeadline("Recipe list ({} recipes)".format(len(self.recipes)))
        for recipe, packages in self.recipes.items():
            print("Recipe '{}':".format(recipe))
            print("--------------------")
            for package in packages:
                print("  - {}".format(package.package_name))
            print(" ")


    def printPackages(self):
        self.printHeadline("Package list ({} packages)".format(len(self.packages_filtered)))
        join_string = ", "
        print("Package Name, Version, Recipe, Licenses")            
        for package in self.packages_filtered:
            print("{1}{0}{2}{0}{3}{0}{4}".format(join_string, package.package_name, package.package_version, package.recipe_name, " & ".join(package.licenses)))


def main() -> int:

    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", help="Path to the license.manifest file")
    parser.add_argument("-l", "--licenses", help="Show each license type and which packgages use it", action="store_true")
    parser.add_argument("-r", "--recipes", help="Show each recipe and which packgages it contains", action="store_true")
    parser.add_argument("-p", "--packages", help="Show each package, version and license type", action="store_true")
    parser.add_argument("-j", "--json", help="Write packages in JSON format to given output file name", dest='outfile', type=str)
    parser.add_argument("-b", "--builddir", \
        help="Yocto build directory. If not given script tries to get build directory from environment.", \
        dest='builddir', type=str, required=False)
    parser.add_argument("-t", "--tmpdir", \
        help="Yocto tmp directory. If not given script tries to get tmp directory from environment.", \
        dest='tmpdir', type=str, required=False)
    parser.add_argument("-c", "--config", \
        help="Config file path. If not given script uses default file within build directory.", \
        dest='conffile', type=str, required=False)

    args = parser.parse_args()

    if not os.path.exists(args.manifest):
        print("{} does not exist".format(args.manifest))
        sys.exit()

    licenses = Licenses()

    if not args.builddir is None:
        licenses.builddir = args.builddir
    if not args.tmpdir is None:
        licenses.tmpdir = args.tmpdir
    if not args.conffile is None:
        licenses.config_file = args.conffile

    licenses.parseManifest(args.manifest)

    if args.licenses:
        licenses.printLicenses()
    elif args.recipes:
        licenses.printRecipes()
    elif args.packages:
        licenses.printPackages()
    elif not args.outfile is None:
        licenses.generateLicenseJson(args.outfile)

    return 0


if __name__ == '__main__':
    sys.exit(main())

# vim: tabstop=4 shiftwidth=4 expandtab
