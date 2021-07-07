from jira import JIRA
import os

if __name__ == '__main__':
    jira_host = os.environ["JIRA_HOST"]
    jira_user = os.environ["JIRA_USER"]
    jira_token = os.environ["JIRA_TOKEN"]
    jira = JIRA(f"https://{jira_host}", basic_auth=(jira_user, jira_token))


    # Simple 'get jira issue' example
    # issue = jira.issue('ABC-1234')
    # print(issue)
