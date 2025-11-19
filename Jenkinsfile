pipeline {
    agent any

    environment {
        // Update this to match your Docker Hub repo
        DOCKERHUB_REPO = "rikchowdhury22/pms-backend"
        CONTAINER_NAME = "pms-backend"

        // Port mapping: host:container
        APP_PORT_HOST  = "5000"
        APP_PORT_CONT  = "5000"
    }

    options {
        timestamps()
    }

    stages {

        stage('Checkout') {
            steps {
                git branch: 'main',
                    url: 'https://github.com/rikchowdhury22/HRMS_Project_Backend.git'
            }
        }

        stage('Build Docker image') {
            steps {
                script {
                    // Versioned tag per build + latest
                    def versionTag = "build-${env.BUILD_NUMBER}"
                    env.IMAGE_TAG = versionTag

                    sh '''
                    docker build \
                      -t ${DOCKERHUB_REPO}:${IMAGE_TAG} \
                      -t ${DOCKERHUB_REPO}:latest \
                      .
                    '''
                }
            }
        }

        stage('Push to Docker Hub') {
            steps {
                script {
                    withCredentials([usernamePassword(
                        credentialsId: 'PMS-Backend_Docker',   // check this ID matches in Jenkins
                        usernameVariable: 'DOCKERHUB_USER',
                        passwordVariable: 'DOCKERHUB_PASS'
                    )]) {
                        // use single quotes so $VAR is expanded by shell, not Groovy
                        sh '''
                        echo "$DOCKERHUB_PASS" | docker login -u "$DOCKERHUB_USER" --password-stdin
                        docker push ${DOCKERHUB_REPO}:${IMAGE_TAG}
                        docker push ${DOCKERHUB_REPO}:latest
                        docker logout
                        '''
                    }
                }
            }
        }

        stage('Deploy on VPS (same node)') {
            steps {
                script {
                    withCredentials([file(
                        credentialsId: 'PMS-Backend-env',     // Secret file ID in Jenkins
                        variable: 'BACKEND_ENV_FILE'          // env var holding file path
                    )]) {

                        // Stop & remove old container if it exists
                        sh """
                        if [ \$(docker ps -aq -f name=${CONTAINER_NAME}) ]; then
                            docker stop ${CONTAINER_NAME} || true
                            docker rm ${CONTAINER_NAME} || true
                        fi
                        """

                        // Run updated container using that secret file as env-file
                        sh """
                        docker run -d \\
                          --name ${CONTAINER_NAME} \\
                          --restart unless-stopped \\
                          --env-file "${BACKEND_ENV_FILE}" \\
                          -p ${APP_PORT_HOST}:${APP_PORT_CONT} \\
                          ${DOCKERHUB_REPO}:latest
                        """
                    }
                }
            }
        }
    }   // 🔴 this closes `stages { ... }` – you were missing this

    post {
        success {
            echo "✅ Deployment succeeded: ${CONTAINER_NAME} running ${DOCKERHUB_REPO}:${IMAGE_TAG}"
        }
        failure {
            echo "❌ Deployment failed. Check the stages above for detailed logs."
        }
    }
}
