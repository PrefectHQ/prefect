import { Artifact } from "@/api/artifacts";
import { createFakeArtifact } from "@/mocks";
import { render } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { ArtifactCard } from "./artifact-card";

describe("Artifacts Card", () => {
	it("renders artifact card with description", () => {
		const artifact: Artifact = createFakeArtifact({
			description: "This is a description",
		});
		const { getByText } = render(<ArtifactCard artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("This is a description")).toBeTruthy();
	});

	it("renders artifact card with updated date", () => {
		const artifact = createFakeArtifact({
			updated: "2021-09-01T12:00:00Z",
		});
		const { getByText } = render(<ArtifactCard artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("Last Updated")).toBeTruthy();
		expect(getByText("Sep 1st, 2021 at 5:00 AM")).toBeTruthy();
	});

	it("renders artifact card with key", () => {
		const artifact = createFakeArtifact({
			key: "test-key",
		});
		const { getByText } = render(<ArtifactCard artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("test-key")).toBeTruthy();
	});

	it("renders artifact card with type", () => {
		const artifact = createFakeArtifact({
			type: "test-type",
		});
		const { getByText } = render(<ArtifactCard artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("TEST-TYPE")).toBeTruthy();
	});
});
