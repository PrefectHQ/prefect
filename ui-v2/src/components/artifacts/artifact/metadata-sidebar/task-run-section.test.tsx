import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeTaskRun } from "@/mocks";
import { formatDate } from "@/utils/date";
import { TaskRunSection } from "./task-run-section";

describe("TaskRunSection", () => {
	it("renders task run section with created date", () => {
		const created = "2024-01-15T10:30:00.000Z";
		const taskRun = createFakeTaskRun({ created });

		render(<TaskRunSection taskRun={taskRun} />);

		expect(screen.getByText("Task Run")).toBeTruthy();
		expect(screen.getByText("Created")).toBeTruthy();
		expect(screen.getByText(formatDate(created, "dateTime"))).toBeTruthy();
	});

	it("renders task run section with last updated date", () => {
		const updated = "2024-01-15T11:30:00.000Z";
		const taskRun = createFakeTaskRun({ updated });

		render(<TaskRunSection taskRun={taskRun} />);

		expect(screen.getByText("Last Updated")).toBeTruthy();
		expect(screen.getByText(formatDate(updated, "dateTime"))).toBeTruthy();
	});

	it("renders task run section with tags", () => {
		const taskRun = createFakeTaskRun({ tags: ["tag1", "tag2"] });

		render(<TaskRunSection taskRun={taskRun} />);

		expect(screen.getByText("Tags")).toBeTruthy();
		expect(screen.getByText("tag1")).toBeTruthy();
		expect(screen.getByText("tag2")).toBeTruthy();
	});

	it("renders task run section with no tags", () => {
		const taskRun = createFakeTaskRun({ tags: [] });

		render(<TaskRunSection taskRun={taskRun} />);

		expect(screen.getByText("Tags")).toBeTruthy();
		expect(screen.getByText("None")).toBeTruthy();
	});
});
