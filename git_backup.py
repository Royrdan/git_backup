#!/usr/bin/python3
import requests
import json
from datetime import datetime
import base64
import os
import pyAesCrypt
import hashlib
import sys
import yaml
from fnmatch import fnmatch
import socket
from urllib.parse import quote as url_encode

try:
    from pyscript import pyscript_compile, service
    ispc = False
except ImportError:
    ispc = True

debug = False
dry_run = False

if not ispc:
    requests_get = pyscript_compile(requests_get)
    requests_put = pyscript_compile(requests_put)
    hash = pyscript_compile(hash)
    open_file = pyscript_compile(open_file)
    write_file = pyscript_compile(write_file)
    start_backup = service(start_backup)
    start_download = service(start_download)


def requests_get(api, repo, file_x, headers,auth, last_database, last_path):
    filename = file_x.split("/")[-1] # Gets the actual file name without the path
    path = file_x[:-(1+len(filename))] # Gets the path without the file name
    tree = url_encode("main:" + path)
    url  = f"{api}/repos/{repo}/git/trees/{tree}"
    # Check if need to re-download or just reuse the last list (Cacheing)
    if url != last_path:
        r = requests.get(url, headers=headers,auth=auth).json()
        last_database = r
        last_path = url
    else:
        r = last_database
    try:
        for f in r['tree']:
            #print(f"fpath   : {f['path']}\nfilename: {filename}")
            if f['path'] == filename:
                return f['sha'], last_database, last_path
    except:
        pass
    return None, last_database, last_path

def requests_put(url, headers, auth, data):
    return requests.put(url, headers=headers,auth=auth, data=data)


def hash(file_path):
    with open(file_path, 'rb') as f:
        file_size = os.path.getsize(file_path)
        sha1_hex = hashlib.sha1()
        sha1_hex.update(b"blob %u\0" % file_size)
        sha1_hex.update(f.read())
    return sha1_hex.hexdigest()

def open_file(file_name, file_path, encrypt_list, encrypt_password, buffer_size):
    file_contents = None
    try:
        with open(file_path, 'rb') as f:
            if file_name in encrypt_list:
                with open(file_path + ".encrypt", 'wb') as f_encrypt:
                    pyAesCrypt.encryptStream(f, f_encrypt, encrypt_password, buffer_size)
                with open(file_path + ".encrypt", 'rb') as f_encrypt:
                    file_contents = base64.b64encode(f_encrypt.read()).decode("utf-8")
                sha1 = hash(file_path + ".encrypt")
                os.remove(file_path + ".encrypt")
            else:
                file_contents = base64.b64encode(f.read()).decode("utf-8")
                sha1 = hash(file_path)

        return file_contents, sha1
    except:
        return None, None

def write_file(file_path, file_content):
    with open(file_path, 'wb+') as f:
        file_content = base64.b64decode(response['content'])
        # decrypt
        f.write(file_content)

