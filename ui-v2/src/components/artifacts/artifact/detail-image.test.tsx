import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeArtifact } from "@/mocks";
import { DetailImage } from "./detail-image";

describe("ArtifactDetailImage", () => {
	it("renders artifact detail image", () => {
		const url = "https://example.com/image.png";
		const artifact = createFakeArtifact({
			type: "image",
			data: url,
		});

		const { getByTestId } = render(
			<DetailImage url={artifact.data as string} />,
		);

		expect(getByTestId(url)).toBeTruthy();
		expect(getByTestId(`image-${url}`)).toHaveAttribute("src", url);
		expect(getByTestId(`image-${url}`)).toHaveAttribute(
			"alt",
			"artifact-image",
		);
	});

	it("renders with url link", () => {
		const url = "https://example.com/image.png";
		const artifact = createFakeArtifact({
			type: "image",
			data: url,
		});

		const { getByText } = render(<DetailImage url={artifact.data as string} />);

		expect(getByText("Image URL:")).toBeTruthy();
		expect(getByText("Image URL:")).toHaveTextContent(
			"Image URL: https://example.com/image.png",
		);
	});
});
