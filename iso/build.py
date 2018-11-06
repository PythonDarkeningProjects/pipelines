"""The objective of this python module is to build a ISO for StarlingX
project"""

from __future__ import print_function

import argparse
import datetime
import getpass
import json
import os
import multiprocessing
from shutil import copyfile
from shutil import rmtree

import docker
import requests

from bash import bash
from git import Repo

# Global variables
CURRENT_USER = getpass.getuser()
BASE_PATH = '/var/opt'
REPOSITORIES = '{}/repositories'.format(BASE_PATH)
LOCAL_STX_TOOLS = '{}/stx-tools'.format(REPOSITORIES)
GITHUB_STX_TOOLS = 'https://git.starlingx.io/stx-tools'
ISO_FOLDER = '{}/html/ISO'.format(BASE_PATH)

# Environ variables
BRANCH = os.environ.get('BRANCH', 'master')
MYUNAME = os.environ.get('MYUNAME', CURRENT_USER)
PROJECT = os.environ.get('PROJECT', 'starlingx')
MIRROR_PATH = os.environ.get('MIRROR_PATH', '{}/mirror/latest'.format(
    BASE_PATH))
SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL', '#gerrit_code_review')
# SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL', '#building_running')

# Jenkins variables
BUILD_URL = os.environ.get('BUILD_URL', None)
BUILD_NUMBER = os.environ.get('BUILD_NUMBER', None)
BUILD_DISPLAY_NAME = os.environ.get('BUILD_DISPLAY_NAME', None)
JOB_NAME = os.environ.get('JOB_NAME', None)

# Docker Variables
TC_CONTAINER_NAME = '{}-centos-builder'.format(MYUNAME)
CLIENT = docker.from_env()


def remove_container():
    """Remove a docker container in the system

    This function will remove the docker container with the name of the global
    variable TC_CONTAINER_NAME declared in this module"""

    for _c in CLIENT.containers.list():
        _id = str(_c).split()[1].replace('>', '')
        container = CLIENT.containers.get(_id)
        if container.attrs['Name'] == '/{}'.format(TC_CONTAINER_NAME):
            print('removing docker container id: {}'.format(_id))
            container.remove(force=True)


def remove_image():
    """Remove a docker image in the system

    This function will remove the docker image create with this module"""

    image = 'local/{}-stx-builder:7.3'.format(CURRENT_USER)
    if CLIENT.images.list(name=image):
        print('removing docker image: {}'.format(image))
        CLIENT.images.remove(image=image, force=True)


def slack_bot(
        msg, _type='comment', priority='Normal', title='', title_link=''):
    """Send a message to slack channel

    :param msg: the message to send to the channel
    :param _type: the type of message to be displayed in slack, the possibles
                 values are:
                - good (green color)
                - warning (yellow color)
                - danger (red color)
                - comment (gray color)
    :param priority: possible values are: High, Normal, Low
    :param title: the title of the link to be displayed
    :param title_link: the link to be inserted, usually an url
    """

    color = ''

    if _type == 'good':
        color = '#36a64f'
    elif _type == 'warning':
        color = '#E7FF1A'
    elif _type == 'danger':
        color = '#FF3838'
    elif _type == 'comment':
        color = '#CDCDCD'

    webhook_url = ('https://hooks.slack.com/services/T9K08FHL4/BB4NZK5B2/'
                   'dXffQfcibJ8wcS8uJ1GkcLKp')
    slack_data = {'text': msg, 'channel': SLACK_CHANNEL}
    attachments = {
        "attachments": [
            {
                'color': color,
                'author_name': 'builder',
                'title': title,  # custom title
                'title_link': title_link,  # custom link
                'fields': [
                    {
                        'title': 'Priority',
                        'value': priority,
                        'short': False
                    }
                ],
                'footer': 'some footer',
                'footer_icon': 'https://platform.slack-edge.com/img/'
                               'default_application_icon.png',
            }
        ]
    }

    slack_data.update(attachments)
    response = requests.post(
        webhook_url, data=json.dumps(slack_data),
        headers={'Content-Type': 'application/json'}
    )

    if not response.ok:
        print('could not send the message to the channel: {}'.format(
            SLACK_CHANNEL))


