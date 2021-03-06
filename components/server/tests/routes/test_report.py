"""Unit tests for the report routes."""

import unittest
from datetime import datetime
from typing import cast
from unittest.mock import Mock, patch

from routes.report import (
    delete_report,
    export_report_as_pdf,
    get_report,
    get_tag_report,
    post_report_attribute,
    post_report_copy,
    post_report_import,
    post_report_new,
)
from server_utilities.type import ReportId

from ..fixtures import JENNY, JOHN, REPORT_ID, REPORT_ID2, SUBJECT_ID, create_report


@patch("bottle.request")
class PostReportAttributeTest(unittest.TestCase):
    """Unit tests for the post report attribute route."""

    def setUp(self):
        """Override to set up a database with a report and a user session."""
        self.database = Mock()
        self.report = dict(_id="id", report_uuid=REPORT_ID, title="Title")
        self.database.reports.find.return_value = [self.report]
        self.database.sessions.find_one.return_value = JOHN
        self.database.datamodels.find_one.return_value = {}
        self.database.measurements.find.return_value = []

    def test_post_report_title(self, request):
        """Test that the report title can be changed."""
        request.json = dict(title="New title")
        self.assertEqual(dict(ok=True), post_report_attribute(REPORT_ID, "title", self.database))
        self.database.reports.insert.assert_called_once_with(self.report)
        self.assertEqual(
            dict(
                uuids=[REPORT_ID],
                email=JOHN["email"],
                description="John changed the title of report 'Title' from 'Title' to 'New title'.",
            ),
            self.report["delta"],
        )

    def test_post_report_layout(self, request):
        """Test that the report layout can be changed."""
        request.json = dict(layout=[dict(x=1, y=2)])
        self.assertEqual(dict(ok=True), post_report_attribute(REPORT_ID, "layout", self.database))
        self.database.reports.insert.assert_called_once_with(self.report)
        self.assertEqual(
            dict(uuids=[REPORT_ID], email=JOHN["email"], description="John changed the layout of report 'Title'."),
            self.report["delta"],
        )


