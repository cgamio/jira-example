from requests.auth import HTTPBasicAuth
import requests
import logging
import re
import json
import os
from datetime import datetime

class Jira:
    __auth = None
    __token = None
    __url = None
    __greenhopper_url = None
    __agile_url = None
    __prefix = ''

    __regex = {}
    __descriptions = {}

    def __makeRequest(self, verb, url, params=None):
        """Wrapper for a simple HTTP request

            Args:
                verb: string - HTTP verb as string (ie. 'GET' or 'POST')
                url: string - URL to make HTTP requests against
                params: dictionary - Any request parameters to pass along (defaults to None)

            Returns:
                dictionary - A JSON represenatation of the response text, or False in the case of an error
        """
        response = requests.request(verb, url, headers={ 'Accept': 'application/json' }, auth=self.__auth, params=params)
        if response.status_code == 200:
            return(json.loads(response.text))
        else:
            logging.error(response.text)
            return(False)

    def __init__(self, host, user, token, prefix=False):
        self.__host = host
        self.__auth = HTTPBasicAuth(user, token)
        self.__prefix = f'{prefix} ' if prefix else ''

        self.__url = f"https://{self.__host}/rest/api/latest/"
        self.__agile_url = f"https://{self.__host}/rest/agile/latest/"
        self.__greenhopper_url = f"https://{self.__host}/rest/greenhopper/latest/"

    def testConnection(self):
        """Tests the connection to Jira by getting user data"""
        url = f"{self.__url}/myself"

        response = self.__makeRequest('GET', url)

        return response

    def calculateSprintMetrics(self, sprint_report):
        """Given the data from a Jira sprint report, calculates sprint metrics

        Args:
            sprint_report: dictionary - the data from a Jira sprint reports

        Returns:
            dictionary - calculated metrics
        """
        points = {
            "committed": 0,
            "completed": 0,
            "planned_completed": 0,
            "unplanned_completed": 0,
            "feature_completed": 0,
            "optimization_completed": 0,
            "not_completed": 0,
            "removed": 0
        }

        items = {
            "committed": 0,
            "completed": 0,
            "planned_completed": 0,
            "unplanned_completed": 0,
            "stories_completed": 0,
            "unplanned_stories_completed": 0,
            "bugs_completed": 0,
            "unplanned_bugs_completed": 0,
            "not_completed": 0,
            "removed": 0
        }

        issue_keys = {
            "committed": [],
            "completed": [],
            "incomplete": [],
            "removed": []
        }

        feature_work = ["Story", "Design", "Spike"]
        optimization = ["Optimization"]
        bug = ["Bug"]
        ignore = ["Task", "Epic"]

        # Completed Work
        for completed in sprint_report["contents"]["completedIssues"]:
            issue_keys["completed"].append(completed["key"])

            # Short-circuit for things we don't track
            if completed["typeName"] in ignore:
                continue

            try:
                issue_points_original = int(completed["estimateStatistic"]["statFieldValue"]["value"])
            except:
                issue_points_original = 0

            try:
                issue_points = int(completed["currentEstimateStatistic"]["statFieldValue"]["value"])
            except:
                issue_points = 0

            points["completed"] += issue_points
            items["completed"] += 1

            unplanned = False
            if completed["key"] in sprint_report["contents"]["issueKeysAddedDuringSprint"].keys():
                unplanned = True
                points["unplanned_completed"] += issue_points
                items["unplanned_completed"] += 1
            else:
                issue_keys["committed"].append(completed["key"])
                points["committed"] += issue_points_original
                items["committed"] += 1
                points["planned_completed"] += issue_points
                items["planned_completed"] += 1
                if issue_points_original < issue_points:
                    points["unplanned_completed"] += issue_points-issue_points_original

            # Story
            if completed["typeName"] == "Story":
                items["stories_completed"] += 1
                if unplanned:
                    items["unplanned_stories_completed"] += 1

            # Story / Design / Spike (Feature Work)
            if completed["typeName"] in feature_work:
                points["feature_completed"] += issue_points

            # Optimization
            if completed["typeName"] in optimization:
                points["optimization_completed"] += issue_points

            # Bugs
            if completed["typeName"] in bug:
                items["bugs_completed"] += 1
                if unplanned:
                    items["unplanned_bugs_completed"] += 1


        # Incomplete Work
        for incomplete in sprint_report["contents"]["issuesNotCompletedInCurrentSprint"]:

            issue_keys["incomplete"].append(incomplete["key"])

            # Short-circuit for things we don't track
            if incomplete["typeName"] in ignore:
                continue

            try:
                issue_points = int(incomplete["currentEstimateStatistic"]["statFieldValue"]["value"])
            except:
                issue_points = 0

            points["not_completed"] += issue_points
            items["not_completed"] += 1

            if incomplete["key"] not in sprint_report["contents"]["issueKeysAddedDuringSprint"].keys():
                issue_keys["committed"].append(incomplete["key"])
                points["committed"] += issue_points
                items["committed"] += 1

        # Removed Work
        for removed in sprint_report["contents"]["puntedIssues"]:

            issue_keys["removed"].append(removed["key"])

            # Short-circuit for things we don't track
            if removed["typeName"] in ignore:
                continue

            try:
                issue_points = int(removed["currentEstimateStatistic"]["statFieldValue"]["value"])
            except:
                issue_points = 0

            if removed["key"] not in sprint_report["contents"]["issueKeysAddedDuringSprint"].keys():
                points["committed"] += issue_points
                items["committed"] += 1
                issue_keys["committed"].append(removed["key"])

            points["removed"] += issue_points
            items["removed"] += 1

        meta = {
            "predictability": 0,
            "predictability_of_commitments": 0
        }

        if points['committed'] != 0:
            meta['predictability'] = int(points['completed']/points['committed']*100)
            meta['predictability_of_commitments'] = int(points['planned_completed']/points['committed']*100)
        else:
            # If a sprint has no points committed, we say the predictability is 0
            logging.warning('This sprint had no commitments, predictability is 0')

        return {
            "points" : points,
            "items" : items,
            "issue_keys": issue_keys,
            "meta": meta
        }

    def getSprint(self, sprint_id):
        """Utility funtion to get sprint data from Jira

        Args:
            sprint_id: string - the id of a Jira sprint

        Returns:
            dictionary - A JSON encoded represenatation of the Jira sprint object
        """
        # Get Jira Sprint Object (including Board reference) from Sprint ID
        sprint = self.__makeRequest('GET', f"{self.__agile_url}sprint/{sprint_id}")
        if not sprint:
            raise Error(f"I could not find sprint with id {sprint_id}. Please check your arguments again. Are you using the right command for your jira instance? Ask me for `help` for more information")

        return sprint

    def getBoard(self, board_id):
        """Utility funtion to get board data from Jira

        Args:
            board_id: string - the id of a Jira board

        Returns:
            dictionary - A JSON encoded represenatation of Jira board object
        """
        board = self.__makeRequest('GET', f"{self.__agile_url}board/{board_id}")
        if not board:
            raise Error(f"Could not find boad with id {board_id}. Please check your arguments again. Are you using the right command for your jira instance? Ask me for `help` for more information")

        return board

    def getSprintReport(self, sprint_id, board_id):
        """Utility funtion to get sprint report data from Jira

        Args:
            sprint_id: string - the id of a Jira sprint
            board_id: string - the id of a Jira board

        Returns:
            dictionary - A JSON encoded represenatation of a Jira Sprint Report for the given sprint and board
        """
        sprint_report = self.__makeRequest('GET',f"{self.__greenhopper_url}rapid/charts/sprintreport?rapidViewId={board_id}&sprintId={sprint_id}")
        if not sprint_report:
            raise Error(f"Could not find report for sprint {sprint_id} on board {board_id}. Please check your arguments again. Are you using the right command for your jira instance? Ask me for `help` for more information")

        return sprint_report

    def getSprintMetricsCommand(self, message):
        """User-friendly wrapper for getting the metrics for a given sprint

        Args:
            message: string - the message from the user that initiated this command

        Returns:
            dictionary - A slack message response
        """
        try:
            sprintid = re.search('sprint metrics ([0-9]+)', message).group(1)
        except :
            logging.error(f"Did not find a sprint number in: '{message}'")
            return {'text': "Sorry, I don't see a valid sprint number there"}

        sprint = self.getSprint(sprintid)
        sprint_report = self.getSprintReport(sprintid, sprint['originBoardId'])
        metrics = self.calculateSprintMetrics(sprint_report)

        metrics_text = json.dumps(metrics, sort_keys=True, indent=4, separators=(",", ": "))

        return {'text': f"```{metrics_text}```"}

    def getJiraSprintReportData(self, sprint_report):
        """Utility funtion to parse general sprint information from a Jira sprint report

        Args:
            sprint_report: string - raw data from a Jira Sprint Report

        Returns:
            dictionary - relevant information parsed from the report
        """
        report = {}

        try:
            report['sprint_number'] = re.search(r'(?i)(S|Sprint )(?P<number>\d+)', sprint_report["sprint"]["name"]).group('number')
        except AttributeError:
            raise Error(f"I couldn't not find or parse sprint number from: '{sprint_report['sprint']['name']}'. Please make sure that you name sprints to include `S#` or `Sprint #`, where `#` is the number of the sprint")

        try:
            report['sprint_start'] = sprint_report['sprint']['startDate']
            report['sprint_end'] = sprint_report['sprint']['endDate']
        except KeyError:
            # Every sprint doesn't have a start / end date
            logging.warning('This sprint does not have start and/or end dates')

        try:
            report['sprint_goals'] = sprint_report['sprint']['goal'].split("\n")
        except (AttributeError, KeyError):
            raise Error(f"I couldn't find or parse sprint goal for one of your sprints. Please check your arguments again, but this might not be your fault so I've let my overlords know. Are you using the right command for your jira instance? Ask me for `help` for more information", f"Unable to find or parse sprint goal\n {sprint_report}")

        return report

    def generateAllSprintReportData(self, sprint_id):
        """Congomerates all the data from different Jira reports into one holistic Sprint Report data-set

        Args:
            sprint_id: string - the id of a Jira sprint

        Returns:
            dictionary - the information necessary for creating an AgileOps Sprint Report
        """
        report = {}

        sprint = self.getSprint(sprint_id)
        sprint_report = self.getSprintReport(sprint_id, sprint['originBoardId'])
        report = self.getJiraSprintReportData(sprint_report)
        report['issue_metrics'] = self.calculateSprintMetrics(sprint_report)
        board = self.getBoard(sprint['originBoardId'])
        report['project_name'] = board['location']['projectName']
        report['project_key'] = board['location']['projectKey']
        report['average_velocity'] = self.getAverageVelocity(sprint['originBoardId'], sprint_id)

        return report

    def getAverageVelocity(self, board_id, sprint_id = None):
        """"Gets the 3 sprint average velocity for a board as of a specific sprint

        Args:
            board_id: string - the id of a Jira board
            sprint_id: string - the id of a Jira sprint (defaults to None, in which case it assumes the most recently completely sprint)

        Returns:
            integer - The 3 sprint average velocity for the board_id as of the sprint_id provided
        """
        velocity_report = self.__makeRequest('GET',f"{self.__greenhopper_url}rapid/charts/velocity?rapidViewId={board_id}")

        if velocity_report == False:
            raise Error(f"I wasn't able to get the velocity report for board {board_id}. Please check your arguments again. Are you using the right command for your jira instance? Ask me for `help` for more information")

        total = 0
        sprints = 0
        found_sprint = True if sprint_id == None else False

        for sprint in sorted(velocity_report['velocityStatEntries'], reverse=True):
            if sprints >= 3:
                # We only care about the last three sprints
                break;

            if found_sprint == True or sprint_id == sprint:
                found_sprint = True
                total = total +  velocity_report['velocityStatEntries'][sprint]['completed']['value']
                sprints = sprints + 1

        return int(total/sprints) if sprints > 0 else total

    def generateGoogleFormURL(self, sprint_report_data):
        """Generates a URL that will pre-populate a specific AgileOps Google Form where teams submit their sprint metrics

        Args:
            sprint_report_data: dictionary - AgileOps Sprint Report Data

        Returns:
            string - A URL to a google form with relevant information pre-populate via query parameters
        """
        url = 'https://docs.google.com/forms/d/e/1FAIpQLSdF__V1ZMfl6H5q3xIQhSkeZMeCNkOHUdTBFdYA1HBavH31hA/formResponse?'

        google_entry_translations = {
        "issue_metrics": {
            "items": {
                "bugs_completed": 'entry.448087930',
                "committed": 'entry.2095001800',
                "completed": 'entry.1399119358',
                "not_completed": 'entry.128659456',
                "planned_completed": 'entry.954885633',
                "removed": 'entry.1137054034',
                "stories_completed": 'entry.1980453543',
                "unplanned_bugs_completed": 'entry.1252702382',
                "unplanned_completed": 'entry.485777497',
                "unplanned_stories_completed": 'entry.370334542'
            },
            "points": {
                "committed": 'entry.1427603868',
                "completed": 'entry.1486076673',
                "feature_completed": 'entry.254612996',
                "not_completed": 'entry.611444996',
                "optimization_completed": 'entry.2092919144',
                "planned_completed": 'entry.493624591',
                "removed": 'entry.976792423',
                "unplanned_completed": 'entry.1333444050'
            }
        },
        #TODO: We're assuming that the project name IS the team name, which isn't always the case
        "project_key": "entry.1082637073",
        "sprint_number": "entry.1975251686"
        }

        try:
            for entry in ["project_key", "sprint_number"]:
                url += f"{google_entry_translations[entry]}={sprint_report_data[entry]}&"

            for metric_type in sprint_report_data['issue_metrics'].keys():
                if metric_type in ["meta", "issue_keys"]:
                    continue
                for item in sprint_report_data['issue_metrics'][metric_type].keys():
                    url += f"{google_entry_translations['issue_metrics'][metric_type][item]}={sprint_report_data['issue_metrics'][metric_type][item]}&"
        except (KeyError):
            raise Error("I wasn't able to generate a Google Form URl for some reason. This probably isn't your fault, I've let my overlords know.", "Unable to generate Google Form URL, expected keys missing")

        url += "submit=Submit"

        return url

    def generateJiraIssueLink(self, issues):
        """Generates a link to a collection of Jira issues

        Args:
            issues: list - Jira issue id's

        Returns:
            string - A Jira link that will display the passed in issues
        """
        link =  f"https://{self.__host}/issues/?jql=issueKey%20in%20("

        for issue in issues:
            link += f"{issue}%2C"

        link = re.sub(r'\%2C$', '', link) + ")"

        return link

    def getBoardsInProject(self, projectkey):
        link = ""
        try:
            link = f"{self.__agile_url}board?projectKeyOrId={projectkey.upper()}"
            results = self.__makeRequest('GET', link)
            if results:
                return results
        except AttributeError:
            pass

        return False

    def getSprintsInBoard(self, board_id):
        # We handle pagination by using `startAt`.
        # Because how sprints are returned (oldest first) we will reverse the list before return.
        link = f"{self.__agile_url}board/{board_id}/sprint"
        sprints = []
        startAt = 0
        while True:
            # Get list of sprints, if this is not the start, then start at `startAt`
            url = f'{link}?startAt={startAt}' if startAt > 0 else link
            results = self.__makeRequest('GET', url)
            logging.debug(f"Sprint Results: {results}")

            if results:
                sprints.extend(results['values'])
                startAt += len(results['values'])

            if (not results) or (results.get('isLast', True)):
                # break from while if results is false or `isLast` is True.
                break

        # if the 'sprints' array is empty it'll still return a falsy object
        # no need to explicitly return "false"
        sprints.reverse()
        logging.debug(f"Sprints: {sprints}")
        return sprints

    def getFiltersWithJQL(self):
        link = f"{self.__url}filter/search?expand=jql"
        filters = []
        startAt = 0

        while True:
            # Get list of sprints, if this is not the start, then start at `startAt`
            url = f'{link}&startAt={startAt}' if startAt > 0 else link
            results = self.__makeRequest('GET', url)
            logging.debug(f"Filter Results: {results}")

            if results:
                filters.extend(results['values'])
                startAt += len(results['values'])

            if (not results) or (results.get('isLast', True)):
                # break from while if results is false or `isLast` is True.
                break

        return filters

    def searchFiltersForJQL(self, jql):
        filters = self.getFiltersWithJQL()

        for filter in filters:
            try:
                if re.search(jql, filter['jql']):
                    print(f"Filter Link: {filter['self']}\nFilter JQL: {filter['jql']}\n------------")
            except AttributeError:
                logging.error(f"Filter does not have jql...\n{filter}")

if __name__ == '__main__':
    jira_host = os.environ["JIRA_HOST"]
    jira_user = os.environ["JIRA_USER"]
    jira_token = os.environ["JIRA_TOKEN"]
    jira = Jira(jira_host, jira_user, jira_token)
