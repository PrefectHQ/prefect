import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { TaskRunsSortFilter } from "./task-run-sort-filter";

describe("TaskRunsSortFilter", () => {
	beforeAll(mockPointerEvents);

	it("renders with placeholder when no value is selected", () => {
		const onSelect = vi.fn();
		render(<TaskRunsSortFilter value={undefined} onSelect={onSelect} />);

		expect(screen.getByRole("combobox")).toBeVisible();
		expect(screen.getByText("Sort by")).toBeVisible();
	});

	it("renders with correct aria-label", () => {
		const onSelect = vi.fn();
		render(<TaskRunsSortFilter value={undefined} onSelect={onSelect} />);

		expect(
			screen.getByRole("combobox", { name: "Task run sort order" }),
		).toBeVisible();
	});

	it("displays 'Newest to oldest' when EXPECTED_START_TIME_DESC is selected", () => {
		const onSelect = vi.fn();
		render(
			<TaskRunsSortFilter
				value="EXPECTED_START_TIME_DESC"
				onSelect={onSelect}
			/>,
		);

		expect(screen.getByText("Newest to oldest")).toBeVisible();
	});

	it("displays 'Oldest to newest' when EXPECTED_START_TIME_ASC is selected", () => {
		const onSelect = vi.fn();
		render(
			<TaskRunsSortFilter
				value="EXPECTED_START_TIME_ASC"
				onSelect={onSelect}
			/>,
		);

		expect(screen.getByText("Oldest to newest")).toBeVisible();
	});

	it("calls onSelect with EXPECTED_START_TIME_DESC when 'Newest to oldest' is clicked", async () => {
		const user = userEvent.setup();
		const onSelect = vi.fn();
		render(<TaskRunsSortFilter value={undefined} onSelect={onSelect} />);

		await user.click(
			screen.getByRole("combobox", { name: /task run sort order/i }),
		);
		await user.click(screen.getByRole("option", { name: /newest to oldest/i }));

		expect(onSelect).toHaveBeenCalledWith("EXPECTED_START_TIME_DESC");
	});

	it("calls onSelect with EXPECTED_START_TIME_ASC when 'Oldest to newest' is clicked", async () => {
		const user = userEvent.setup();
		const onSelect = vi.fn();
		render(<TaskRunsSortFilter value={undefined} onSelect={onSelect} />);

		await user.click(
			screen.getByRole("combobox", { name: /task run sort order/i }),
		);
		await user.click(screen.getByRole("option", { name: /oldest to newest/i }));

		expect(onSelect).toHaveBeenCalledWith("EXPECTED_START_TIME_ASC");
	});

	it("uses defaultValue when provided and value is undefined", () => {
		const onSelect = vi.fn();
		render(
			<TaskRunsSortFilter
				defaultValue="EXPECTED_START_TIME_ASC"
				value={undefined}
				onSelect={onSelect}
			/>,
		);

		expect(screen.getByText("Oldest to newest")).toBeVisible();
	});

	it("shows both sort options in the dropdown", async () => {
		const user = userEvent.setup();
		const onSelect = vi.fn();
		render(<TaskRunsSortFilter value={undefined} onSelect={onSelect} />);

		await user.click(
			screen.getByRole("combobox", { name: /task run sort order/i }),
		);

		expect(
			screen.getByRole("option", { name: /newest to oldest/i }),
		).toBeVisible();
		expect(
			screen.getByRole("option", { name: /oldest to newest/i }),
		).toBeVisible();
	});
});