def update_mirror():
    """Update local mirror

    This function update a local mirror in the server preventing the download
    from scratch and saving a lot of time
    """

    mirror_path = os.path.join(MIRROR_PATH, 'CentOS', 'pike')

    if not os.path.isdir(mirror_path):
        os.makedirs(mirror_path)

    tis_installer = '{}/CentOS/tis-installer'.format(MIRROR_PATH)
    if not os.path.isdir(tis_installer):
        os.makedirs(tis_installer)

    bash('rsync -e "ssh -i /home/{}/.ssh/id_rsa -o StrictHostKeyChecking=no '
         '-o UserKnownHostsFile=/dev/null" -avF '
         'user@host:/mirror/mirror/ {}'.format(
             CURRENT_USER, mirror_path))

    # copying mirror binaries
    base_path = '{}/CentOS/pike/Binary'.format(MIRROR_PATH)
    copyfile('{}/images/pxeboot/initrd.img'.format(base_path),
             '{}/initrd.img-stx-0.2'.format(tis_installer))
    copyfile('{}/images/pxeboot/vmlinuz'.format(base_path),
             '{}/vmlinuz-stx-0.2'.format(tis_installer))
    copyfile('{}/LiveOS/squashfs.img'.format(base_path),
             '{}/squashfs.img-stx-0.2'.format(tis_installer))


def common_setup():
    """Common setup

    All the steps here are pre requisites before to run some module for
    instance
    """

    if not os.path.isdir(REPOSITORIES):
        os.mkdir(REPOSITORIES)


def run_in_container(cmd):
    """Run inside the container a command

    :param cmd: the cmd that will be run inside the container

    :return
        - _c.stdout: which is the cmd's stdout
        - _c.stderr which is the cmd's stderr
    """
    _c = bash('docker exec --interactive --user={0} -e MYUNAME={0} {1} script '
              '-q -c "{2}" /dev/null'.format(
                  CURRENT_USER, TC_CONTAINER_NAME, cmd))

    return _c.stdout, _c.stderr


def create_localrc():
    """Creating localrc file into stx-tools repository"""

    print('creating localrc file')

    content = ('MYUNAME={}\n'
               'PROJECT={}\n'
               'HOST_PREFIX={}/work\n'
               'HOST_MIRROR_DIR={}\n')\
        .format(MYUNAME, PROJECT, LOCAL_STX_TOOLS, MIRROR_PATH)
    with open('{}/localrc'.format(LOCAL_STX_TOOLS), 'w') as localrc:
        localrc.writelines(content)

    print('creating .dockerignore file')
    with open('{}/.dockerignore'.format(LOCAL_STX_TOOLS), 'w') as dockerignore:
        dockerignore.write('work/*\n')

    print('copying .gitconfig file')
    copyfile(
        '{}/.gitconfig'.format(os.environ['HOME']),
        '{}/toCOPY/.gitconfig'.format(LOCAL_STX_TOOLS))


def conf_proxies(docker_file):
    """Configure proxies for dockers containers

    :param docker_file: the docker file to configure the proxies
    """

    if not os.path.isfile(docker_file):
        print('Docker file does not exists')
        return

    print('setting proxies for: {}'.format(os.path.basename(docker_file)))

    with open(docker_file, 'r') as _file:
        data = _file.readlines()

    cmd = "cat -n {} | grep -w FROM | awk '{{print $1}}'".format(docker_file)
    reference = bash(cmd).stdout.strip()
    _ln = int(reference) + 1

    # this lines will be insert in a reverse order
    data.insert(_ln, 'RUN echo \"proxy=<proxy>:port\" >> '
                     '/etc/yum.conf\n')
    data.insert(
        _ln, 'ENV no_proxy \"127.0.0.1\"\n')
    data.insert(_ln, 'ENV ftp_proxy \"ftp://<proxy>:<port>\"\n')
    data.insert(_ln, 'ENV https_proxy \"https://<proxy>:<port>\"\n')
    data.insert(_ln, 'ENV http_proxy \"http://<proxy>:<port>\"\n')

    with open(docker_file, 'w') as _file:
        _file.writelines(data)


def create_containers():
    """Create docker containers"""

    for docker_file in os.listdir('{}'.format(LOCAL_STX_TOOLS)):
        if docker_file.startswith('Dockerfile'):
            # configure proxies for each docker container
            conf_proxies('{}/{}'.format(LOCAL_STX_TOOLS, docker_file))

    print('make base-build')
    bash('make -C {} base-build'.format(LOCAL_STX_TOOLS))
    print('make build')
    bash('make -C {} build'.format(LOCAL_STX_TOOLS))


