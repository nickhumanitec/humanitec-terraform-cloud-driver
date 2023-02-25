import requests
import shutil
import tarfile
import os
import zipfile
import json

import base64

import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def clean_tmp(download_folder, decompress_folder):
    try:
        shutil.rmtree(download_folder)
    except Exception as e:
        pass

    try:
        os.mkdir(download_folder)
    except Exception as e:
        pass

    try:
        os.mkdir(decompress_folder)
    except Exception as e:
        pass


def make_tarfile(decompress_folder, downloaded_file, source_tar, compress_folder):
    with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
        zip_ref.extractall(decompress_folder)

    with tarfile.open(source_tar, "w:gz") as tar:
        tar.add(compress_folder, arcname=os.path.basename(compress_folder))


def clean_name(s):
    s = s.replace("modules.", "")
    s = s.replace(".", "-")
    getVals = list([val for val in s if val.isalnum() or "-"])

    return "".join(getVals).replace(" ", "")


def get_github_latest_commit(url, token=""):
    h = {}
    if token != "":
        h = {"Authorization": "Bearer {TOKEN}".format(
            TOKEN=token)}
    x = requests.get(
        url, headers=h)
    log("get_github_latest_commit response", x)

    x = x.json()

    sha = x[0]["sha"]
    return x, sha


def get_error(error="", message=""):
    return {
        "error": error,
        "message": message
    }


def get_wait(status=""):
    return {"status": status}


def get_body(id, resource_type, values={}, secrets={}):
    return json.dumps({
        "id": id,
        "type": resource_type,
        "resource": {
            "values": values,
            "secrets": secrets
        },
        "manifests": [

        ]})


def get_response(debug="", cookie="", body="", status=200):
    if cookie != "":
        cookie = base64.b64encode(json.dumps(cookie).encode())

    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Set-Humanitec-Driver-Cookie": cookie,
            "X-HumanitecDebug": debug
        },
        "body": body
    }


def log(m, x):
    logger.debug("## {}".format(m))
    if isinstance(x, requests.Response):
        logger.debug(x.url)
        logger.debug(x.headers)
        logger.debug(x.text)
        return
    logger.debug(x)


