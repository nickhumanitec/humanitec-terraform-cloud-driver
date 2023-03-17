from tfc import *

import deepdiff
import base64
import requests


import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def main(local, terraform_variables, cookie):

    tf = TerraformCloud(cookie["tfc_organization_name"],
                        cookie["tfc_token"], cookie["tfc_project_name"],  cookie["tfc_workspace_name"], log)

    if local["action"] == "DELETE":
        # get last run, if it's a destroy and 200, return OK, otherwise wait
        # if not a destroy, create a destroy run  and wait
        w, _ = tf.get_workspace()
        r = w.get("data", {})["relationships"]["latest-run"].get("data", {})
        if r != None:
            r = w.get("data", {})[
                "relationships"]["latest-run"].get("data", {})["id"]
            r, status = tf.get_run(r)

            if r.get("data", {})["attributes"]["is-destroy"]:
                status = tf.get_run_status(status)

                if status == 200:
                    c, _ = tf.get_workspace_variable("HUMANITEC_SHA")
                    if c:
                        tf.delete_workspace_variable(c["id"])

                    tf.safe_delete_workspace()
                    tf.delete_project()

                    return get_response(debug="delete: ok",
                                        cookie=cookie, body="", status=204)
                elif status == 400:

                    return get_response(
                        cookie=cookie, body=get_error(message="delete: failed"), status=400)
                else:
                    return get_response(
                        cookie=cookie, body=get_wait(status="delete: wait"), status=202)
            else:
                _, run_id = tf.create_run(
                    None, None, apply=True, destroy=True)
                cookie["tfc_run_id"] = run_id
                return get_response(cookie=cookie, body=get_wait(status="delete: accepted, wait"), status=202)
        else:

            if w.get("data", {})["attributes"]["resource-count"] == 0:
                tf.safe_delete_workspace()
                return get_response(debug="delete: ok, no run found, no resources found",
                                    cookie=cookie, body="", status=204)

            return get_response(cookie=cookie, body=get_error(message="delete: failed, no run found but resources in workspace or another error"), status=400)

    if local["action"] == "PUT":

        latest_run = cookie["tfc_run_id"]

        updateCode = False
        reRun = False
        firstRun = False

        _, incoming_commit = get_github_latest_commit(
            local["source_commit"], cookie["github_token"])

        # existing run, get status
        if latest_run != "":

            latest_run, status = tf.get_run(latest_run)

            status = tf.get_run_status(status)

            if status == 200:

                # latest run finished, do I have new code? updateCode
                _, current_commit = tf.get_workspace_variable(
                    "HUMANITEC_SHA")

                if incoming_commit != current_commit:
                    updateCode = True

                # latest run finished, do I have diff variables? reRun
                current_variables = latest_run.get(
                    "data", {})["attributes"]["variables"]
                ddiff = deepdiff.DeepDiff(
                    terraform_variables, current_variables, ignore_order=True)
                if ddiff != {}:
                    reRun = True

                # nothing to do, return 200 with outputs
                if reRun == False and updateCode == False:

                    values, secrets = tf.get_current_state_version_outputs()
                    body = get_body(
                        id=local["id"], resource_type=local["type"], values=values, secrets=secrets)

                    return get_response(debug="update: ok",
                                        cookie=cookie, body=body, status=status)

            elif status == 400:
                return get_response(cookie=cookie, body=get_error(message="update: failed"), status=status)
            else:
                return get_response(cookie=cookie, body=get_wait(status="update: waiting to finish an update"), status=202)

        if latest_run == "":
            firstRun = True

        if firstRun or updateCode or reRun:

            # TODO: getting source code and pushing it to TF Cloud can take long time, make async

            if updateCode or firstRun:  # this also reRun with new variables

                clean_tmp(local["download_folder"], local["decompress_folder"])

                h = {}
                if cookie["github_token"] != "":
                    h = {"Authorization": "Bearer {TOKEN}".format(
                        TOKEN=cookie["github_token"])}
                r = requests.get(local["source_zip"],
                                 allow_redirects=True, headers=h)
                open(local["downloaded_file"], 'wb').write(r.content)

                make_tarfile(local["decompress_folder"],
                             local["downloaded_file"], local["source_tar"], local["compress_folder"])

                _, config_version, upload_url = tf.create_configuration_version()
                tf.upload_file(upload_url, local["source_tar"])
                _, run_id = tf.create_run(
                    config_version, terraform_variables, apply=True)
                cookie["tfc_run_id"] = run_id

            if reRun:  # reuse existing code
                _, run_id = tf.create_run(
                    None, terraform_variables, apply=True)
                cookie["tfc_run_id"] = run_id

            # store or update the commit id, used to see if we need to updateCode later
            c, _ = tf.get_workspace_variable("HUMANITEC_SHA")
            if not c:
                tf.add_workspace_variable("HUMANITEC_SHA", incoming_commit)
            else:
                tf.update_workspace_variable(
                    "HUMANITEC_SHA", incoming_commit, c["id"])

            # always return 202
            debug = "firstRun: {}, updateCode: {}, reRun: {}. : waiting".format(
                firstRun, updateCode, reRun)
            return get_response(cookie=cookie, body=get_wait(status=debug), status=202)


