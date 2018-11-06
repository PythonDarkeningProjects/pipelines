"""Download Starlingx ISOS"""

from __future__ import print_function

import argparse
import os
import sys

from bash import bash

SERVER_USER = 'jenkins-slave'
SERVER_FOLDER = '/home/jenkins-slave/html/ISO'
RSYNC_CMD = '-avzhe'
SSH_CMD = 'ssh -o StrictHostKeyChecking=no'


def download_isos(number, folder, verbose=False):
    """Download starlingx ISOS

    :param number: the number of isos to download
    :param folder: the folder where the isos will be downloading
    :param verbose: show the progress of rsync command
    """

    progress = '--progress' if verbose else ''
    ssh_cmd = ('ssh -XC {}@{} "ls {} | grep -E \"^stx\" | grep -E \"\.iso$\" '
               '| grep -iv \"**centos**\" "')\
        .format(SERVER_USER, SERVER_IP, SERVER_FOLDER)
    isos_list = bash('{}'.format(ssh_cmd)).stdout.split()
    isos_list.sort()

    if int(number) > len(isos_list):
        sys.exit('err: there is only {} ISOS available in the server'.format(
            len(isos_list)))

    isos_to_download = isos_list[-int(number):]

    for iso in isos_to_download:
        if not os.path.isfile('{}/{}'.format(folder, iso)):
            print('Downloading: {} ...'.format(iso))
            cmd = ('rsync {} "{}" {} {}@{}:{}/{} {}'.format(
                RSYNC_CMD, SSH_CMD, progress, SERVER_USER, SERVER_IP,
                SERVER_FOLDER, iso, folder))
            os.system(cmd)


def evaluate_args(args):
    """Evaluate arguments from arg parse

    :param args: list arguments as objects assigned as attributes
       of a namespace
    """

    # evaluating arguments
    if not os.path.exists(args.folder):
        try:
            os.makedirs(args.folder)
        except OSError:
            sys.exit('Permission denied: {}'.format(args.folder))

    # downloading the ISOS
    download_isos(args.number, args.folder, args.verbose)


def arguments():
    """Define and handle arguments with options to run the script

    Return:
     - parser.parse_args(): list arguments as objects assigned as attributes
       of a namespace
    """

    description = 'Script used to run static analysis over python files'
    parser = argparse.ArgumentParser(description=description)
    # optional args
    parser.add_argument(
        '--verbose', dest='verbose', action='store_true',
        help='show the progress of the transfer')
    # groups args
    group = parser.add_argument_group(
        'mandatory arguments')
    group.add_argument('--number', dest='number', nargs='?', required=True,
                       help='the number of ISOS to be downloaded')
    group.add_argument('--folder', dest='folder', nargs='?', required=True,
                       help='the folder to storage the ISOS')

    return parser.parse_args()


if __name__ == '__main__':
    evaluate_args(arguments())
