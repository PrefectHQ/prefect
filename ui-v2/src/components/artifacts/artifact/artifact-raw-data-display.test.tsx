import { fireEvent, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { createFakeArtifact } from "@/mocks";
import { ArtifactDataDisplay } from "./artifact-raw-data-display";

describe("ArtifactDataDisplay", () => {
	it.each([
		{ data: { count: 12 }, expected: '{\n  "count": 12\n}' },
		{ data: [{ count: 12 }], expected: '[\n  {\n    "count": 12\n  }\n]' },
		{ data: "test-data", expected: "test-data" },
		{ data: null, expected: "null" },
	])("displays and copies $data as raw data", async ({ data, expected }) => {
		const user = userEvent.setup();
		const { getByTestId, getByRole } = render(
			<ArtifactDataDisplay artifact={createFakeArtifact({ data })} />,
		);

		await user.click(getByRole("button", { name: "Show Raw Data" }));

		const lines = getByTestId("raw-data-display").querySelectorAll(".cm-line");
		expect(Array.from(lines, (line) => line.textContent).join("\n")).toBe(
			expected,
		);

		await user.click(getByRole("button", { name: "copy" }));
		expect(await navigator.clipboard.readText()).toBe(expected);
	});

	it("renders artifact data display", () => {
		const artifact = createFakeArtifact({
			type: "markdown",
			data: "test-data",
		});

		const { getByTestId } = render(<ArtifactDataDisplay artifact={artifact} />);

		expect(getByTestId("raw-data-display")).not.toBeVisible();

		const toggleButton = getByTestId("show-raw-data-button");

		fireEvent.click(toggleButton);

		expect(getByTestId("raw-data-display")).toBeVisible();
	});
});
