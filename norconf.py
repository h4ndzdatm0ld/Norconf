
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from nornir_utils.plugins.tasks.data import load_yaml
from nornir_jinja2.plugins.tasks import template_file
from nornir_netconf.plugins.tasks import netconf_edit_config, netconf_get_config
from nc_tasks import netconf_edit_config, netconf_commit
import xmltodict, json, pprint


# from nornir.core.plugins.connections import ConnectionPluginRegister

# from nornir_netconf.plugins.connections import Netconf

# ConnectionPluginRegister.register("netconf", ConnectionPluginRegister)

__author__ = 'Hugo Tinoco'
__email__ = 'hugotinoco@icloud.com'

# Specify a custom config yaml file.
nr = InitNornir('config.yml')

# Filter the hosts by the 'west-region' site key.
west_region = nr.filter(region='west-region')

def get_vrf(task, servicename):
    ''' Retrieve interfaces from IOS and NOKIA devices(Base).
    '''
    if task.host.platform == 'iosxr':
        vrf = task.run(netmiko_send_command, command_string= f"sh vrf {servicename} detail")
        print(vrf)

    elif task.host.platform == 'alcatel_sros':
        vrf = task.run(netmiko_send_command, command_string= f"show service id {servicename} base")
        print(vrf)

    else:
        print(f"{task.host} | {task.host.platform} not supported in this runbook.")

def nc_getvprn(task, servicename, customerid, serviceid=None):
    ''' Validate and compare the intended customer against the 7750 core device.
    '''
    r = task.run(task=netconf_get_config)
    config = r.result
    dict_config = xmltodict.parse(config)    
    try:
        customers = dict_config['data']['configure']['service']['customer']
        for cust in customers:
            if cust['customer-id'] == customerid:
                print(f"SR Customer: {cust['customer-name']}")
                print(f"SR Customer ID: {cust['customer-id']}")
            elif cust['customer-id'] != customerid:
                pass
            else:
                print("Can't find {customerid}")
        services = dict_config['data']['configure']['service']['vprn']
        for vprn in services:
            if vprn['service-name'] == servicename:
                print(f'SR Service Name: {servicename}')
            elif vprn['service-name'] != servicename:
                pass
            else:
                print(f"Can't find Service: {servicename}")
        else: 
            pass
    except Exception as e:
        print(f'Error with nc_getcust function:: {e}')

def iac_render(task):
    ''' Load the YAML vars and render the Jinja2 Templates. Deploy L3VPN/VPRN via NETCONF.
    Once configuration is committed, validate via Netmiko / simple show commands.
    '''
    
    # Load Yaml Files by Hostname
    vars_yaml = f"vars/{task.host}.yml"
    vars_data = task.run(task=load_yaml, file=vars_yaml)

    # With the YAML variables loaded, render the Jinja2 Template with the previous function: iac_render.
    template= f"{task.host.platform}-vrf.j2"

    vprn = task.run(task=template_file, path='templates/', template=template, data=vars_data.result['VRF'])

    # Convert the generated template into a string.
    payload = str(vprn.result)

    # Extract the custom data.target attribute passed into the group of hosts to specifcy 'candidate' target
    # configuration store to run the edit_config rpc against on our task.device. 
    # IOSXR/Nokia take advantage of candidate/lock via netconf.
    deploy_config = task.run(task=netconf_edit_config, target=task.host['target'], config=payload)

    # # Extract the new Service ID Created:
    if task.host.platform == 'alcatel_sros':
        for vrf in vars_data.result['VRF']:
            serviceid = vrf['SERVICE_ID']
            servicename = vrf['SERVICE_NAME'] 
            # Ensure the customer - id is always interpreted as a string:
            customer = vrf['CUSTOMER_ID']
            customerid = str(customer)

    if task.host.platform == 'iosxr':
        for vrf in vars_data.result['VRF']:
            servicename = vrf['SERVICE_NAME']
            serviceid = None


    rpcreply = deploy_config.result 
    
    # if 'ok' in result:
    if rpcreply.ok:

        print(f"NETCONF RPC = OK. Committing Changes:: {task.host.platform}")
        task.run(task=netconf_commit)

        # Validate service on the 7750.
        if task.host.platform == 'alcatel_sros':
            nc_getvprn(task, serviceid=serviceid, servicename=servicename, customerid=customerid)

        # Validate via Netmiko the output of the VRF/VPRNs on both devices:
        # get_vrf(task, servicename=servicename)

    elif rpcreply != rpcreply.ok:
        print(rpcreply)

    else:
        print("NETCONF Error.")

def main():

    complete = west_region.run(task=iac_render)
    print(complete)

    # servicename = 'AVIFI'

    # print_result(west_region.run(task=get_vrf, servicename=servicename))

if __name__=="__main__":
    main()