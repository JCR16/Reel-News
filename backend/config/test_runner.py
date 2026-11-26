# Reel News - Custom Test Runner
#
# Developed by: Reel News team
# Description: Provides readable, scenario-based test output
# while preserving Django's standard test execution behavior.
#
# External libraries:
# - Python unittest: Test execution and result reporting.
# - Django DiscoverRunner: Django's standard test runner.
#
# External code:
# - No third-party source code copied or adapted.

import unittest

from django.test.runner import DiscoverRunner


class ReelNewsTestResult(unittest.TextTestResult):

    def __init__(self, *args, **kwargs):
        # Initialize the standard unittest result handler
        super().__init__(*args, **kwargs)

        # Track the most recently executed test class
        self.current_test_class = None
        self.has_subtests = False

        # Track successful test methods and individual subtests
        self.passed_tests = 0
        self.passed_subtests = 0
        self.failed_subtests = 0

    def startTest(self, test):
        # Identify the class containing the current test
        test_class = type(test)

        # Display a section heading when entering a new test class
        if self.showAll and test_class != self.current_test_class:

            # Allow test classes to define custom section headings
            heading = getattr(
                test_class,
                "section_name",
                test_class.__name__
            )

            self.stream.writeln()
            self.stream.writeln(heading)
            self.stream.writeln("-" * len(heading))

            self.current_test_class = test_class

        # Reset subtest tracking for each new test
        self.has_subtests = False
        # Preserve standard unittest test execution and reporting
        super().startTest(test)

    def getDescription(self, test):
        # Handle individual subtest descriptions
        if hasattr(test, "params") and hasattr(test, "test_case"):
            return (
                f"{self.getDescription(test.test_case)} "
                f"({self.describe_subtest(test)})"
            )

        # Prefer a descriptive docstring when available
        description = test.shortDescription()

        if description:
            return description

        # Fall back to a readable method name
        return test._testMethodName.removeprefix(
            "test_"
        ).replace("_", " ").capitalize()

    def colorize(self, text, color):
        # Only apply colors when output is connected to a terminal
        if self.stream.isatty():
            return f"\033[{color}m{text}\033[0m"

        return str(text)

    def green(self, text):
        return self.colorize(text, 32)

    def red(self, text):
        return self.colorize(text, 31)

    def yellow(self, text):
        return self.colorize(text, 33)

    def addSubTest(self, test, subtest, err):
        # Track whether the current test contains subtests
        self.has_subtests = True

        # Track individual subtest outcomes
        if err is None:
            self.passed_subtests += 1
        else:
            self.failed_subtests += 1

        # Preserve standard result registration without duplicating
        # the default subtest output in verbose mode
        if self.showAll:
            unittest.TestResult.addSubTest(
                self, test, subtest, err
            )
        else:
            super().addSubTest(test, subtest, err)
            return

        # Start subtest output on a separate line
        if not self._newline:
            self.stream.writeln()
            self._newline = True

        # Determine the scenario description
        description = self.describe_subtest(subtest)

        # Determine the outcome of the subtest
        if err is None:
            outcome = self.green("ok")
        elif issubclass(err[0], test.failureException):
            outcome = self.red("FAIL")
        else:
            outcome = self.red("ERROR")

        # Display the individual scenario result
        self.stream.writeln(
            f"    {description} ... {outcome}"
        )

    def addSuccess(self, test):

        self.passed_tests += 1

        # Preserve standard output for tests without subtests
        if not self.showAll or not self.has_subtests:
            super().addSuccess(test)
            return

        # Register the successful parent test without repeating
        # its description
        unittest.TestResult.addSuccess(self, test)

        self.stream.writeln(
            f"    {self.green('All scenarios passed.')}"
        )

    def describe_subtest(self, subtest):
        # Format the parameters identifying the subtest scenario
        parameters = ", ".join(
            f"{key}={value!r}"
            for key, value in subtest.params.items()
        )

        return parameters or "Subtest"


class ReelNewsTextTestRunner(unittest.TextTestRunner):

    # Use our custom result formatting
    resultclass = ReelNewsTestResult

    def run(self, test):
        # Execute tests using the standard unittest runner
        result = super().run(test)

        if self.verbosity >= 2:

            # Collect result counts
            failures = len(result.failures)
            errors = len(result.errors)
            skipped = len(result.skipped)
            failed_subtests = result.failed_subtests

            self.stream.writeln()
            self.stream.writeln("Test Results Summary")
            self.stream.writeln("--------------------")

            self.stream.writeln(
                f"Test methods executed: {result.testsRun}"
            )

            self.stream.writeln(
                f"Passed: {result.green(result.passed_tests)}"
            )

            self.stream.writeln(
                f"Failure reports: "
                f"{result.red(failures) if failures else failures}"
            )

            self.stream.writeln(
                f"Error reports: "
                f"{result.red(errors) if errors else errors}"
            )

            self.stream.writeln(
                f"Skipped: "
                f"{result.yellow(skipped) if skipped else skipped}"
            )

            self.stream.writeln()

            self.stream.writeln(
                f"Subtests passed: "
                f"{result.green(result.passed_subtests)}"
            )

            self.stream.writeln(
                f"Subtests failed or errored: "
                f"{result.red(failed_subtests) if failed_subtests else failed_subtests}"
            )

            self.stream.writeln()

            # Display the overall outcome
            if result.wasSuccessful():
                self.stream.writeln(
                    result.green("All tests passed.")
                    if not result.skipped
                    and result.passed_tests == result.testsRun
                    else result.green("Test run successful.")
                )
            else:
                self.stream.writeln(
                    result.red("Test run unsuccessful.")
                )

        return result


class ReelNewsTestRunner(DiscoverRunner):

    # Preserve Django's test discovery and execution behavior
    # while using our custom output formatter
    test_runner = ReelNewsTextTestRunner