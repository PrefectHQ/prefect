import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeArtifact } from "@/mocks";
import { ArtifactDataDisplay } from "./artifact-raw-data-display";

describe("ArtifactDataDisplay", () => {
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
