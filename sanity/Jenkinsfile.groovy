pipeline {
	agent { label 'some agent' }

    // global variables
	environment {
        // general variables
        USER_HOST = 'jenkins'
        ISOS_FOLDER = "/home/${USER_HOST}/ISOS"
        GITHUB_STX_REPO = 'git@github.intel.com:Madawaska/stx-test-suite.git'
        REPO_FOLDER = "/home/${USER_HOST}/repositories"
        STX_REPO = "${REPO_FOLDER}/stx-test-suite"
        TMP_RESULTS = "/home/${USER_HOST}/tmp_results"
        ROBOT_RESULTS = "/home/${USER_HOST}/robot_results"
        JENKINS_ID = "${JOB_NAME}/${BUILD_NUMBER}"
        // testing images section
        IMAGES_FOLDER = "/home/${USER_HOST}/testing_images"
        CIRROS_IMG = 'cirros-0.4.0-x86_64-disk.img'
        CENTOS_IMG = 'CentOS-7-x86_64-Minimal-1804.img'
        UBUNTU_IMG = 'lubuntu-18.04-desktop-amd64.img'
        // virtual environment section
        VIRTUALENVWRAPPER = '/usr/local/bin/virtualenvwrapper.sh'
        VIRTUAL_ENV_NAME = 'jenkins-sanity'
    }
    // global options
    options {
        timeout(time: 70, unit: 'MINUTES')
        disableConcurrentBuilds()
        skipDefaultCheckout()
        timestamps()
    }

    stages{
        stage('create a new virtual environment'){
            steps{
                echo 'checking if the virtual environment exists'
                sh '''#!/bin/bash
                env_is_running=$(workon | grep ${VIRTUAL_ENV_NAME})
                if [[ ! -z ${env_is_running} ]]; then
                    rmvirtualenv ${VIRTUAL_ENV_NAME}
                fi
                '''
                echo 'creating a virtual environment'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                mkvirtualenv ${VIRTUAL_ENV_NAME}
                '''
            }
        }
        stage('cloning repositories'){
            steps{
                echo 'cloning repositories'
                sh '''#!/bin/bash
                sudo rm -rf ${REPO_FOLDER}
                mkdir -p ${REPO_FOLDER}
                git -C ${REPO_FOLDER} clone ${GITHUB_STX_REPO}
                '''
            }
        }
        stage('copying the isos'){
            steps{
                echo 'copying test images isos'
                sh '''#!/bin/bash
                image_list=(${CIRROS_IMG} ${CENTOS_IMG} ${UBUNTU_IMG})
                for image in ${image_list[@]};
                do
                    cp ${IMAGES_FOLDER}/${image} ${STX_REPO}
                done
                '''
                echo 'copying stx latest image'
                sh '''#!/bin/bash
                latest_iso=$(ls ${ISOS_FOLDER} | grep -E "^stx" | grep -E "\\.iso$" | grep -Eiv "**centos**" | sort -u | tail -1)
                cp ${ISOS_FOLDER}/${latest_iso} ${STX_REPO}/bootimage.iso
                '''
            }
        }
        stage('install suite requirements'){
            steps{
                echo 'install suite requirements'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                pip install -r ${STX_REPO}/requirements.txt
                pip install -r ${STX_REPO}/test-requirements.txt
                '''
            }
        }
        stage('execute suite setup'){
            steps{
                echo 'execute suite setup'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${STX_REPO}/runner.py --run-suite Setup
                '''
                echo 'moving the results'
                sh '''#!/bin/bash
                rm -rf ${TMP_RESULTS}
                mkdir -p ${TMP_RESULTS}
                cp ${STX_REPO}/latest-results/output.xml ${TMP_RESULTS}/setup_output.xml
                cp ${STX_REPO}/latest-results/report.html ${TMP_RESULTS}/setup_report.html
                cp ${STX_REPO}/latest-results/log.html ${TMP_RESULTS}/setup_log.html
                '''
            }
        }
        stage('execute suite sanity tests'){
            steps{
                echo 'execute suite sanity tests'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${STX_REPO}/runner.py --run-suite Sanity-Test
                '''
                echo 'moving the results'
                sh '''#!/bin/bash
                rm -rf ${TMP_RESULTS}
                mkdir -p ${TMP_RESULTS}
                cp ${STX_REPO}/latest-results/output.xml ${TMP_RESULTS}/sanity_output.xml
                cp ${STX_REPO}/latest-results/report.html ${TMP_RESULTS}/sanity_report.html
                cp ${STX_REPO}/latest-results/log.html ${TMP_RESULTS}/sanity_log.html
                '''
            }
        }
        stage('generate robot results'){
            steps{
                echo 'generate robot results'
                sh '''#!/bin/bash
                mkdir -p ${ROBOT_RESULTS}/${JENKINS_ID}
                cd ${TMP_RESULTS}
                rebot --outputdir ${ROBOT_RESULTS}/${JENKINS_ID} --output output setup_output.xml sanity_output.xml
                mv sanity_report.html sanity_log.html ${ROBOT_RESULTS}/${JENKINS_ID}
                '''
            }
        }
        stage('delete the virtual environment'){
            steps{
                echo 'creating a virtual environment'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                rmvirtualenv ${VIRTUAL_ENV_NAME}
                '''
            }
        }
    }
    post {
        // valid conditions are [always, changed, fixed, regression, aborted, success, unstable, failure, notBuilt, cleanup] 
        always {
            echo 'delete jenkins workspace'
            deleteDir()
        }
    }
}
