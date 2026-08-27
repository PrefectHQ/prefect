import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { TagsSelect } from "./tags-select";

const SUGGESTIONS = ["alpha", "beta", "prod"];

beforeAll(() => {
	mockPointerEvents();
});

describe("TagsSelect", () => {
	const openSelect = async (user: ReturnType<typeof userEvent.setup>) => {
		await user.click(screen.getByRole("button", { name: /tags/i }));
	};

	it("shows the placeholder when no tags are selected", () => {
		render(
			<TagsSelect
				suggestions={SUGGESTIONS}
				value={[]}
				onChange={vi.fn()}
				placeholder="All tags"
			/>,
		);

		expect(screen.getByText("All tags")).toBeInTheDocument();
	});

	it("shows selected tags in the trigger", () => {
		render(
			<TagsSelect
				suggestions={SUGGESTIONS}
				value={["alpha", "beta"]}
				onChange={vi.fn()}
			/>,
		);

		expect(screen.getByText("alpha")).toBeInTheDocument();
		expect(screen.getByText("beta")).toBeInTheDocument();
	});

	it("lists the suggestions", async () => {
		const user = userEvent.setup();
		render(
			<TagsSelect suggestions={SUGGESTIONS} value={[]} onChange={vi.fn()} />,
		);

		await openSelect(user);

		const listbox = await screen.findByRole("listbox");
		for (const suggestion of SUGGESTIONS) {
			expect(within(listbox).getByText(suggestion)).toBeInTheDocument();
		}
	});

	it("selects a suggestion", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<TagsSelect
				suggestions={SUGGESTIONS}
				value={["alpha"]}
				onChange={onChange}
			/>,
		);

		await openSelect(user);
		const listbox = await screen.findByRole("listbox");
		await user.click(within(listbox).getByText("prod"));

		expect(onChange).toHaveBeenCalledWith(["alpha", "prod"]);
	});

	it("filters the suggestions by the search value", async () => {
		const user = userEvent.setup();
		render(
			<TagsSelect suggestions={SUGGESTIONS} value={[]} onChange={vi.fn()} />,
		);

		await openSelect(user);
		await user.type(screen.getByRole("combobox"), "al");

		const listbox = await screen.findByRole("listbox");
		expect(within(listbox).getByText("alpha")).toBeInTheDocument();
		expect(within(listbox).queryByText("prod")).not.toBeInTheDocument();
	});

	it("adds a freeform tag on Enter", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<TagsSelect suggestions={SUGGESTIONS} value={[]} onChange={onChange} />,
		);

		await openSelect(user);
		await user.type(screen.getByRole("combobox"), "newtag");
		await user.keyboard("{Enter}");

		expect(onChange).toHaveBeenCalledWith(["newtag"]);
	});

	it("adds a tag when typing a trailing comma", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<TagsSelect suggestions={SUGGESTIONS} value={[]} onChange={onChange} />,
		);

		await openSelect(user);
		await user.type(screen.getByRole("combobox"), "temp,");

		await waitFor(() => {
			expect(onChange).toHaveBeenCalledWith(["temp"]);
		});
	});

	it("removes the last tag on Backspace when the search is empty", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<TagsSelect
				suggestions={SUGGESTIONS}
				value={["alpha"]}
				onChange={onChange}
			/>,
		);

		await openSelect(user);
		await user.keyboard("{Backspace}");

		expect(onChange).toHaveBeenCalledWith([]);
	});

	it("removes a tag with the remove button", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<TagsSelect
				suggestions={SUGGESTIONS}
				value={["alpha", "beta"]}
				onChange={onChange}
			/>,
		);

		await openSelect(user);
		await user.click(
			await screen.findByRole("button", { name: /remove alpha tag/i }),
		);

		expect(onChange).toHaveBeenCalledWith(["beta"]);
	});

	it("clears all tags", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<TagsSelect
				suggestions={SUGGESTIONS}
				value={["alpha", "beta"]}
				onChange={onChange}
			/>,
		);

		await openSelect(user);
		const listbox = await screen.findByRole("listbox");
		await user.click(await within(listbox).findByText(/clear all tags/i));

		expect(onChange).toHaveBeenCalledWith([]);
	});

	it("does not show 'No tags found' when there are no suggestions", async () => {
		const user = userEvent.setup();
		render(<TagsSelect suggestions={[]} value={[]} onChange={vi.fn()} />);

		await openSelect(user);

		const listbox = await screen.findByRole("listbox");
		expect(
			within(listbox).queryByText(/no tags found/i),
		).not.toBeInTheDocument();
	});
});
