
# Python
import time
import logging
from datetime import datetime

# ATS
from ats.log.utils import banner

# GenieMonitor
from geniemonitor.results import OK, WARNING, ERRORED, PARTIAL, CRITICAL

# Parsergen
from parsergen import oper_fill_tabular

# abstract
from abstract import Lookup

# TFTPUtils
import tftp_utils

# Unicon
from unicon.eal.dialogs import Statement, Dialog

# ssh
from ..ssh import Ssh

# module logger
logger = logging.getLogger(__name__)


def check_cores(device, core_list, **kwargs):

    # Init
    status = OK

    # Execute command to check for cores
    header = [ "VDC", "Module", "Instance",
                "Process\-name", "PID", "Date\(Year\-Month\-Day Time\)" ]
    output = oper_fill_tabular(device = device, 
                               show_command = 'show cores vdc-all',
                               header_fields = header, index = [5])

    if not output.entries:
        meta_info = "No cores found!"
        logger.info(banner(meta_info))
        return OK(meta_info)
    
    # Parse through output to collect core information (if any)
    for k in sorted(output.entries.keys(), reverse=True):
        row = output.entries[k]
        date = row.get("Date\\(Year\\-Month\\-Day Time\\)", None)
        if not date:
            continue
        date_ = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')

        # Save core info
        core_info = dict(module = row['Module'],
                         pid = row['PID'],
                         instance = row['Instance'],
                         process = row['Process\\-name'],
                         date = date.replace(" ", "_"))
        core_list.append(core_info)

        meta_info = "Core dump generated for process '{}' at {}".format(
            row['Process\\-name'], date_)
        logger.error(banner(meta_info))
        status += CRITICAL(meta_info)

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

    # Get the corresponding tftputils implementation
    tftpcls = Lookup.from_device(device).tftp_utils.tftp.tftp.TFTPUtils(
        scp, kwargs['destination'])

    # Upload each core found
    for core in core_list:
        # Sample command:
        # copy core://<module-number>/<process-id>[/instance-num]
        #      tftp:[//server[:port]][/path] vrf management
        path = '{dest}/core_{pid}_{process}_{date}_{time}'.format(
                                                   dest = destination,
                                                   pid = core['pid'],
                                                   process = core['process'],
                                                   date = core['date'],
                                                   time = time.time())
        if port:
            server = '{server}:{port}'.format(server = server, port = port)

        if 'instance' in core:
            pid = '{pid}/{instance}'.format(pid = core['pid'],
                                            instance = core['instance'])

        message = "Core dump upload attempt from {} to {} via server {}".format(
            core['module'], destination, server)

        # construction the module/pid for the copy process
        core['core'] = '{module}/{pid}'.format(module = core['module'],
                                               pid = core['pid'])
        try:
            tftpcls.save_core(device=device, location='core:/',
                              core=core['core'], server=server,
                              destination=path, port=port, vrf='management',
                              timeout=timeout, username=username,
                              password=password)
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


def clear_cores(device, core_list, **kwargs):

    # Execute command to delete cores
    try:
        device.execute('clear cores')
        meta_info = "Successfully cleared cores on device"
        logger.info(banner(meta_info))
        status = OK(meta_info)
    except Exception as e:
        # Handle exception
        logger.warning(e)
        meta_info = "Unable to clear cores on device"
        logger.error(meta_info)
        status = ERRORED(meta_info)

    return status
