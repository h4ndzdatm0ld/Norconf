from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from nornir_utils.plugins.tasks.data import load_yaml
from nornir_jinja2.plugins.tasks import template_file
from nornir_napalm.plugins.tasks import napalm_validate
from nornir_napalm.plugins.tasks import napalm_get
from nornir_napalm.plugins.tasks import napalm_ping
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
    """Load the input YAML data and validate required values are present."""

    # Load Data
    loaded_data = task.run(task=load_yaml, file=f"data/{task.host}.yml")
    # Store the contents as a host dict
    task.host["CUST_VRFS"] = loaded_data.result

    for cust, data in task.host["CUST_VRFS"].items():
        for vrf in data:
            assert vrf["ASN"]
            assert vrf["RD"]
            assert vrf["RT"]
            assert type(vrf["ASN"]) == int
            assert type(vrf["RD"]) == int
            assert type(vrf["RT"]) == int


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

    # Ensure the RPC REPLY was successfull before we commit our changes.
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
            servicename = vrf["SERVICE_NAME"]

    # Path to save output: This path will be generated.
    path = f"Output/{task.host.platform}"
    createFolder(path)

    if task.host.platform == "alcatel_sros":
        vprn = task.run(
            netmiko_send_command, command_string=f"show service id {servicename} base"
        )
        write_file(
            task,
            filename=f"{path}/{task.name}-{servicename}.txt",
            content=str(vprn.result),
        )

    elif task.host.platform == "iosxr":
        vrf = task.run(
            netmiko_send_command, command_string=f"sh vrf {servicename} detail"
        )
        write_file(
            task, filename=f"{path}/{task.name}-{servicename}.txt", content=str(vrf)
        )

    else:
        return f"{task.host.platform} Not supported in this runbook"


def routing_validation(task):
    """Two forms of validation. Unfortunately, SROS NAPALM is not fully integrated into the major framework, so we will provide a workaround.
    As for IOSXR, it's fully supported. Use napalm validators to ensure BGP peers are established.
    Individual test cases are stored under /tests/{host} directory."""

    if task.host.platform == "alcatel_sros":
        command = 'ping router-instance "AVIFI" 1.1.1.1 rapid'
        ping_iosxrlo = task.run(netmiko_send_command, command_string=command)
        assert "0.00% packet loss" in ping_iosxrlo.result

    elif task.host.platform == 'iosxr':
        task.run(task=napalm_get, getters=["get_bgp_neighbors"])
        task.run(task=napalm_validate, src=f"tests/{task.host}-compliance.yml")

        command = 'ping 3.3.3.3 vrf AVIFI'
        ping_sros = task.run(netmiko_send_command, command_string=command)
        assert "Success rate is 100 percent" in ping_sros.result

    else:
        return "platform not specified or supported."

def main():

    createFolder("Logs")

    # print_result(west_region.run(task=data_validation))

    # print_result(west_region.run(task=nc_deployment))

    # print_result(west_region.run(task=cli_stats))

    print_result(west_region.run(task=routing_validation))


if __name__ == "__main__":
    main()