class ReportTest(unittest.TestCase):
    """Unit tests for adding, deleting, and getting reports."""

    def setUp(self):
        """Override to set up a database with a report and a user session."""
        self.database = Mock()
        self.database.sessions.find_one.return_value = JENNY
        self.database.datamodels.find_one.return_value = dict(
            _id="id",
            subjects=dict(subject_type=dict(name="Subject type")),
            metrics=dict(metric_type=dict(name="Metric type")),
            sources=dict(source_type=dict(name="Source type", parameters={})),
        )
        self.report = create_report()
        self.database.reports.find.return_value = [self.report]
        self.database.measurements.find.return_value = []
        self.options = (
            "emulateScreenMedia=false&goto.timeout=60000&scrollPage=true&waitFor=10000&pdf.scale=0.7&"
            "pdf.margin.top=25&pdf.margin.bottom=25&pdf.margin.left=25&pdf.margin.right=25"
        )

    def test_get_report(self):
        """Test that a report can be retrieved."""
        self.assertEqual(REPORT_ID, get_report(self.database, REPORT_ID)["reports"][0]["report_uuid"])

    def test_get_report_and_info_about_other_reports(self):
        """Test that a report can be retrieved, and that other reports are also returned."""
        self.database.reports.find.return_value.insert(0, dict(_id="id2", report_uuid=REPORT_ID2))
        self.assertEqual(2, len(get_report(self.database, REPORT_ID)["reports"]))

    def test_get_report_missing(self):
        """Test that a report can be retrieved."""
        self.database.reports.find.return_value = []
        self.assertEqual([], get_report(self.database, ReportId("report does not exist"))["reports"])

    def test_add_report(self):
        """Test that a report can be added."""
        self.assertTrue(post_report_new(self.database)["ok"])
        self.database.reports.insert.assert_called_once()
        inserted = self.database.reports.insert.call_args_list[0][0][0]
        self.assertEqual("New report", inserted["title"])
        self.assertEqual(
            dict(uuids=[inserted["report_uuid"]], email=JENNY["email"], description="Jenny created a new report."),
            inserted["delta"],
        )

    def test_copy_report(self):
        """Test that a report can be copied."""
        self.assertTrue(post_report_copy(REPORT_ID, self.database)["ok"])
        self.database.reports.insert.assert_called_once()
        inserted_report = self.database.reports.insert.call_args[0][0]
        inserted_report_uuid = inserted_report["report_uuid"]
        self.assertNotEqual(self.report["report_uuid"], inserted_report_uuid)
        self.assertEqual(
            dict(
                uuids=[REPORT_ID, inserted_report_uuid],
                email=JENNY["email"],
                description="Jenny copied the report 'Report'.",
            ),
            inserted_report["delta"],
        )

    @patch("requests.get")
    def test_get_pdf_report(self, requests_get):
        """Test that a PDF version of the report can be retrieved."""
        response = Mock()
        response.content = b"PDF"
        requests_get.return_value = response
        self.assertEqual(b"PDF", export_report_as_pdf(cast(ReportId, "report_uuid")))
        requests_get.assert_called_once_with(
            f"http://renderer:9000/api/render?url=http%3A//www%3A80/report_uuid&{self.options}"
        )

    @patch("requests.get")
    def test_get_pdf_tag_report(self, requests_get):
        """Test that a PDF version of a tag report can be retrieved."""
        requests_get.return_value = Mock(content=b"PDF")
        self.assertEqual(b"PDF", export_report_as_pdf(cast(ReportId, "tag-security")))
        requests_get.assert_called_once_with(
            f"http://renderer:9000/api/render?url=http%3A//www%3A80/tag-security&{self.options}"
        )

    def test_delete_report(self):
        """Test that the report can be deleted."""
        self.assertEqual(dict(ok=True), delete_report(REPORT_ID, self.database))
        inserted = self.database.reports.insert.call_args_list[0][0][0]
        self.assertEqual(
            dict(uuids=[REPORT_ID], email=JENNY["email"], description="Jenny deleted the report 'Report'."),
            inserted["delta"],
        )

    @patch("bottle.request")
    def test_post_report_import(self, request):
        """Test that a report is imported correctly."""
        request.json = dict(_id="id", title="Title", report_uuid="report_uuid", subjects={})
        post_report_import(self.database)
        inserted = self.database.reports.insert.call_args_list[0][0][0]
        self.assertEqual("Title", inserted["title"])
        self.assertEqual("report_uuid", inserted["report_uuid"])

    @patch("server_utilities.functions.datetime")
    def test_get_tag_report(self, date_time):
        """Test that a tag report can be retrieved."""
        date_time.now.return_value = now = datetime.now()
        self.database.reports.find.return_value = [
            dict(
                _id="id",
                report_uuid=REPORT_ID,
                title="Report",
                subjects={
                    "subject_without_metrics": dict(metrics={}),
                    SUBJECT_ID: dict(
                        name="Subject",
                        type="subject_type",
                        metrics=dict(
                            metric_with_tag=dict(type="metric_type", tags=["tag"]),
                            metric_without_tag=dict(type="metric_type", tags=["other tag"]),
                        ),
                    ),
                },
            )
        ]
        self.assertDictEqual(
            dict(
                summary=dict(red=0, green=0, yellow=0, grey=0, white=1),
                summary_by_tag=dict(tag=dict(red=0, green=0, yellow=0, grey=0, white=1)),
                summary_by_subject={SUBJECT_ID: dict(red=0, green=0, yellow=0, grey=0, white=1)},
                title='Report for tag "tag"',
                subtitle="Note: tag reports are read-only",
                report_uuid="tag-tag",
                timestamp=now.replace(microsecond=0).isoformat(),
                subjects={
                    SUBJECT_ID: dict(
                        name="Report / Subject",
                        type="subject_type",
                        metrics=dict(
                            metric_with_tag=dict(
                                status=None,
                                value=None,
                                scale="count",
                                recent_measurements=[],
                                type="metric_type",
                                tags=["tag"],
                            )
                        ),
                    )
                },
            ),
            get_tag_report("tag", self.database),
        )
