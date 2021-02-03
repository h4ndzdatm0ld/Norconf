from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from nornir_utils.plugins.tasks.data import load_yaml
from nornir_jinja2.plugins.tasks import template_file
import xmltodict
import json
import pprint
import os
from nornir_utils.plugins.tasks.files import write_file
from nornir_scrapli.tasks import (
    netconf_lock,
    netconf_unlock,
    netconf_edit_config,
    netconf_get,
    netconf_get_config,
    netconf_rpc,
    netconf_commit,
)

__author__ = "Hugo Tinoco"
__email__ = "hugotinoco@icloud.com"

nr = InitNornir("config.yml")

# Filter the hosts by the 'west-region' site key.
west_region = nr.filter(region="west-region")


def createFolder(directory):
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError:
        print("Error: Creating directory. " + directory)


def nc_deployment(task):
    """Load the YAML vars and render the Jinja2 Templates. Deploy L3VPN/VPRN via NETCONF."""

    # Load Yaml file to extract specific vars
    loaded_data = task.run(task=load_yaml, file=f"data/{task.host}.yml")
    # Store the contents as a host dict
    task.host['CUST_VRFS'] = loaded_data.result
    # Assign a template based on device platform.
    template = f"{task.host.platform}-vrf.j2"
    # Rendering Template
    vrf = task.run(
        task=template_file,
        path="templates/",
        template=template,
    )
    # Extract the custom data.target attribute passed into the group of hosts to specifcy 'candidate' target
    # configuration store to run the edit_config rpc against on our task.device.

    # IOSXR/Nokia take advantage of candidate/lock via netconf.
    deploy_config = task.run(
        task=netconf_edit_config, target=task.host["target"], config=str(vrf.result)
    )

    # # # Extract the new Service ID Created:
    # if task.host.platform == "alcatel_sros":
    #     for vrf in vars_data.result["VRF"]:
    #         serviceid = vrf["SERVICE_ID"]
    #         servicename = vrf["SERVICE_NAME"]
    #         # Ensure the customer - id is always interpreted as a string:
    #         customer = vrf["CUSTOMER_ID"]
    #         customerid = str(customer)

    # if task.host.platform == "iosxr":
    #     for vrf in vars_data.result["VRF"]:
    #         servicename = vrf["SERVICE_NAME"]
    #         serviceid = None

    # rpcreply = deploy_config.result

    # # if 'ok' in result:
    # if rpcreply.ok:

    #     print(f"NETCONF RPC = OK. Committing Changes:: {task.host.platform}")
    #     task.run(task=netconf_commit)

    #     # Validate service on the 7750.
    #     if task.host.platform == "alcatel_sros":
    #         nc_getvprn(
    #             task,
    #             serviceid=serviceid,
    #             servicename=servicename,
    #             customerid=customerid,
    #         )

    #     elif task.host.platform == "iosxr":
    #         pass
    #         # Duplicate the getvprn function but for iosxr

    # elif rpcreply != rpcreply.ok:
    #     print(rpcreply)

    # else:
    #     print(f"NETCONF Error. {rpcreply}")


