import { createFakeArtifact } from "@/mocks";
import { render } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { ArtifactsPage } from "./artifacts-page";

describe("Artifacts Page", () => {
	const defaultCount = 2;
	const defaultArtifacts = Array.from(
		{ length: defaultCount },
		createFakeArtifact,
	);
	const defaultFilters = [
		{ id: "type", label: "Type", value: "all" },
		{ id: "name", label: "Name", value: "" },
	];
	const onFilterChange = vi.fn();

	it("renders filter", () => {
		const { findByTestId } = render(
			<ArtifactsPage
				filters={defaultFilters}
				onFilterChange={onFilterChange}
				artifactsCount={defaultCount}
				artifactsList={defaultArtifacts}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(findByTestId("artifact-filter")).toBeTruthy();
		expect("Artifacts").toBeTruthy();
	});
});