def lambda_handler(event, context):
    logger.debug("## lambda_handler event")
    logger.debug(event)
    logger.debug("## lambda_handler body")
    logger.debug(json.loads(event.get("body", "{}")))

    action = event["requestContext"]["http"]["method"]
    if action not in ["PUT", "DELETE"]:
        return get_response(cookie="", body=get_error(message="bad request"), status=400)
    id = event["requestContext"]["http"]["path"][1:]
    cookie = event.get("headers", {}).get("humanitec-driver-cookie", "")

    if cookie != "":
        cookie = json.loads((base64.b64decode(cookie)).decode())

    inputs = json.loads(event.get("body", "{}"))

    type = inputs.get("type", {})

    if action == "PUT":
        driver = inputs["driver"]

        source = driver["values"].get("data", {}).get("source")
        humanitec = driver["values"].get("data", {}).get("humanitec")

        local = {
            "id": id,
            "action": action,
            "type": type,
            "source_zip": source["source_zip"],
            "source_commit": source["source_commit"],
            "download_folder": "/tmp/download/",
            "downloaded_file": "/tmp/download/{branch}.zip".format(branch=source["branch"]),
            "decompress_folder": "/tmp/download/{branch}/".format(branch=source["branch"]),
            "source_tar": "/tmp/download/{branch}.tar.gz".format(branch=source["branch"]),
            "compress_folder": "/tmp/download/{branch}/{path}".format(branch=source["branch"], path=source["path"])
        }

        terraform_variables = driver["values"].get("data", {}).get(
            "terraform_variables", [])

        terraform_secrets = driver["secrets"].get("data", {}).get(
            "terraform_secrets", [])

        terraform_variables = terraform_variables + terraform_secrets

        # update or create cookie with the latest token and info, this is used later on for the DELETE event,
        # api v1 does not send tokens and information to perform a delete
        secrets = driver["secrets"].get("data", {})
        tfcloud = driver["values"].get("data", {}).get("terraform_cloud")
        if cookie == "":
            cookie = {
                "tfc_organization_name": tfcloud["organization_name"],
                "tfc_project_name": ("humanitec-{org}-{app}".format(org=clean_name(humanitec["org"]), app=clean_name(humanitec["app"]))).lower(),
                "tfc_workspace_name": ("{env}-{res}".format(env=clean_name(humanitec["env"]), res=clean_name(humanitec["res"]))).lower(),
                "tfc_token": secrets["tfc_token"],
                "github_token": secrets["github_token"],
                "tfc_run_id": ""
            }
        else:
            cookie["tfc_token"] = secrets["tfc_token"]
            cookie["github_token"] = secrets["github_token"]

    if action == "DELETE":
        local = {
            "id": id,
            "action": action
        }
        secrets = None
        tfcloud = None
        terraform_variables = None

    x = main(local, terraform_variables, cookie=cookie)
    logger.debug("## lambda_handler response")
    logger.debug(x)
    return x


if __name__ == "__main__":
    pass