def nc_getvprn(task, servicename, customerid, serviceid=None):
    """Validate and compare the intended customer against the 7750 core device."""
    r = task.run(task=netconf_get_config)
    config = r.result
    dict_config = xmltodict.parse(config)
    try:
        customers = dict_config["data"]["configure"]["service"]["customer"]
        for cust in customers:
            if cust["customer-id"] == customerid:
                print(f"SR Customer: {cust['customer-name']}")
                print(f"SR Customer ID: {cust['customer-id']}")
            elif cust["customer-id"] != customerid:
                pass
            else:
                print("Can't find {customerid}")
        services = dict_config["data"]["configure"]["service"]["vprn"]
        for vprn in services:
            if vprn["service-name"] == servicename:
                print(f"SR Service Name: {servicename}")
            elif vprn["service-name"] != servicename:
                pass
            else:
                print(f"Can't find Service: {servicename}")
        else:
            pass
    except Exception as e:
        print(f"Error with nc_getvprn function:: {e}")


    """Load the YAML vars and render the Jinja2 Templates. Deploy L3VPN/VPRN via NETCONF."""

    # Load Yaml Files by Hostname
    vars_yaml = f"vars/{task.host}.yml"
    vars_data = task.run(task=load_yaml, file=vars_yaml)

    # With the YAML variables loaded, render the Jinja2 Template with the previous function: iac_render.
    template = f"{task.host.platform}-vrf.j2"

    vprn = task.run(
        task=template_file,
        path="templates/",
        template=template,
        data=vars_data.result["VRF"],
    )

    # Convert the generated template into a string.
    payload = str(vprn.result)

    # Extract the custom data.target attribute passed into the group of hosts to specifcy 'candidate' target
    # configuration store to run the edit_config rpc against on our task.device.
    # IOSXR/Nokia take advantage of candidate/lock via netconf.
    deploy_config = task.run(
        task=netconf_edit_config, target=task.host["target"], config=payload
    )

    # # Extract the new Service ID Created:
    if task.host.platform == "alcatel_sros":
        for vrf in vars_data.result["VRF"]:
            serviceid = vrf["SERVICE_ID"]
            servicename = vrf["SERVICE_NAME"]
            # Ensure the customer - id is always interpreted as a string:
            customer = vrf["CUSTOMER_ID"]
            customerid = str(customer)

    if task.host.platform == "iosxr":
        for vrf in vars_data.result["VRF"]:
            servicename = vrf["SERVICE_NAME"]
            serviceid = None

    rpcreply = deploy_config.result

    # if 'ok' in result:
    if rpcreply.ok:

        print(f"NETCONF RPC = OK. Committing Changes:: {task.host.platform}")
        task.run(task=netconf_commit)

        # Validate service on the 7750.
        if task.host.platform == "alcatel_sros":
            nc_getvprn(
                task,
                serviceid=serviceid,
                servicename=servicename,
                customerid=customerid,
            )

        elif task.host.platform == "iosxr":
            pass
            # Duplicate the getvprn function but for iosxr

    elif rpcreply != rpcreply.ok:
        print(rpcreply)

    else:
        print(f"NETCONF Error. {rpcreply}")


def cli_stats(task):
    """Revert to CLI scraping automation to retrieve simple show commands and verify status of Services / L3 connectivity."""
    # Load Yaml file to extract specific vars
    # Load Yaml file to extract specific vars
    data = f"data/{task.host}.yml"
    loaded_data = task.run(task=load_yaml, file=data)

    # Capture the Service Name:
    servicename = loaded_data.result["VRF"][0]["SERVICE_NAME"]

    # Path to save output: This path will be auto-created for your below>
    path = f"Output/{task.host.platform}"

    if task.host.platform == "alcatel_sros":
        vprn = task.run(
            netmiko_send_command, command_string=f"show service id {servicename} base"
        )
        # Create the path folder directory.
        createFolder(path)
        # Capture the get_vprn output and write it to a file:
        write_file(
            task,
            filename=f"{path}/{task.name}-{servicename}.txt",
            content=str(vprn.result),
        )

    elif task.host.platform == "iosxr":
        vrf = task.run(
            netmiko_send_command, command_string=f"sh vrf {servicename} detail"
        )
        # Create the path folder directory.
        createFolder(path)
        # Capture the get_vprn output and write it to a file:
        write_file(
            task, filename=f"{path}/{task.name}-{servicename}.txt", content=str(vrf)
        )

    else:
        print(f"{task.host.platform} Not supported in this runbook")


def main():

    # west_region.run(task=nc_getvprn)

    west_region.run(task=nc_deployment)

    # west_region.run(task=cli_stats)


if __name__ == "__main__":
    main()
