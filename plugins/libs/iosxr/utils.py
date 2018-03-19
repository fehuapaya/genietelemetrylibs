
# Python
import re
import logging

# ATS
from ats.log.utils import banner

# GenieMonitor
from genie.telemetry.status import OK, WARNING, ERRORED, PARTIAL, CRITICAL

# abstract
from abstract import Lookup

# Unicon
from unicon.eal.dialogs import Statement, Dialog

# TFTPUtils
import filetransferutils
from filetransferutils.ssh import Ssh

# module logger
logger = logging.getLogger(__name__)


def check_cores(device, core_list, **kwargs):

    # Init
    status = OK
    timeout = kwargs['timeout']
    
    # Execute command to check for cores
    for location in ['disk0:', 'disk0:core', 'harddisk:']:
        try:
            output = device.execute('dir {}'.format(location), timeout=timeout)
        except Exception as e:
            # Handle exception
            logger.warning(e)
            logger.warning(banner("Location '{}' does not exist on device".format(location)))
            continue
        
        if 'Invalid input detected' in output:
            logger.warning(banner("Location '{}' does not exist on device".format(location)))
            continue
        elif not output:
            meta_info = "Unable to check for cores"
            logger.error(banner(meta_info))
            return ERRORED(meta_info)

        # 24 -rwxr--r-- 1 18225345 Oct 23 05:15 ipv6_rib_9498.by.11.20170624-014425.xr-vm_node0_RP0_CPU0.237a0.core.gz
        pattern1 = '(?P<number>(\d+)) +(?P<permissions>(\S+)) +(?P<other_number>(\d+)) +(?P<filesize>(\d+)) +(?P<month>(\S+)) +(?P<date>(\d+)) +(?P<time>(\S+)) +(?P<core>(.*core\.gz))'
        # 12089255    -rwx  23596201    Tue Oct 31 05:16:50 2017  ospf_14495.by.6.20171026-060000.xr-vm_node0_RP0_CPU0.328f3.core.gz
        pattern2 = '(?P<number>(\d+)) +(?P<permissions>(\S+)) +(?P<filesize>(\d+)) +(?P<day>(\S+)) +(?P<month>(\S+)) +(?P<date>(\d+)) +(?P<time>(\S+)) +(?P<year>(\d+)) +(?P<core>(.*core\.gz))'

        for line in output.splitlines():
            # Parse through output to collect core information (if any)
            match = re.search(pattern1, line, re.IGNORECASE) or \
                    re.search(pattern2, line, re.IGNORECASE)
            if match:
                core = match.groupdict()['core']
                meta_info = "Core dump generated:\n'{}'".format(core)
                logger.error(banner(meta_info))
                status += CRITICAL(meta_info)
                core_info = dict(location = location,
                                 core = core)
                core_list.append(core_info)

        if not core_list:
            meta_info = "No cores found at location: {}".format(location)
            logger.info(banner(meta_info))
            status += OK(meta_info)

    return status


def upload_to_server(device, core_list, *args, **kwargs):

    # Init
    status= OK

    # Get info
    port = kwargs['port']
    server = kwargs['server']
    timeout = kwargs['timeout']
    destination = kwargs['destination']
    protocol = kwargs['protocol']
    username = kwargs['username']
    password = kwargs['password']

    # Check values are not None
    for item in [protocol, server, destination, username, password]:
        if item is None:
            meta_info = "Unable to upload core dump - parameters not provided"
            return ERRORED(meta_info)

    # Got a tftp, set it up
    # Get the information needed
    scp = Ssh(ip=server)
    scp.setup_scp()

    # Get the corresponding filetransferutils Utils implementation
    tftpcls = Lookup(device.os).filetransferutils.tftp.utils.Utils(
        scp, kwargs['destination'])

    # Upload each core found
    for item in core_list:

        message = "Core dump upload attempt from {} to {} via server {}".format(
            item['location'], destination, server)

        try:
            tftpcls.copy_core(device, item['location'], item['core'],
                                       server=server, destination=destination,
                                       port=port, timeout=timeout,
                                       username=username, password=password)
        except Exception as e:
            if 'Tftp operation failed' in e:
                meta_info = "Core dump upload operation failed: {}".format(
                    message)
                logger.error(banner(meta_info))
                status += ERRORED(meta_info)
            else:
                # Handle exception
                logger.warning(e)
                status += ERRORED("Failed: {}".format(message))

        meta_info = "Core dump upload operation passed: {}".format(message)
        logger.info(banner(meta_info))
        status += OK(meta_info)

    return status


def clear_cores(device, core_list, crashreport_list, **kwargs):

    # Create dialog for response
    dialog = Dialog([
        Statement(pattern=r'Delete.*',
                  action='sendline()',
                  loop_continue=True,
                  continue_timer=False),
        ])

    # preparing the full list to iterate over
    full_list = core_list + crashreport_list

    # Delete cores from the device
    for item in full_list:
        try:
            # Execute delete command for this core
            cmd = 'delete {location}/{core}'.format(
                    core=item['core'],location=item['location'])
            output = device.execute(cmd, timeout=300, reply=dialog)
            # Log to user
            meta_info = 'Successfully deleted {location}/{core}'.format(
                        core=item['core'],location=item['location'])
            logger.info(banner(meta_info))
            return OK(meta_info)
        except Exception as e:
            # Handle exception
            logger.warning(e)
            meta_info = 'Unable to delete {location}/{core}'.format(
                        core=item['core'],location=item['location'])
            logger.error(banner(meta_info))
            return ERRORED(meta_info)

def check_tracebacks(device, timeout, **kwargs):

    # Execute command to check for tracebacks
    output = device.execute('show logging', timeout=timeout)

    return output

def clear_tracebacks(device, timeout, **kwargs):

    # Execute command to clear tracebacks
    output = device.execute('clear logging', timeout=timeout)

    return output
