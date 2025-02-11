import { createFakeTaskRun } from "@/mocks";
import { formatDate } from "@/utils/date";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TaskRunSection } from "./task-run-section";

describe("flow run section in details page right table", () => {
	const fakeTaskRun = createFakeTaskRun({
		tags: ["tag1", "tag2"],
	});

	it("renders task run section with created", () => {
		const { getByText } = render(<TaskRunSection taskRun={fakeTaskRun} />);

		expect(getByText("Created")).toBeTruthy();
		expect(
			getByText(formatDate(fakeTaskRun.created ?? "", "dateTime")),
		).toBeTruthy();
	});

	it("renders task run section with last updated", () => {
		const { getByText } = render(<TaskRunSection taskRun={fakeTaskRun} />);

		expect(getByText("Last Updated")).toBeTruthy();
		expect(
			getByText(formatDate(fakeTaskRun.updated ?? "", "dateTime")),
		).toBeTruthy();
	});

	it("renders task run section with tags", () => {
		const { getByText } = render(<TaskRunSection taskRun={fakeTaskRun} />);

		expect(getByText("Tags")).toBeTruthy();
		expect(getByText("tag1")).toBeTruthy();
		expect(getByText("tag2")).toBeTruthy();
	});

	it("renders task run section with no tags", () => {
		const fakeTaskRunNoTags = createFakeTaskRun({
			tags: [],
		});
		const { getByText } = render(
			<TaskRunSection taskRun={fakeTaskRunNoTags} />,
		);

		expect(getByText("Tags")).toBeTruthy();
		expect(getByText("None")).toBeTruthy();
	});
});
