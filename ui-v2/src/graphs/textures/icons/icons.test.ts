import { describe, expect, it } from "vitest";

const svgs = import.meta.glob<string>("./*.svg", {
	query: "?raw",
	import: "default",
	eager: true,
});

describe("graph icon SVGs", () => {
	it("finds the icon files", () => {
		expect(Object.keys(svgs).length).toBeGreaterThan(0);
	});

	// WebGL can't upload an SVG image without intrinsic dimensions as a texture
	// (texImage2D fails with INVALID_VALUE), which renders the icon as a black box.
	it.each(Object.entries(svgs))("%s declares width and height", (_, svg) => {
		const root = svg.match(/<svg\b[^>]*>/)?.[0] ?? "";
		expect(root).toMatch(/\swidth="\d+"/);
		expect(root).toMatch(/\sheight="\d+"/);
	});
});
