import { createFakeArtifact } from "@/mocks";
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ArtifactDataDisplay } from "./artifact-raw-data-display";

describe("ArtifactDataDisplay", () => {
	it("renders artifact data display", () => {
		const artifact = createFakeArtifact({
			type: "markdown",
			data: "test-data",
		});

		const { getByText, queryByText, getByTestId } = render(
			<ArtifactDataDisplay artifact={artifact} />,
		);

		expect(queryByText("test-data")).toBeFalsy();

		const toggleButton = getByTestId("show-raw-data-button");

		fireEvent.click(toggleButton);

		expect(getByText("test-data")).toBeTruthy();
	});
});
