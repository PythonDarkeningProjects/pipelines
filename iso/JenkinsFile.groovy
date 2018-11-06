def email_list = "humberto.i.perez.rodriguez@intel.com"

pipeline {
    agent { label 'starlingxnewton' }

    // global variables
    environment {
        BASE_PATH = '/var/opt'
        LOCAL_REPOSITORIES = "${BASE_PATH}/repositories"
        GITHUB_REPO = sh(returnStdout: true, script: 'basename ${GITHUB_REPOSITORY} .git').trim()
        PYTHON_SCRIPT = "${LOCAL_REPOSITORIES}/${GITHUB_REPO}/starlingx-steps-build.py"
        // virtual environment section
        VIRTUALENVWRAPPER = '/usr/local/bin/virtualenvwrapper.sh'
        VIRTUAL_ENV_NAME = 'jenkins-build-iso'
        // files to fail the pipeline (if any of they exists)
        MISSING_PACKAGES_FILE = "${LOCAL_REPOSITORIES}/stx-tools/work/localdisk/missing_packages"
        BUILD_SRPMS_FILE = "${LOCAL_REPOSITORIES}/stx-tools/work/localdisk/build_srpms_fail"
        BUILD_STD_FILE = "${LOCAL_REPOSITORIES}/stx-tools/work/localdisk/build_std_fail"
        BUILD_RT_FILE = "${LOCAL_REPOSITORIES}/stx-tools/work/localdisk/build_rt_fail"
        BUILD_INSTALLER_FILE = "${LOCAL_REPOSITORIES}/stx-tools/work/localdisk/build_installer_fail"
        BUILD_ISO_FILE = "${LOCAL_REPOSITORIES}/stx-tools/work/localdisk/build_iso_fail"
        BUILD_INIT_FILES = "${LOCAL_REPOSITORIES}/stx-tools/work/localdisk/build_init_files"
        // Jenlkins jobs
        MANIFEST_JOB = 'create_manifests'
        CVE_JOB = 'cve_test'
    }

    // global options
    options {
        timeout(time: 300, unit: 'MINUTES')
        disableConcurrentBuilds()
        skipDefaultCheckout()
        timestamps()
    }

    stages{
        stage('create a new virtual environment'){
            steps{
                echo 'checking if the virtual environment exists'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
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
        stage('download repositories'){
            options {
                retry(2)
            }
            steps{
                sh '''/bin/bash
                sudo rm -rf ${LOCAL_REPOSITORIES}
                mkdir -p ${LOCAL_REPOSITORIES}
                git -C ${LOCAL_REPOSITORIES} clone ${GITHUB_REPOSITORY}
                '''
            }
        }
        stage('install suite requirements'){
            steps{
                echo 'install suite requirements'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                pip install -r ${LOCAL_REPOSITORIES}/$(basename ${GITHUB_REPOSITORY} .git)/requirements.txt
                '''
            }
        }
        stage('clean docker environment'){
            steps{
                echo 'remove docker containers'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --action remove_container
                '''
                echo 'remove docker images'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --action remove_image
                '''
            }
        }
        stage('setup build'){
            steps{
                echo 'update_mirror'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --setup_build update_mirror
                '''
                echo 'common_setup'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --setup_build common_setup
                '''
                echo 'clone_stx_tools'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                export BRANCH=${BRANCH}
                python ${PYTHON_SCRIPT} --setup_build clone_stx_tools
                '''
                echo 'create_localrc'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --setup_build create_localrc
                '''
                echo 'create_containers'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --setup_build create_containers
                '''
                echo 'other_actions'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                export BRANCH=${BRANCH}
                python ${PYTHON_SCRIPT} --setup_build other_actions
                '''
                //script {
                    // TODO: uncomment this path when the job is stable
                    //echo "call Jenkins job to generate manifests"
                    //build job: MANIFEST_JOB, parameters: [[$class: 'StringParameterValue', name: 'FROM_JOB', value: JOB_NAME]], wait: false
                //}
                echo 'check_mirror_packages'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --setup_build check_mirror_packages
                '''
                script{
                    // possibles values pipeline are: (SUCCESS, UNSTABLE, or FAILURE)
                    if (fileExists(MISSING_PACKAGES_FILE)) {
                        echo "(info) check the file: ${MISSING_PACKAGES_FILE}"
                        currentBuild.result = 'FAILURE'
                        error "there is some missing packages in the mirror"
                    }
                }
            }
        }
        stage('build srpms'){
            steps{
                echo 'build_srpms'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --build_srpms
                '''
                script{
                    // possibles values pipeline are: (SUCCESS, UNSTABLE, or FAILURE)
                    if (fileExists(BUILD_SRPMS_FILE)) {
                        echo "(info) check the files into: ${LOCAL_REPOSITORIES}/stx-tools/work/localdisk/loadbuild/${USER}/${PROJECT}/std/tmp"
                        currentBuild.result = 'FAILURE'
                        error "build_srpms fail"
                    } else {
                        echo "TODO: uncomment this path when the job is stable"
                        //echo "call Jenkins job to generate CVE report"
                        //build job: CVE_JOB, parameters: [[$class: 'StringParameterValue', name: 'FROM_JOB', value: JOB_NAME]], wait: false
                    }
                }
            }
        }
        stage('build std'){
            steps{
                echo 'build_std'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --build_std
                '''
                script{
                    // possibles values pipeline are: (SUCCESS, UNSTABLE, or FAILURE)
                    if (fileExists(BUILD_STD_FILE)) {
                        currentBuild.result = 'FAILURE'
                        error "build_std fail"
                    }
                }
            }
        }
        stage('build rt'){
            steps{
                echo 'build_rt'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --build_rt
                '''
                script{
                    // possibles values pipeline are: (SUCCESS, UNSTABLE, or FAILURE)
                    if (fileExists(BUILD_RT_FILE)) {
                        currentBuild.result = 'FAILURE'
                        error "build_rt fail"
                    }
                }
            }
        }
        stage('build installer'){
            steps{
                echo 'build_installer'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --build_installer
                '''
                script{
                    // possibles values pipeline are: (SUCCESS, UNSTABLE, or FAILURE)
                    if (fileExists(BUILD_INSTALLER_FILE)) {
                        currentBuild.result = 'FAILURE'
                        error "build_installer fail"
                    }
                }
            }
        }
        stage('build iso'){
            steps{
                echo 'build_iso'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --build_iso
                '''
                script{
                    // possibles values pipeline are: (SUCCESS, UNSTABLE, or FAILURE)
                    if (fileExists(BUILD_ISO_FILE)) {
                        currentBuild.result = 'FAILURE'
                        error "build_iso fail"
                    }
                }
            }
        }
        stage('build init files'){
            steps{
                echo 'build_init_files'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --build_init_files
                '''
                script{
                    // possibles values pipeline are: (SUCCESS, UNSTABLE, or FAILURE)
                    if (fileExists(BUILD_INIT_FILES)) {
                        currentBuild.result = 'FAILURE'
                        error "build_init_files fail"
                    }
                }
            }
        }
        stage('cgcs-tis-repo'){
            steps{
                echo 'cgcs_tis_repo'
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${PYTHON_SCRIPT} --cgcs_tis_repo
                '''
            }
        }
        stage('delete the virtual environment'){
            steps{
                echo 'delete the virtual environment'
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
            echo 'deleting jenkins workspace'
            deleteDir()
        }
        success {
            mail to: "${email_list}",
            subject: "Jenkins build: ${JOB_NAME} #${BUILD_NUMBER} success",
            body: "Build success for: ${JOB_NAME} #${BUILD_NUMBER}\n Build URL: ${BUILD_URL}\nThis is an automated message. Please do not reply"
        }
        failure {
            mail to: "${email_list}",
            subject: "Jenkins build: ${JOB_NAME} #${BUILD_NUMBER} failure",
            body: "Build failure for: ${JOB_NAME} #${BUILD_NUMBER}\n Build URL: ${BUILD_URL}\nThis is an automated message. Please do not reply"
        }
    }
}