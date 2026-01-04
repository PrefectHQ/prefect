import { render, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DetailMarkdown } from "./detail-markdown";

describe("ArtifactDetailMarkdown", () => {
	it("renders artifact detail markdown", async () => {
		const markdown = "# Title\n\nThis is a test markdown";

		const { getByText } = render(<DetailMarkdown markdown={markdown} />);

		await waitFor(() => {
			expect(getByText("Title")).toBeTruthy();
		});
	});
});