def clone_stx_tools():
    """clone stx-tools"""

    if os.path.isdir(LOCAL_STX_TOOLS):
        print('removing stx-tools repository')
        rmtree(LOCAL_STX_TOOLS)

    print('cloning stx-tools repository')
    os.makedirs(LOCAL_STX_TOOLS)
    Repo.clone_from(GITHUB_STX_TOOLS, LOCAL_STX_TOOLS, branch=BRANCH)


def setup_build_other_actions():
    """Setup build other actions

    All the others actions in order to setup build must be here
    """

    # launch the container
    bash('cd {} && bash tb.sh run'.format(LOCAL_STX_TOOLS))
    # copying file to container
    bash('docker cp {}/buildrc {}:/home/{}'.format(
        LOCAL_STX_TOOLS, TC_CONTAINER_NAME, CURRENT_USER))
    bash('docker cp {}/localrc {}:/home/{}'.format(
        LOCAL_STX_TOOLS, TC_CONTAINER_NAME, CURRENT_USER))

    # copy cgcs-tis-repo
    if os.path.isdir('/var/opt/cgcs-tis-repo'):
        bash('docker cp /var/opt/cgcs-tis-repo {}:/home/{}'.format(
            TC_CONTAINER_NAME, CURRENT_USER))

    system_cores = multiprocessing.cpu_count()
    clone_code = ('''
    source \$HOME/.bashrc

    # disable repo init colorization prompt
    git config --global color.ui false

    # cleaning old build code and artifacts
    if [[ -d /localdisk/loadbuild/{USER} ]]; then
        sudo rm -rf /localdisk/designer/\$MYUNAME/\$PROJECT/*
        sudo rm -rf /localdisk/designer/\$MYUNAME/\$PROJECT/.repo
        sudo rm -rf /localdisk/loadbuild/*
    fi

    cd \$MY_REPO_ROOT_DIR
    repo init -u https://git.starlingx.io/stx-manifest.git -m default.xml \
    -b {BRANCH}
    repo sync -j{CORES}

    # generate cgcs-centos-repo
    time generate-cgcs-centos-repo.sh /import/mirrors/CentOS/pike | tee \
    /localdisk/cgcs-centos-repo-output

    # symlink to downloads
    mkdir -p \$MY_REPO/stx
    if [[ ! -L \$MY_REPO/stx/downloads ]]; then
        ln -s /import/mirrors/CentOS/pike/downloads \$MY_REPO/stx/
    fi
    
    # copy cgcs-tis-repo
    mkdir -p \$MY_REPO/cgcs-tis-repo
    cp -r \$HOME/cgcs-tis-repo/* \$MY_REPO/cgcs-tis-repo/
    '''.format(USER=CURRENT_USER, BRANCH=BRANCH, CORES=system_cores))

    run_in_container(clone_code)


def check_mirror_packages():
    """Check if there is not error in cgcs-centos-repo-output file

    This function checks that the file cgcs-centos-repo-output must have not
    errors in order to build the srpms
    """
    with open('{}/work/localdisk/cgcs-centos-repo-output'.format(
            LOCAL_STX_TOOLS), 'r') as _f:
        lines = _f.readlines()

    missing_packages = []
    for line in lines:
        if line.startswith('Error'):
            missing_packages.append(line)

    if missing_packages:
        _file = '{}/work/localdisk/missing_packages'.format(LOCAL_STX_TOOLS)
        with open(_file, 'w') as _f:
            _f.writelines(missing_packages)
        print('(err) there is missing packages in the mirror')
        print('(info) check the file: {}'.format(_file))


def build_srpms():
    """Build srpms

    This function build the srpms in the container and sent a message to slack
    if the build were not successfully
    """

    cmd = ('''
    source \$HOME/.bashrc
    cd \$MY_REPO
    time build-srpms | tee /localdisk/build-srpms.log
    ''')

    run_in_container(cmd)

    path = '{}/work/localdisk/loadbuild/{}/{}/std/tmp'.format(
        LOCAL_STX_TOOLS, MYUNAME, PROJECT)

    if os.listdir(path):
        for _f in os.listdir(path):
            if os.stat(os.path.join(path, _f)).st_size > 0:
                slack_bot(
                    ':neutral_face: Build failed in stage `build-srpms` for '
                    'branch `{}`'.format(BRANCH), _type='danger',
                    title='Check the logs here', title_link=BUILD_URL
                )
                # fail the current pipeline step
                _file = '{}/work/localdisk/build_srpms_fail'.format(
                    LOCAL_STX_TOOLS)
                with open(_file, 'w') as f:
                    f.write('build_srpms_fail')
                return


