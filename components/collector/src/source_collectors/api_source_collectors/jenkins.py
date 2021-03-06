"""Jenkins metric collector."""

from datetime import datetime, date
from typing import Iterator, cast

from base_collectors import SourceCollector
from collector_utilities.functions import days_ago, match_string_or_regular_expression
from collector_utilities.type import URL, Job, Jobs
from source_model import Entity, SourceMeasurement, SourceResponses


class JenkinsJobs(SourceCollector):
    """Collector to get job counts from Jenkins."""

    async def _api_url(self) -> URL:
        url = await super()._api_url()
        job_attrs = "buildable,color,url,name,builds[result,timestamp]"
        return URL(f"{url}/api/json?tree=jobs[{job_attrs},jobs[{job_attrs},jobs[{job_attrs}]]]")

    async def _parse_source_responses(self, responses: SourceResponses) -> SourceMeasurement:
        entities = [
            Entity(
                key=job["name"],
                name=job["name"],
                url=job["url"],
                build_status=self._build_status(job),
                build_date=str(self._build_datetime(job).date()) if self._build_datetime(job) > datetime.min else "",
            )
            for job in self.__jobs((await responses[0].json())["jobs"])
        ]
        return SourceMeasurement(entities=entities)

    def __jobs(self, jobs: Jobs, parent_job_name: str = "") -> Iterator[Job]:
        """Recursively return the jobs and their child jobs that need to be counted for the metric."""
        for job in jobs:
            if parent_job_name:
                job["name"] = f"{parent_job_name}/{job['name']}"
            if job.get("buildable") and self._include_job(job):
                yield job
            for child_job in self.__jobs(job.get("jobs", []), parent_job_name=job["name"]):
                yield child_job

    def _include_job(self, job: Job) -> bool:
        """Return whether the job should be counted."""
        jobs_to_include = self._parameter("jobs_to_include")
        if len(jobs_to_include) > 0 and not match_string_or_regular_expression(job["name"], jobs_to_include):
            return False
        return not match_string_or_regular_expression(job["name"], self._parameter("jobs_to_ignore"))

    def _build_datetime(self, job: Job) -> datetime:
        """Return the date and time of the most recent build of the job."""
        builds = [build for build in job.get("builds", []) if self._include_build(build)]
        return datetime.utcfromtimestamp(int(builds[0]["timestamp"]) / 1000.0) if builds else datetime.min

    def _build_status(self, job: Job) -> str:
        """Return the status of the most recent build of the job."""
        builds = [build for build in job.get("builds", []) if self._include_build(build)]
        for build in builds:
            if status := build.get("result"):
                return str(status).capitalize().replace("_", " ")
        return "Not built"

    def _include_build(  # pylint: disable=no-self-use,unused-argument # skipcq: PYL-W0613,PYL-R0201
        self, build
    ) -> bool:
        """Return whether the include this build."""
        return True


class JenkinsFailedJobs(JenkinsJobs):
    """Collector to get failed jobs from Jenkins."""

    def _include_job(self, job: Job) -> bool:
        """Count the job if its build status matches the failure types selected by the user."""
        return super()._include_job(job) and self._build_status(job) in self._parameter("failure_type")


class JenkinsUnusedJobs(JenkinsJobs):
    """Collector to get unused jobs from Jenkins."""

    def _include_job(self, job: Job) -> bool:
        """Count the job if its most recent build is too old."""
        if super()._include_job(job) and (build_datetime := self._build_datetime(job)) > datetime.min:
            max_days = int(cast(str, self._parameter("inactive_days")))
            return days_ago(build_datetime) > max_days
        return False


class JenkinsSourceUpToDateness(JenkinsJobs):
    """Collector to get the last build date from Jenkins jobs."""

    def _include_build(self, build) -> bool:
        """Override to only include builds with an allowed result type."""
        result_types = self._parameter("result_type")
        return str(build.get("result", "Not built")).capitalize().replace("_", " ") in result_types

    async def _parse_source_responses(self, responses: SourceResponses) -> SourceMeasurement:
        """Extend to calculate how many days ago the jobs were built."""
        measurement = await super()._parse_source_responses(responses)
        build_dates = [entity["build_date"] for entity in measurement.entities if entity["build_date"]]
        measurement.value = str((date.today() - date.fromisoformat(max(build_dates))).days) if build_dates else None
        return measurement
