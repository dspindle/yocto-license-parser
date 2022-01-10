#!/usr/bin/env python3

import argparse
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

class Licenses:
    def __init__(self):
        self.licenses = {}
        self.recipes = {}
        self.packages = []
        self.json_packages = []

    def parseManifest(self, manifest):
        # Initialise a package object
        package = Package()
        with open(manifest) as file:
            for line in file:
                if line == "\n":
                    # New package
                    self.packages.append(package)
                    for license in package.licenses:
                        if not self.licenses.get(license):
                            self.licenses[license] = [package]
                        else:
                            self.licenses[license].append(package)

                    if not self.recipes.get(package.recipe_name):
                        self.recipes[package.recipe_name] = [package]
                    else:
                        self.recipes[package.recipe_name].append(package)

                    package = Package()

                else:
                    tmp = line.split(': ')
                    if tmp[0] == "PACKAGE NAME":
                        package.package_name = tmp[1].strip()
                    elif tmp[0] == "PACKAGE VERSION":
                        package.package_version = tmp[1].strip()
                    elif tmp[0] == "RECIPE NAME":
                        package.recipe_name = tmp[1].strip()
                    elif tmp[0] == "LICENSE":
                        package.license_string = tmp[1].strip()
                        package.licenses = tmp[1].strip().split(' & ')

        for recipe, packages in self.recipes.items():
            if all(package.package_version == packages[0].package_version for package in packages) and all(package.license_string == packages[0].license_string for package in packages):
                for package in packages:
                    self.packages.remove(package)
                p = Package()
                p.package_name = recipe
                p.recipe_name = recipe
                p.package_version = packages[0].package_version
                p.license_string = packages[0].license_string
                p.licenses = p.license_string.split(' & ')
                self.packages.append(p)
 
        for package in self.packages:
            json_package = JsonPackage()
            
            json_package.name = package.package_name
            json_package.version = package.package_version
            json_package.license = package.license_string
            json_package.licenseText = ""
            
            self.json_packages.append(json_package)
 

    def printLicenses(self):
        for license, packages in self.licenses.items():
            if license == "CLOSED":
                continue
           # if package.package_name.startswith("packagegroup"):
           #     continue
            print("{}:".format(license))
            for package in packages:
                print(package.package_name)

            print(" ")

        for recipe, packages in self.recipes.items():
            print("{}:".format(recipe))
            for package in packages:
                print(package.package_name)

            print(" ")


    def printPackages(self, csv=False):
        join_string = " "
        if csv:
            join_string = ","
            print("Package Name,Version,Recipe,Licenses")
        for package in self.packages:
            if len(package.licenses) == 1 and package.licenses[0] == "CLOSED":
                continue
            if package.package_name.startswith("packagegroup"):
                continue
            print("{1}{0}{2}{0}{3}{0}{4}".format(join_string, package.package_name, package.package_version, package.recipe_name, " & ".join(package.licenses)))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", help="Path to the licence.manifest file")
    parser.add_argument("-l", "--licenses", help="Show each licence type and which packgages use it", action="store_true")
    parser.add_argument("-p", "--packages", help="Show each package, version and license type", action="store_true")
    parser.add_argument("-c", "--csv", help="Display the output as CSV", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.manifest):
        print("{} does not exist".format(args.manifest))
        sys.exit()

    licenses = Licenses()
    licenses.parseManifest(args.manifest)

    if args.licenses:
        licenses.printLicenses()
    elif args.packages:
        licenses.printPackages(args.csv)

    with open('licenses_linux.json', 'w') as outfile:
        json.dump(licenses.json_packages, outfile, cls=JsonPackageEncoder, indent=4)



# vim: tabstop=4 shiftwidth=4 expandtab