def build_std():
    """Build std

    Note: this step takes a long time to be executed (3.5 to 4 HRS)
    """

    cmd = ('''
    source \$HOME/.bashrc
    cd \$MY_REPO
    time build-pkgs --std | tee /localdisk/build-pkgs_std.log
    ''')

    run_in_container(cmd)

    fail_files = bash(
        'find {}/work/localdisk/loadbuild/{}/{}/std/results -name fail'.format(
            LOCAL_STX_TOOLS, MYUNAME, PROJECT)).stdout

    if fail_files:
        slack_bot(
            ':neutral_face: Build failed in stage `build-pkgs` for '
            'branch `{}`'.format(BRANCH), _type='danger',
            title='Check the logs here', title_link=BUILD_URL
        )
        # fail the current pipeline step
        _file = '{}/work/localdisk/build_std_fail'.format(
            LOCAL_STX_TOOLS)
        with open(_file, 'w') as f:
            f.write('build_std_fail')


def build_rt():
    """Build rt

    Note: this step takes around 20 minutes to be executed
    """

    cmd = ('''
    source \$HOME/.bashrc
    cd \$MY_REPO
    time build-pkgs --rt | tee /localdisk/build-pkgs_rt.log
    ''')

    run_in_container(cmd)

    fail_files = bash(
        'find {}/work/localdisk/loadbuild/{}/{}/rt/results -name fail'.format(
            LOCAL_STX_TOOLS, MYUNAME, PROJECT)).stdout

    if fail_files:
        slack_bot(
            ':neutral_face: Build failed in stage `build-pkgs --rt` for '
            'branch `{}`'.format(BRANCH), _type='danger',
            title='Check the logs here', title_link=BUILD_URL
        )
        # fail the current pipeline step
        _file = '{}/work/localdisk/build_rt_fail'.format(
            LOCAL_STX_TOOLS)
        with open(_file, 'w') as f:
            f.write('build_rt_fail')


def build_installer():
    """Build installer

    Note: this step takes around 5 minutes to be executed.
    """

    cmd = ('''
    source \$HOME/.bashrc
    cd \$MY_REPO
    time build-pkgs --installer | tee /localdisk/build-pkgs_installer.log
    ''')

    run_in_container(cmd)

    fail_files = bash(
        'find {}/work/localdisk/loadbuild/{}/{}/installer/results -name '
        'fail'.format(LOCAL_STX_TOOLS, MYUNAME, PROJECT)).stdout

    if fail_files:
        slack_bot(
            ':neutral_face: Build failed in stage `build-pkgs --installer` '
            'for branch `{}`'.format(BRANCH), _type='danger',
            title='Check the logs here', title_link=BUILD_URL
        )
        # fail the current pipeline step
        _file = '{}/work/localdisk/build_installer_fail'.format(
            LOCAL_STX_TOOLS)
        with open(_file, 'w') as f:
            f.write('build_installer_fail')


def build_iso():
    """Build ISO

    Note: this step takes around 5 minutes to be executed.
    Warning: PLEASE DO NOT USE 'jenkins' as a system user due the following
    know issue:

    file: sign-rpms:282 #sign_packages_on_server
    path: /localdisk/designer/jenkins/starlingx/cgcs-root/build-tools

    when jenkins user is in use the above script will try to sign the packages
    in a unknown server.
    """

    cmd = ('''
    source \$HOME/.bashrc
    cd \$MY_REPO
    time build-iso | tee /localdisk/build-iso.log
    ''')

    run_in_container(cmd)

    iso_file = '{}/work/localdisk/loadbuild/{}/{}/export/bootimage.iso'.format(
        LOCAL_STX_TOOLS, MYUNAME, PROJECT)

    if not os.path.isfile(iso_file):
        slack_bot(
            ':neutral_face: Build failed in stage `build-iso` for branch '
            '`{}`'.format(BRANCH), _type='danger',
            title='Check the logs here', title_link=BUILD_URL
        )
        # fail the current pipeline step
        _file = '{}/work/localdisk/build_iso_fail'.format(
            LOCAL_STX_TOOLS)
        with open(_file, 'w') as f:
            f.write('build_iso_fail')
    else:
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        s_branch = BRANCH.replace('/', '-')
        iso_name = 'stx-{}-{}-{}.iso'.format(date, BUILD_NUMBER, s_branch)

        if not os.path.exists(ISO_FOLDER):
            os.makedirs(ISO_FOLDER)

        copyfile(iso_file, '{}/{}'.format(ISO_FOLDER, iso_name))
        slack_bot(
            ':smiley: Successful build for branch `{}`'.format(BRANCH),
            _type='good', title='Get the new ISO here',
            title_link='{}/{}'.format(ISO_URL, iso_name)
        )


