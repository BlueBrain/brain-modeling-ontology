# Brain Modeling Ontology

## CI/CD

`.gitlab-ci.yml` configures the continuous integration pipeline. 

### Pipeline stages

The pipeline consists of 3 stages:

1) `test` Runs unit tests on the ontologies files
2) `register` Registers the modified ontologies either on staging or production environments
3) `deploy` Deploys the documentation on production

### Triggers

#### On Merge Request

When a merge request receives a commit:

- Tests ontologies

#### On push/merge to develop

When `develop` branch receives a commit:

- Tests ontologies
- Register to nexus staging environment
- Deploy ontology documentation on staging environment

#### On tag

When `main` branch receives a tag:

- Tests ontologies
- Register to nexus production environment

### Variables

The Gitlab CI configuration requires the following variables to be set as [CI/CD variables](https://docs.gitlab.com/12.10/ee/ci/variables/#via-the-ui):

| Variable Name | Description | Masked  |
|:-------------:|-------------|:-----:|
| `CI_REGISTRY` | The registry of docs deployment. Should be set to `docker-registry-default.ocp.bbp.epfl.ch` | :heavy_multiplication_x: |
| `CI_REGISTRY_IMAGE` | The image stream of the docs. eg. `docker-registry-default.ocp.bbp.epfl.ch/bbp-dke-staging/bmo-docs` | :heavy_multiplication_x: |
| `CI_REGISTRY_USER` | The username of the account with permission to push an image to openshift project eg. `remote-pusher` | :white_check_mark: |
| `CI_REGISTRY_PASSWORD` | The password of the account with permission to push an image to openshift project | :white_check_mark: |
| `GITLAB_DEPLOY_TOKEN` | The deploy token of the custom Ontodocs repository. Dockerfile uses it to clone the private repository | :white_check_mark: |
| `GITLAB_DEPLOY_PASSWORD` | The deploy password of the custom Ontodocs repository. Dockerfile uses it to clone the private repository | :heavy_multiplication_x: |
| `NEXUS_TOKEN_STAGING` | The token of Nexus staging environment | :white_check_mark: |
| `NEXUS_TOKEN_PRODUCTION` | The token of Nexus production environment | :white_check_mark: |
