import { describe, expect, it } from "vitest";
import { DEFAULT_TEXT_RESOLUTION } from "@/graphs/consts";

const svgs = import.meta.glob<string>("./*.svg", {
	query: "?raw",
	import: "default",
	eager: true,
});

const getRootAttribute = (svg: string, name: string): string | undefined => {
	const root = svg.match(/<svg\b[^>]*>/)?.[0] ?? "";
	return root.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1];
};

describe("graph icon SVGs", () => {
	it("finds the icon files", () => {
		expect(Object.keys(svgs).length).toBeGreaterThan(0);
	});

	// WebGL can't upload an SVG image without intrinsic dimensions as a texture
	// (texImage2D fails with INVALID_VALUE), which renders the icon as a black
	// box. The image is rasterized at its intrinsic size, so it's declared at the
	// same resolution as graph text to stay sharp when the graph is zoomed in.
	it.each(Object.entries(svgs))(
		"%s declares width and height at text resolution",
		(_, svg) => {
			const [, , viewBoxWidth, viewBoxHeight] = (
				getRootAttribute(svg, "viewBox") ?? ""
			)
				.split(/\s+/)
				.map(Number);

			expect(Number(getRootAttribute(svg, "width"))).toBe(
				viewBoxWidth * DEFAULT_TEXT_RESOLUTION,
			);
			expect(Number(getRootAttribute(svg, "height"))).toBe(
				viewBoxHeight * DEFAULT_TEXT_RESOLUTION,
			);
		},
	);
});