def build_init_files():
    """Build init files

    Note: this step takes around 5 minutes to be executed.
    """

    cmd = ('''
    source \$HOME/.bashrc
    cd \$MY_REPO
    time update-pxe-network-installer | tee /localdisk/build_init_files.log
    ''')

    run_in_container(cmd)

    # check if the init files were correctly generated
    init_files = ['new-initrd.img', 'new-squashfs.img', 'new-vmlinuz']
    path = ('{}/work/localdisk/loadbuild/{}/{}/pxe-network-installer/output'
            .format(LOCAL_STX_TOOLS, MYUNAME, PROJECT))

    for _file in init_files:
        init_file = os.path.join(path, _file)
        if not os.path.isfile(init_file):
            print('missing: {}'.format(init_file))
            # fail the current pipeline step
            _file = '{}/work/localdisk/build_init_files'.format(
                LOCAL_STX_TOOLS)
            with open(_file, 'w') as f:
                f.write('build_init_files')


def cgcs_tis_repo():
    """Copy the cgcs-tis-repo folder

    This step is optional but will improve performance on subsequent builds.
    The cgcs-tis-repo has the dependency information that sequences the build
    order
    """

    _cgcs_tis_repo = (
        '{}/work/localdisk/designer/{}/{}/cgcs-root/cgcs-tis-repo'.format(
            LOCAL_STX_TOOLS, MYUNAME, PROJECT))
    if os.path.isdir(_cgcs_tis_repo):
        print('copying cgcs-tis-repo to: {}'.format(BASE_PATH))
        bash('cp -r {} {}'.format(cgcs_tis_repo, BASE_PATH))


def get_args():
    """Define and handle arguments with options to run the script

    Return:
        - parser.parse_args(): list arguments as objects assigned as
          attributes of a namespace
    """

    description = 'Script used to build starlingx ISO'
    parser = argparse.ArgumentParser(description=description)
    # groups args
    group1 = parser.add_argument_group('Clean docker environment')
    group1.add_argument('--action', dest='action', choices=[
        'remove_container', 'remove_image'])
    group2 = parser.add_argument_group('Execution Steps')
    group2.add_argument(
        '--setup_build', dest='setup_build', choices=[
            'update_mirror',
            'common_setup',
            'clone_stx_tools',
            'create_localrc',
            'create_containers',
            'other_actions',
            'check_mirror_packages'], help='the execution step to be run')
    group2.add_argument('--build_srpms', dest='build_srpms',
                        action='store_true')
    group2.add_argument('--build_std', dest='build_std', action='store_true')
    group2.add_argument('--build_rt', dest='build_rt', action='store_true')
    group2.add_argument('--build_installer', dest='build_installer',
                        action='store_true')
    group2.add_argument('--build_iso', dest='build_iso', action='store_true')
    group2.add_argument('--build_init_files', dest='build_init_files',
                        action='store_true')
    group2.add_argument('--cgcs_tis_repo', dest='cgcs_tis_repo',
                        action='store_true')

    return parser.parse_args()


if __name__ == '__main__':
    ARGS = get_args()

    # clean docker environment
    if ARGS.action == 'remove_container':
        remove_container()
    elif ARGS.action == 'remove_image':
        remove_image()

    # setup build steps
    if ARGS.setup_build == 'update_mirror':
        update_mirror()
    elif ARGS.setup_build == 'common_setup':
        common_setup()
    elif ARGS.setup_build == 'clone_stx_tools':
        clone_stx_tools()
    elif ARGS.setup_build == 'create_localrc':
        create_localrc()
    elif ARGS.setup_build == 'create_containers':
        create_containers()
    elif ARGS.setup_build == 'other_actions':
        setup_build_other_actions()
    elif ARGS.setup_build == 'check_mirror_packages':
        check_mirror_packages()

    # build srpms
    if ARGS.build_srpms:
        build_srpms()
    # build std
    if ARGS.build_std:
        build_std()
    # build rt
    if ARGS.build_std:
        build_rt()
    # build installer
    if ARGS.build_installer:
        build_installer()
    # build iso
    if ARGS.build_iso:
        build_iso()
    # build init files
    if ARGS.build_init_files:
        build_init_files()
    # cgcs-tis-repo
    if ARGS.cgcs_tis_repo:
        cgcs_tis_repo()
