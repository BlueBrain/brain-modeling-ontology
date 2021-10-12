
CI/CD
=====

`.gitlab-ci.yml` configures the continuous integration pipeline.

Pipeline stages
---------------

The pipeline consists of 3 stages:

1) `test` Runs unit tests on the ontologies files
2) `register` Registers the modified ontologies either on staging or production environments
3) `generate` Generates the documentations
4) `deploy` Deploys the documentations on Openshift

Triggers
--------

On Merge Request
^^^^^^^^^^^^^^^^

When a merge request receives a commit:

- Tests ontologies

On push/merge to develop
^^^^^^^^^^^^^^^^^^^^^^^^

When `develop` branch receives a commit:

- Tests ontologies
- Register to nexus staging environment
- Generate and deploy ontology documentation on Openshift staging environment

On tag
^^^^^^

When `main` branch receives a tag:

- Tests ontologies
- Register to nexus production environment
- Generate and deploy ontology documentation on Openshift production environment

Variables
---------

The Gitlab CI configuration requires the following variables to be set as [CI/CD variables](https://docs.gitlab.com/12.10/ee/ci/variables/#via-the-ui):

+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
| Variable Name            | Description                                                                                               | Masked                   |
+==========================+===========================================================================================================+==========================+
| `CI_REGISTRY`                    | The registry of docs deployment. Should be set to `docker-registry-default.ocp.bbp.epfl.ch`                          | Yes   |
+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
| `CI_REGISTRY_USER_STAGING`       | The username of the account with permission to push an image to the staging openshift project eg. `remote-pusher`    | Yes   |
+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
| `CI_REGISTRY_USER_PRODUCTION`    | The username of the account with permission to push an image to the production openshift project eg. `remote-pusher` | Yes   |
+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
| `CI_REGISTRY_PASSWORD_STAGING`   | The password of the account with permission to push an image to the staging openshift project                        | Yes   |
+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
| `CI_REGISTRY_PASSWORD_PRODUCTION`| The password of the account with permission to push an image to the production openshift project                     | Yes   |
+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
| `GITLAB_DEPLOY_TOKEN`            | The deploy token of the custom Ontodocs repository. Dockerfile uses it to clone the private repository               | Yes   |
+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
| `GITLAB_DEPLOY_PASSWORD`         | The deploy password of the custom Ontodocs repository. Dockerfile uses it to clone the private repository            | Yes   |
+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
| `NEXUS_TOKEN_STAGING`            | The token of Nexus staging environment                                                                               | Yes   |
+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
| `NEXUS_TOKEN_PRODUCTION`         | The token of Nexus production environment                                                                            | Yes   |
+--------------------------+-----------------------------------------------------------------------------------------------------------+--------------------------+
