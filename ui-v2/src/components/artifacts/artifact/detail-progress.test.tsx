import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DetailProgress } from "./detail-progress";

describe("ArtifactDetailProgress", () => {
	it("renders artifact detail progress", () => {
		const progress = 50;

		const { getByText } = render(<DetailProgress progress={progress} />);

		expect(getByText(/Progress/)).toBeTruthy();
		expect(getByText(/Progress/)).toHaveTextContent("Progress: 50%");
	});
});
