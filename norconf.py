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


def data_validation(task):
    """Load the input YAML data and validates"""

    # Load Data
    loaded_data = task.run(task=load_yaml, file=f"data/{task.host}.yml")
    # Store the contents as a host dict
    task.host["CUST_VRFS"] = loaded_data.result

    for cust, data in task.host["CUST_VRFS"].items():
        for vrf in data:
            assert vrf["ASN"]
            assert vrf["RD"]
            assert vrf["RT"]

def nc_deployment(task):
    """Render the templates for VPRN/L3VPN deployment. """

    # Assign a template based on device platform.
    template = f"{task.host.platform}-vrf.j2"

    vrf = task.run(
        task=template_file,
        path="templates/",
        template=template,
    )

    # Extract the custom data.target attribute passed into the group of hosts to specifcy 'candidate' target
    # configuration store to run the edit_config rpc against on our device.
    deploy_config = task.run(
        task=netconf_edit_config, target=task.host["target"], config=str(vrf.result)
    )

    if "<ok/>" in deploy_config.result:
        task.run(task=netconf_commit)
        return f"NETCONF RPC = OK. Committing Changes:: {task.host.platform}"
    else:
        return f"NETCONF Error. {rpcreply}"

def cli_stats(task):
    """Simple CLI commands to validate and save output"""

    # Extract servicename and perform show commands 
    for cust, data in task.host["CUST_VRFS"].items():
        for vrf in data:
            servicename = vrf['SERVICE_NAME']

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

def routing_validation(task):

    if task.host.platform == "alcatel_sros":
        command = 'ping router-instance "AVIFI" 1.1.1.1'

        ping_iosxrlo = task.run(
            netmiko_send_command, command_string=command
        )
        assert '0.00% packet loss' in ping_iosxrlo.result


def main():

    print_result(west_region.run(task=data_validation))

    print_result(west_region.run(task=nc_deployment))

    print_result(west_region.run(task=cli_stats))

    print_result(west_region.run(task=routing_validation))

if __name__ == "__main__":
    main()