class github():
    def __init__(self, dry_run, single_file):
        self.errors = []
        self.last_database = {}
        self.last_path = ""
        if ispc:
            #################  ROYRDANPC CONFIG  ############################
            self.errors_file = "errors.txt"
            self.errors_file_all = "errors_all.txt"
            secrets_file = "secrets.yaml"
            try:
                with open(secrets_file, 'r+') as s:
                    secrets = yaml.load(s, Loader=yaml.FullLoader)
                    api_token = secrets['github_api']
                    encrypt_pass = secrets['github_backup_encryption_pass']
            except:
                self.errors.append("Open secrets file failed")
                print("Failed to open secrets file " + secrets)
                sys.exit()
            self.repo = "royrdan/royrdanpc"
            self.encrypt_password = encrypt_pass
            self.login=("Royrdan", api_token)

            # Uses fnmatch to compare filenames to full directory
            # First only includes folder matching INCLUDE
            # Then removes any folder matching EXCLUDE

            self.include = [
                "/home/royrdan/Documents*",
                "/home/royrdan/Desktop*",
            ]

            self.exclude = [
                "*HomeAssistant/floorplans/floorplan_4K.xcf",
                "*HomeAssistant/floorplans/floorplan.xcf",
                "/etc/resolvconf/resolv.conf.d/original",
                "/etc/systemd/system/key-mapper.service",
                "/etc/systemd/system/default.target.wants/key-mapper.service",
                "/etc/NetworkManager/system-connections/*",
                "/root/.cache/*",
                "/root/.config/pulse/dafd9a61376b4676aa8b190bc1ed4b43-runtime",
                "*.img*",
                ]

            # Encrypt must be exact file path after <directory
            self.encrypt = [
                "Documents/python/secrets.yaml"
                ]

            self.dry_run = dry_run
            self.single_file = single_file
            self.directory = "/"
        else:
            #################  HOME ASSISTANT CONFIG  #########################
            self.repo = pyscript.config['apps']['git_backup']['repo']
            self.encrypt_password = pyscript.config['apps']['git_backup']['encrypt_password']
            self.login=(pyscript.config['apps']['git_backup']['username'], pyscript.config['apps']['git_backup']['api_token'])

            self.exclude = pyscript.config['apps']['git_backup']['exclude']
            self.encrypt = pyscript.config['apps']['git_backup']['encrypt']
            self.include = None

            self.dry_run = dry_run
            self.single_file = single_file
            self.directory = pyscript.config['apps']['git_backup']['ha_config_dir']

        self.github_api = "https://api.github.com"
        self.headers = {'Accept': 'application/vnd.github.v3+json'}

        self.buffer_size = 64 * 1024

        # Fix directory if ending in a /
        if self.directory[-1] != "/":
            self.directory += "/"

    def get_sha1(self, file_x):
        if ispc:
            ret, self.last_database, self.last_path = requests_get(api=self.github_api, repo=self.repo, file_x=file_x, headers=self.headers,auth=self.login, last_database=self.last_database, last_path=self.last_path)
            return ret
        else:
            ret, self.last_database, self.last_path = task.executor(requests_get, api=self.github_api, repo=self.repo, file_x=file_x, headers=self.headers,auth=self.login, last_database=self.last_database, last_path=self.last_path)
            return ret

    def get_encrypted_files(self, dry_run):
        if not os.path.isdir(self.directory + "restore/"):
            os.makedirs(self.directory + "restore/")
        for item in self.encrypt:
            item += ".encrypt"
            response = self.get(item)
            file_path = self.directory + "restore/" + item
            if "/" in item:
                path = "/".join(file_path.split('/')[:-1])
                if not os.path.isdir(path):
                    os.makedirs(path)
            if ispc:
                write_file(file_path, file_content)
            else:
                task.executor(write_file, file_path, file_content)
            pyAesCrypt.decryptFile(file_path, file_path.replace('.encrypt', ''), self.encrypt_password, self.buffer_size)
            os.remove(file_path)

    def upload_file(self, file_x, content, original_sha1=None):
        # Encode string to Base64
        data = {
            "message": datetime.now().strftime("%d %m %Y"),
            "content": content
        }
        if original_sha1:
            data['sha'] = original_sha1
        data_str = json.dumps(data)
        url = f"{self.github_api}/repos/{self.repo}/contents/{url_encode(file_x)}"
        if ispc:
            response = requests_put(url=url, headers=self.headers,auth=self.login, data=data_str)
        else:
            response = task.executor(requests_put, url=url, headers=self.headers,auth=self.login, data=data_str)
        if response.status_code in [200, 201]:
            return None
        else:
            return f"{file_x} with code: {str(response.status_code)}"

    def run_upload(self):
        copied_files = []
        file_paths = []
        if self.single_file:
            if ispc and debug: print("Single file mode: " + self.single_file)
            file_paths.append(self.single_file)
        else:
            if ispc and debug: print("Building file list...")
            for root, directories, files in os.walk(self.directory):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    add = False
                    if self.include == None:
                        add = True
                    else:
                        # Add Includes
                        for i in self.include:
                            if fnmatch(filepath, i):
                                add = True
                    # Remove Excludes
                    for e in self.exclude:
                        if fnmatch(filepath, e):
                            add = False
                    if add:
                        file_paths.append(filepath)

        for file_path in file_paths:
            file_name = file_path[ len(self.directory) :] # remove the directory

            #log.warning("Processing " + file_name)

            # Open the file for processing and return SHA1 and contents
            if ispc:
                file_contents, sha1 = open_file(file_name=file_name, file_path=file_path, encrypt_list=self.encrypt, encrypt_password=self.encrypt_password, buffer_size=self.buffer_size)
            else:
                file_contents, sha1 = task.executor(open_file, file_name=file_name, file_path=file_path, encrypt_list=self.encrypt, encrypt_password=self.encrypt_password, buffer_size=self.buffer_size)

            if file_contents == None:
                self.errors.append("Failed to open file: " + file_path)
                continue
            # Check if is an encrypted file
            if file_name in self.encrypt:
                file_name += ".encrypt"

            # Get file from Github
            original_sha1 = self.get_sha1(file_name)

            # Check if file exists on github
            if original_sha1:
                if ispc:
                    if debug: print("Found file " + file_name)
                else:
                    log.debug("Found file " + file_name)
            if debug: print( f"Original SHA1: {original_sha1}\nNew SHA1: {sha1}" )
            if original_sha1 == sha1:
                if ispc:
                    if debug: print("Skipping " + file_name + ". No update is needed")
                else:
                    log.debug("Skipping " + file_name + ". No update is needed")
            else:
                if not self.dry_run:
                    if ispc:
                        print("Uploading " + file_name)
                    else:
                        log.warning("Uploading " + file_name)
                    up = self.upload_file(file_name, file_contents, original_sha1)
                    if up:
                        self.errors.append("Failed to upload " + up)
                    else:
                        copied_files.append(file_name)
                else:
                    if ispc:
                        print("DRY: Uploading " + file_name)
                    else:
                        log.warning("DRY: Uploading " + file_name)

        if ispc:
            if debug: print("Successfully processed " + str(len(copied_files)) + " files")
            if len(self.errors) > 0:
                with open(self.errors_file, 'a+') as myfile:
                    if len(self.errors) > 2:
                        myfile.write("Git Backup failed to copy " + str( len(self.errors) ) + " files")
                    else:
                        myfile.write("Git Backup failed to copy " + str( len(self.errors) ) + " files " + ", ".join(self.errors) )
                with open(self.errors_file_all, 'w+') as myfile:
                    myfile.write("\n".join(self.errors))
        else:
            if len(copied_files) > 0:
                log.warning("Successfully uploaded " + str(len(copied_files)) + " files")
            if len(self.errors) > 0:
                input_text.set_value(entity_id="input_text.github_backup_message", value="Failed to upload " + str(len(self.errors)) + " files")
                log.warning("Failed to process " + str(len(self.errors)) + " files")
                for er in self.errors:
                    log.warning("Failed to upload: " + er)
            else:
                log.warning("Github Backup was successful")
                input_text.set_value(entity_id="input_text.github_backup_message", value="Successful")

def start_backup(dry_run=False, single_file=None):
    x = github(dry_run, single_file) # Create the class
    x.run_upload()

def start_download(dry_run=False):
    x = github(dry_run) # Create the class
    x.get_encrypted_files(dry_run)


if ispc: start_backup(dry_run = dry_run)
