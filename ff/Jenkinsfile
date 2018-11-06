#!/usr/bin/env groovy

def email_list = "some email"

pipeline {

    agent { label 'some agent' }

    // The timeout is calculated using the worst case scenario for test execution.
    // Assuming a platform is busy so the pipeline has to retry 5 times before being able
    // to run the tests. Then considering the max time it would take a platform to run fast-feedback
    // timeout = (5 times X 30 minutes) + 3 hours = 5.5 hours -> 6 hours
    options {
        timeout(time: 6, unit: 'HOURS')
        disableConcurrentBuilds()
    }

    environment {
        home = '/home/shared/suites'
        ff_home = "${home}/dev/igt/suites/fastfeedback"
    }

    stages {
        stage('IGT-Fastfeedback') {
            steps {
                echo 'Updating the repo with the latest commits'
                sh """
                rm -rf ${home}/dev
                git clone https://github.com/linuxgraphics/gfx-qa-tools.git ${home}/dev
                """
                echo "Updating the whitelist.yml file with the necessary platforms"
                sh "cp ${home}/whitelist.yml ${ff_home}/whitelist.yml"
                echo "Launching intel-gpu-tools fastfeedback in the selected platforms"
                sh """
                cd ${ff_home}
                PYTHONPATH=/home/shared/gitlist/gfx-qa-tools python fastfeedback__orchestrator.py -f \${FIRMWARE^} -s \${STACK^} -k \${KERNEL^} -d \${DRY_RUN^} -g False | tee ${home}/fastfeedback.log
                """
                // Retry up to 5 times the test execution on those platforms
                // that were unavailable
                script {
                    int retry = 0
                    int max_retry = 5
                    while (fileExists("${ff_home}/platforms_not_launched.yml") && (retry < max_retry)) {
                        retry+=1
                        sleep time: 30, unit: 'MINUTES'
                        sh """
                        cd ${ff_home}
                        PYTHONPATH=/home/shared/gitlist/gfx-qa-tools python fastfeedback__orchestrator.py -f \${FIRMWARE^} -s False -k False -d \${DRY_RUN^} -g True | tee -a ${home}/fastfeedback.log
                        """
                    }
                    // If after all re-trying there are still platforms in the platforms_not_launched.yml
                    // mark the build as Aborted and finish the pipeline.
                    if (fileExists("${ff_home}/platforms_not_launched.yml")) {
                        def data = readYaml file: "${ff_home}/platforms_not_launched.yml"
                        currentBuild.result = 'ABORTED'
                        error("Failed to run IGT Fastfeeback in the following platforms: ${data}")
                    }
                }
            }
        }

    }

    post {

        always {
            // This will always run
            echo 'Deleting the Jenkins workspace'
            deleteDir()
        }
        success {
            // This will run only if successful
            mail to: "${email_list}",
             subject: "Successful Pipeline: ${currentBuild.fullDisplayName}",
             body: "The IGT Fastfeedback ${env.BUILD_URL} was executed successfully"
        }
        failure {
            // This will run only if failed
            mail to: "${email_list}",
             subject: "Failed Pipeline: ${currentBuild.fullDisplayName}",
             body: "Something went wrong with the IGT Fastfeedback execution ${env.BUILD_URL}"
        }

    }

}
