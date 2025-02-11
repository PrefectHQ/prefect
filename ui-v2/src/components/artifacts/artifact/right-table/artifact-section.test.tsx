import { createFakeArtifact } from "@/mocks";
import { formatDate } from "@/utils/date";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ArtifactSection } from "./artifact-section";

describe("artifact section in details page right table", () => {
	const fakeArtifact = createFakeArtifact();

	it("renders artifact section with key", () => {
		const { getByText } = render(<ArtifactSection artifact={fakeArtifact} />);

		expect(getByText("Artifact")).toBeTruthy();
		expect(getByText("Key")).toBeTruthy();
		expect(getByText(fakeArtifact.key ?? "")).toBeTruthy();
	});

	it("renders artifact section with type", () => {
		const { getByText } = render(<ArtifactSection artifact={fakeArtifact} />);

		expect(getByText("Type")).toBeTruthy();
		expect(getByText(fakeArtifact.type ?? "")).toBeTruthy();
	});

	it("renders artifact section with created", () => {
		const { getByText } = render(<ArtifactSection artifact={fakeArtifact} />);

		expect(getByText("Created")).toBeTruthy();
		expect(
			getByText(formatDate(fakeArtifact.created ?? "", "dateTime")),
		).toBeTruthy();
	});
});
