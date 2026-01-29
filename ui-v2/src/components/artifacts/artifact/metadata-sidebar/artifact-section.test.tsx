import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeArtifact } from "@/mocks";
import { formatDate } from "@/utils/date";
import { ArtifactSection } from "./artifact-section";

describe("ArtifactSection", () => {
	it("renders artifact section with key", () => {
		const artifact = createFakeArtifact({ key: "test-key" });

		render(<ArtifactSection artifact={artifact} />);

		expect(screen.getByText("Artifact")).toBeTruthy();
		expect(screen.getByText("Key")).toBeTruthy();
		expect(screen.getByText("test-key")).toBeTruthy();
	});

	it("renders artifact section with type", () => {
		const artifact = createFakeArtifact({ type: "markdown" });

		render(<ArtifactSection artifact={artifact} />);

		expect(screen.getByText("Type")).toBeTruthy();
		expect(screen.getByText("markdown")).toBeTruthy();
	});

	it("renders artifact section with created date", () => {
		const created = "2024-01-15T10:30:00.000Z";
		const artifact = createFakeArtifact({ created });

		render(<ArtifactSection artifact={artifact} />);

		expect(screen.getByText("Created")).toBeTruthy();
		expect(screen.getByText(formatDate(created, "dateTime"))).toBeTruthy();
	});

	it("renders None when key is missing", () => {
		const artifact = createFakeArtifact({ key: null });

		render(<ArtifactSection artifact={artifact} />);

		const noneElements = screen.getAllByText("None");
		expect(noneElements.length).toBeGreaterThan(0);
	});
});