class TerraformCloud:
    def __init__(self, org_name, tfcloud_token, project_name, workspace_name, log):

        self.org_name = org_name
        self.tfcloud_token = tfcloud_token
        self.workspace_name = workspace_name
        self.project_name = project_name

        self.workspace_id = None
        self.project_id = None

        self.url = "https://app.terraform.io/api/v2"

        self.headers = self.set_headers()
        self.log = log

        # upsert project
        _, self.project_id = self.get_project_by_name()
        if not self.project_id:
            _, self.project_id = self.create_project()

        # upsert workspace
        _, self.workspace_id = self.get_workspace()
        if not self.workspace_id:
            _, self.workspace_id = self.create_workspace()

    def set_headers(self):
        return {
            "Authorization": "Bearer {TOKEN}".format(TOKEN=self.tfcloud_token),
            "Content-Type": "application/vnd.api+json"
        }

    def create_project(self):
        url = "{URL}/organizations/{ORG_NAME}/projects".format(URL=self.url,
                                                               WORKSPACE_NAME=self.workspace_name, ORG_NAME=self.org_name)
        payload = {
            "data": {
                "attributes": {
                    "name": self.project_name
                },
                "type": "projects"
            }
        }
        self.log("create_project request", payload)
        x = requests.post(
            url, data=json.dumps(payload), headers=self.headers)
        self.log("create_project response", x)
        x = x.json()

        project_id = x["data"]["id"]
        self.project_id = project_id
        return x, project_id

    def get_project_by_name(self):
        url = "{URL}/organizations/{ORG_NAME}/projects?q={PROJECT_NAME}".format(URL=self.url,
                                                                                WORKSPACE_NAME=self.workspace_name, ORG_NAME=self.org_name, PROJECT_NAME=self.project_name)

        x = requests.get(
            url, headers=self.headers)
        self.log("get_project_by_name response", x)

        x = x.json()
        if not x["data"]:
            return None, None

        project_id = x["data"][0]["id"]
        self.project_id = project_id
        return x, project_id

    def get_project(self):
        url = "{URL}/projects/{PROJECT_ID}".format(URL=self.url,
                                                   PROJECT_ID=self.project_id)
        x = requests.get(
            url, headers=self.headers)
        self.log("get_project response", x)
        if x.status_code != 200:
            return None, None
        x = x.json()

        project_id = x["data"]["id"]
        self.project_id = project_id
        return x, project_id

    def delete_project(self):
        url = "{URL}/projects/{PROJECT_ID}".format(URL=self.url,
                                                   PROJECT_ID=self.project_id)
        x = requests.delete(
            url, headers=self.headers)
        self.log("delete_project response", x)

    def create_workspace(self):
        url = "{URL}/organizations/{ORG_NAME}/workspaces".format(URL=self.url,
                                                                 WORKSPACE_NAME=self.workspace_name, ORG_NAME=self.org_name)

        payload = {
            "data": {
                "attributes": {
                    "name": self.workspace_name,
                    "auto-apply": False,
                    "queue-all-runs": False
                },
                "relationships": {
                    "project": {
                        "data": {
                            "id": self.project_id
                        }
                    }
                },
                "type": "workspaces"
            }
        }
        self.log("create_workspace request", payload)
        x = requests.post(
            url, data=json.dumps(payload), headers=self.headers)
        self.log("create_workspace response", x)
        x = x.json()

        workspace_id = x["data"]["id"]
        return x, workspace_id

    def safe_delete_workspace(self):
        url = "{URL}/organizations/{ORG_NAME}/workspaces/{WORKSPACE_NAME}/actions/safe-delete".format(URL=self.url,
                                                                                                      WORKSPACE_NAME=self.workspace_name, ORG_NAME=self.org_name)

        x = requests.post(
            url, headers=self.headers)
        self.log("safe_delete_workspace response", x)

    def delete_workspace(self):
        url = "{URL}/organizations/{ORG_NAME}/workspaces/{WORKSPACE_NAME}".format(URL=self.url,
                                                                                  WORKSPACE_NAME=self.workspace_name, ORG_NAME=self.org_name)

        x = requests.delete(
            url, headers=self.headers)
        self.log("delete_workspace response", x)

    def get_workspace(self):

        url = "{URL}/organizations/{ORG_NAME}/workspaces/{WORKSPACE_NAME}".format(URL=self.url,
                                                                                  WORKSPACE_NAME=self.workspace_name, ORG_NAME=self.org_name)

        x = requests.get(
            url, headers=self.headers)
        self.log("get_workspace response", x)
        x = x.json()
        if "errors" in x:
            return None, None

        workspace_id = x["data"]["id"]
        return x, workspace_id

    def create_configuration_version(self):
        url = "{URL}/workspaces/{WORKSPACE_ID}/configuration-versions".format(URL=self.url,
                                                                              WORKSPACE_ID=self.workspace_id)

        payload = {
            "data": {
                "type": "configuration-versions",
                "attributes": {
                    "auto-queue-runs": False
                }
            }
        }
        self.log("create_configuration_version request", payload)
        x = requests.post(
            url, data=json.dumps(payload), headers=self.headers)
        self.log("create_configuration_version response", x)
        x = x.json()

        upload_url = x["data"]["attributes"]["upload-url"]
        version = x["data"]["id"]
        return x, version, upload_url

    def get_config_version(self, version):
        url = "{URL}/configuration-versions/{VERSION}".format(URL=self.url,
                                                              VERSION=version)

        x = requests.get(
            url, headers=self.headers)
        self.log("get_config_version response", x)
        x = x.json()

        status = x["data"]["attributes"]["status"]
        return x, status

    def create_run(self, config_version, variables, apply=True, destroy=False):
        url = "{URL}/runs".format(URL=self.url)

        payload = {
            "data": {

                "attributes": {
                    "message": "Run from Humanitec Driver",
                    "auto-apply": apply,
                    "variables": variables,
                    "is-destroy": destroy,
                    "allow-empty-apply": True,
                    "plan-only": False
                },
                "type": "runs",
                "relationships": {
                    "workspace": {
                        "data": {
                            "type": "workspaces",
                            "id": self.workspace_id
                        }
                    },
                    "configuration-version": {
                        "data": {
                            "type": "configuration-versions",
                            "id": config_version
                        }
                    }
                }
            }
        }
        self.log("create_run request", payload)
        x = requests.post(
            url, data=json.dumps(payload), headers=self.headers)
        self.log("create_run response", x)
        x = x.json()

        id = x["data"]["id"]
        return x, id

    def get_run(self, run):
        url = "{URL}/runs/{RUN}".format(URL=self.url,
                                        RUN=run)

        x = requests.get(
            url, headers=self.headers)
        self.log("get_run response", x)
        x = x.json()

        status = x["data"]["attributes"]["status"]
        return x, status

    def get_run_status(self, status):
        if status in ["errored", "discarded", "policy_soft_failed", "force_canceled", "canceled"]:
            return 400
        if status in ["applied", "planned_and_finished"]:
            return 200
        return 202

    def upload_file(self, upload_url, tar_file):
        h = {
            "Content-Type": "application/octet-stream"
        }

        with open(tar_file, 'rb') as f:
            data = f.read()
        x = requests.put(upload_url, data=data, headers=h)
        self.log("upload_file response", x)

    def add_workspace_variable(self, k, v):
        url = "{URL}/workspaces/{WORKSPACE_ID}/vars".format(URL=self.url,
                                                            WORKSPACE_ID=self.workspace_id)

        payload = {
            "data": {
                "type": "vars",
                "attributes": {
                    "key": k,
                    "value": v,
                    "category": "env",
                    "hcl": False,
                    "sensitive": False
                }
            }
        }
        self.log("add_workspace_variable request", payload)
        x = requests.post(
            url, data=json.dumps(payload), headers=self.headers)
        self.log("add_workspace_variable response", x)

    def update_workspace_variable(self, k, v, id):
        url = "{URL}/workspaces/{WORKSPACE_ID}/vars/{VAR_ID}".format(URL=self.url,
                                                                     WORKSPACE_ID=self.workspace_id, VAR_ID=id)

        payload = {
            "data": {
                "type": "vars",
                "id": id,
                "attributes": {
                    "key": k,
                    "value": v,
                    "category": "env",
                    "hcl": False,
                    "sensitive": False
                }
            }
        }
        self.log("update_workspace_variable request", payload)
        x = requests.patch(
            url, data=json.dumps(payload), headers=self.headers)
        self.log("update_workspace_variable response", x)

    def delete_workspace_variable(self, id):
        url = "{URL}/workspaces/{WORKSPACE_ID}/vars/{VAR_ID}".format(URL=self.url,
                                                                     WORKSPACE_ID=self.workspace_id, VAR_ID=id)

        x = requests.delete(
            url, headers=self.headers)
        self.log("delete_workspace_variable response", x)

    def get_workspace_variable(self, k):
        url = "{URL}/workspaces/{WORKSPACE_ID}/vars".format(URL=self.url,
                                                            WORKSPACE_ID=self.workspace_id)

        x = requests.get(
            url, headers=self.headers)
        self.log("get_workspace_variable response", x)

        x = x.json()
        for v in x["data"]:
            if v["attributes"]["key"] == k:
                return v, v["attributes"]["value"]
        return None, None

    def get_state_version_output(self, wsout):
        url = "{URL}/state-version-outputs/{WSOUT}".format(URL=self.url,
                                                           WSOUT=wsout)

        x = requests.get(
            url, headers=self.headers)
        self.log("get_state_version_output response", x)
        x = x.json()

        k = x["data"]["attributes"]["name"]
        v = x["data"]["attributes"]["value"]
        sensitive = x["data"]["attributes"]["sensitive"]
        return k, v, sensitive

    def get_current_state_version_outputs(self):
        w, _ = self.get_workspace()

        outputs = w["data"]["relationships"]["outputs"]["data"]

        values = {}
        secrets = {}
        for output in outputs:
            if output["type"] == "workspace-outputs":
                wsout = output["id"]
                k, v, sensitive = self.get_state_version_output(wsout)
                if sensitive:
                    secrets[k] = v
                else:
                    values[k] = v

        return values, secrets
