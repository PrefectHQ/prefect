import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { FlowRunTagsInput } from "./flow-run-tags-input";

// Mock scrollIntoView function for tests
Object.defineProperty(Element.prototype, "scrollIntoView", {
	value: vi.fn(),
	writable: true,
});

describe("FlowRunTagsInput", () => {
	const mockOnChange = vi.fn();
	const mockAvailableTags = ["production", "staging", "development", "test"];

	beforeEach(() => {
		mockOnChange.mockClear();
	});

	it("renders with placeholder text when no tags are selected", () => {
		render(
			<FlowRunTagsInput
				value={[]}
				onChange={mockOnChange}
				availableTags={mockAvailableTags}
				placeholder="Add tags"
			/>,
		);

		expect(screen.getByText("Add tags")).toBeInTheDocument();
	});

	it("displays selected tags count when tags are selected", () => {
		render(
			<FlowRunTagsInput
				value={["production", "staging"]}
				onChange={mockOnChange}
				availableTags={mockAvailableTags}
				placeholder="Add tags"
			/>,
		);

		expect(screen.getByText("2 tags selected")).toBeInTheDocument();
	});

	it("shows singular form for one selected tag", () => {
		render(
			<FlowRunTagsInput
				value={["production"]}
				onChange={mockOnChange}
				availableTags={mockAvailableTags}
				placeholder="Add tags"
			/>,
		);

		expect(screen.getByText("1 tag selected")).toBeInTheDocument();
	});

	it("displays TagsInput component when tags are selected", () => {
		render(
			<FlowRunTagsInput
				value={["production", "staging"]}
				onChange={mockOnChange}
				availableTags={mockAvailableTags}
			/>,
		);

		// The TagsInput component should be rendered
		expect(screen.getByPlaceholderText("Selected tags")).toBeInTheDocument();
	});

	it("opens combobox and shows available tags", async () => {
		const user = userEvent.setup();
		render(
			<FlowRunTagsInput
				value={[]}
				onChange={mockOnChange}
				availableTags={mockAvailableTags}
				placeholder="Add tags"
			/>,
		);

		const comboboxButton = screen.getByRole("button", { name: /select tags/i });
		await user.click(comboboxButton);

		expect(screen.getByPlaceholderText("Search tags...")).toBeInTheDocument();

		// All available tags should be shown
		expect(screen.getByText("production")).toBeInTheDocument();
		expect(screen.getByText("staging")).toBeInTheDocument();
		expect(screen.getByText("development")).toBeInTheDocument();
		expect(screen.getByText("test")).toBeInTheDocument();
	});

	it("filters out already selected tags from available options", async () => {
		const user = userEvent.setup();
		render(
			<FlowRunTagsInput
				value={["production"]}
				onChange={mockOnChange}
				availableTags={mockAvailableTags}
				placeholder="Add tags"
			/>,
		);

		const comboboxButton = screen.getByRole("button", { name: /select tags/i });
		await user.click(comboboxButton);

		// Check that only 3 tags are available in the dropdown (not 4)
		const commandItems = screen.getAllByRole("option");
		expect(commandItems).toHaveLength(3);

		// But other tags should be shown
		expect(screen.getByText("staging")).toBeInTheDocument();
		expect(screen.getByText("development")).toBeInTheDocument();
		expect(screen.getByText("test")).toBeInTheDocument();
	});

	it("shows option to add custom tag when searching", async () => {
		const user = userEvent.setup();
		render(
			<FlowRunTagsInput
				value={[]}
				onChange={mockOnChange}
				availableTags={mockAvailableTags}
				placeholder="Add tags"
			/>,
		);

		const comboboxButton = screen.getByRole("button", { name: /select tags/i });
		await user.click(comboboxButton);

		const searchInput = screen.getByPlaceholderText("Search tags...");
		await user.type(searchInput, "custom-tag");

		expect(screen.getByText('Add "custom-tag"')).toBeInTheDocument();
	});

	it("shows empty state when no tags are available", async () => {
		const user = userEvent.setup();
		render(
			<FlowRunTagsInput
				value={[]}
				onChange={mockOnChange}
				availableTags={[]}
				placeholder="Add tags"
			/>,
		);

		const comboboxButton = screen.getByRole("button", { name: /select tags/i });
		await user.click(comboboxButton);

		expect(screen.getByText("No tags available")).toBeInTheDocument();
	});
});
