# jira-example
Examples of leveraging the Jira API via Python

## Authentication
The only way to authenticate against the API's these days is to pass in a user's email and API token via HTTP's basic auth. You can find documentation on creating a key for yourself [here](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/). 

## Setup
For this example I use [Pipenv](https://pipenv.pypa.io/en/latest/) to manage the installation of modules, keep a clean virtual environment, and load relevant env vars from a `.env` file.

1. Make sure you have python installed
2. Make sure you have pipenv installed `pip install pipenv`
3. Create a `.env` file and add appropriate variables
```
JIRA_HOST=my-jira-server.atlassian.net
JIRA_USER=my-jira-email-address@example.com
JIRA_TOKEN=my-jira-api-key
```
4. Either run files directly through `pipenv run python -i my_python_script.py` or start a pipenv shell with `pipenv shell` and run scripts in there

This repository contains simple examples of connecting to Jira in two ways...

## Using the Python SDK
This is the simpler method and an example of creating the connection is found in `jira_sdk_example.py`. The general pattern is to create a new `JIRA` object, passing in the URL and authentication for the instance. You can then call this objects functions to interact with Jira

Documentation for the SDK can be found [here](https://jira.readthedocs.io/en/latest/)

## Calling the API's Directly
This method is a bit more complex, but allows access to the full breadth of Jira's API's (supported and the unsupported ones that the web app uses). The best practice here is to create a wrapper class similar to the official SDK to handle authentication and the actual requests, and create functions related to specific calls. If you're going this route, you'll want to have Jira's [API docs](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/) handy. This is what I've done in `custom-jira.py`
