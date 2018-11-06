#!/usr/bin/env groovy

def email_from = 'some email'
def email_to = 'some email'

pipeline {

    agent none

    environment {
        // Global Variables
        HOME = '/home/testing'
        REPOSITORIES = "${HOME}/static_analysis/repositories"
        STX_REPO = "${REPOSITORIES}/stx-test-suite"
        PIPELINE_REPO = "${REPOSITORIES}/Jenkins-pipelines"
        SCRIPT = "${PIPELINE_REPO}/tools/static_analysis/python/run_analysis.py"
        VIRTUALENVWRAPPER = '/usr/local/bin/virtualenvwrapper.sh'
        VIRTUAL_ENV_NAME = 'static_analysis'
    }

    options {
        timeout(time: 10, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('preparing the jenkins workspace'){
            agent {
                node {
                    label 'some agent'
                    customWorkspace '/home/testing/jenkins'
                }
            }
            options {
                timeout(time: 2, unit: 'MINUTES')
                retry(2)
                timestamps()
            }
            steps{
                echo "Deleting ${REPOSITORIES} folder"
                sh "sudo rm -rf ${REPOSITORIES}"
                echo "Creating ${REPOSITORIES} folder"
                sh "mkdir -p ${REPOSITORIES}"
                echo 'downloading repositories'
                sh '''#!/bin/bash
                git -C ${REPOSITORIES} clone git@some_repo.git
                git -C ${REPOSITORIES} clone git@some_repo.git
                '''
            }
        }
        stage('preparing the virtual environment'){
            agent {
                node {
                    label 'some agent'
                    customWorkspace '/home/testing/jenkins'
                }
            }
            options {
                timeout(time: 1, unit: 'MINUTES')
                retry(2)
                timestamps()
            }
            steps{
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                mkvirtualenv ${VIRTUAL_ENV_NAME}'''
            }
        }
        stage('installing dependencies on virtual environment'){
            agent {
                node {
                    label 'some agent'
                    customWorkspace '/home/testing/jenkins'
                }
            }
            options {
                timeout(time: 5, unit: 'MINUTES')
                retry(2)
                timestamps()
            }
            steps{
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                pip install -r ${STX_REPO}/requirements.txt
                pip install -r ${STX_REPO}/test-requirements.txt'''
            }
        }
        stage('downloading the patch from Gerrit Code Review'){
            agent {
                node {
                    label 'some agent'
                    customWorkspace '/home/testing/jenkins'
                }
            }
            options {
                timeout(time: 1, unit: 'MINUTES')
                retry(2)
                timestamps()
            }
            steps{
                sh '''#!/bin/bash
                git -C ${STX_REPO} review -d ${GERRIT_CHANGE_NUMBER}
                git -C ${STX_REPO} checkout FETCH_HEAD'''
            }
        }
        stage('running static analysis'){
            agent {
                node {
                    label 'some agent'
                    customWorkspace '/home/testing/jenkins'
                }
            }
            options {
                timeout(time: 5, unit: 'MINUTES')
                retry(2)
                timestamps()
            }
            environment {
                VERDICT = '/tmp/VERDICT'
            }
            steps{
                // Getting the verdict of the python files (if any)
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                python ${SCRIPT} ${STX_REPO}
                python ${SCRIPT} ${STX_REPO}
                '''
                script{
                    VERDICT = readFile(VERDICT).trim()
                    echo "The VERDICT is: ${VERDICT}"
                    // possibles values pipeline are: (SUCCESS, UNSTABLE, or FAILURE)
                    if (VERDICT == "FAIL") {
                        echo "---------------------------------------------------------------------------------"
                        echo "The patch of [${GERRIT_CHANGE_OWNER_NAME}] does meet the minimum score for pylint"
                        echo "---------------------------------------------------------------------------------"
                        currentBuild.result = 'FAILURE'
                    }
                    if (VERDICT == "PASS") {
                        echo "----------------------------------------------------------------------------"
                        echo "The patch of [${GERRIT_CHANGE_OWNER_NAME}] meet the minimum score for pylint"
                        echo "----------------------------------------------------------------------------"
                        currentBuild.result = 'SUCCESS'
                    }
                    if (VERDICT == "NOT_RUN") {
                        echo "-----------------------------------------------------------------------------------"
                        echo "The patch of [${GERRIT_CHANGE_OWNER_NAME}] does not has python files to be analyzed"
                        echo "-----------------------------------------------------------------------------------"
                        currentBuild.result = 'SUCCESS'
                    }
                }
            }
        }
        stage('show static analysis results'){
            agent {
                node {
                    label 'some agent'
                    customWorkspace '/home/testing/jenkins'
                }
            }
            options {
                timeout(time: 1, unit: 'MINUTES')
                retry(2)
                timestamps()
            }
            steps{
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                workon ${VIRTUAL_ENV_NAME}
                echo "--------------------------------------------------------"
                python ${SCRIPT} ${STX_REPO} True
                echo "--------------------------------------------------------"
                '''
            }
        }
        stage('deleting the virtual environment'){
            agent {
                node {
                    label 'some agent'
                    customWorkspace '/home/testing/jenkins'
                }
            }
            options {
                timeout(time: 1, unit: 'MINUTES')
                retry(2)
                timestamps()
            }
            steps{
                sh '''#!/bin/bash
                source ${VIRTUALENVWRAPPER}
                rmvirtualenv ${VIRTUAL_ENV_NAME}'''
            }
        }
    }
    post {
        // valid conditions are [always, changed, fixed, regression, aborted, success, unstable, failure, notBuilt, cleanup]
        always {
            node('some agent'){
                // This will always run
                echo 'Deleting jenkins workspace'
                deleteDir()
            }
        }
    }
}
