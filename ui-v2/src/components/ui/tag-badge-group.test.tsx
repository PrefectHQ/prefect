import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TagBadgeGroup } from "./tag-badge-group";

const TAGS = ["alpha", "beta", "gamma", "delta", "epsilon"];

const TAG_WIDTH = 60;
const OVERFLOW_WIDTH = 30;

/**
 * jsdom has no layout, so give the group container a fixed width and each
 * tag/overflow control a fixed width to exercise the fit calculation.
 */
const mockLayout = (
	containerWidth: number,
	overflowWidth: (label: string) => number = () => OVERFLOW_WIDTH,
) => {
	const clientWidth = Object.getOwnPropertyDescriptor(
		Element.prototype,
		"clientWidth",
	);
	Object.defineProperty(Element.prototype, "clientWidth", {
		configurable: true,
		get(this: Element) {
			return this.getAttribute("data-slot") === "tag-badge-group"
				? containerWidth
				: 0;
		},
	});
	const widthOf = (element: Element) => {
		switch (element.getAttribute("data-slot")) {
			case "tag-badge-group-item":
				return TAG_WIDTH;
			case "tag-badge-group-overflow-sizer":
				return overflowWidth(element.textContent ?? "");
			default:
				return 0;
		}
	};
	const spy = vi
		.spyOn(Element.prototype, "getBoundingClientRect")
		.mockImplementation(function (this: Element) {
			const width = widthOf(this);
			return {
				x: 0,
				y: 0,
				top: 0,
				left: 0,
				bottom: 0,
				right: width,
				width,
				height: 0,
				toJSON: () => ({}),
			};
		});
	return () => {
		spy.mockRestore();
		if (clientWidth) {
			Object.defineProperty(Element.prototype, "clientWidth", clientWidth);
		}
	};
};

const getVisibleTag = (tag: string) => screen.getByText(tag);

const getOverflowButton = () =>
	screen.getByRole("button", { name: /show \d+ more tags/i });

describe("TagBadgeGroup", () => {
	let restoreLayout: (() => void) | undefined;

	afterEach(() => {
		restoreLayout?.();
		restoreLayout = undefined;
	});

	it("shows every tag name when there is room", () => {
		render(<TagBadgeGroup tags={TAGS} />);

		for (const tag of TAGS) {
			expect(getVisibleTag(tag)).toBeVisible();
		}
		expect(
			screen.queryByRole("button", { name: /more tags/i }),
		).not.toBeInTheDocument();
	});

	it("renders nothing without tags", () => {
		const { container } = render(<TagBadgeGroup tags={[]} />);

		expect(container).toBeEmptyDOMElement();
	});

	it("keeps the tags that fit and summarizes the rest", () => {
		// 2 tags (120) + overflow (30) fit in 160; a third tag would need 210
		restoreLayout = mockLayout(160);
		render(<TagBadgeGroup tags={TAGS} />);

		expect(getVisibleTag("alpha")).toBeVisible();
		expect(getVisibleTag("beta")).toBeVisible();
		expect(getOverflowButton()).toHaveTextContent("+3");
		expect(getOverflowButton()).toHaveAccessibleName("Show 3 more tags");
		expect(getOverflowButton()).toHaveAttribute(
			"title",
			"gamma, delta, epsilon",
		);
	});

	it("measures duplicate tags independently", () => {
		// 2 tags (120) + overflow (30) fit in 160
		restoreLayout = mockLayout(160);
		render(<TagBadgeGroup tags={["alpha", "alpha", "beta", "beta"]} />);

		expect(screen.getAllByText("alpha")).toHaveLength(2);
		expect(getOverflowButton()).toHaveTextContent("+2");
		expect(getOverflowButton()).toHaveAttribute("title", "beta, beta");
	});

	it("keeps keys unique when a tag equals another tag's generated key", () => {
		const consoleError = vi
			.spyOn(console, "error")
			.mockImplementation(() => {});
		render(<TagBadgeGroup tags={["alpha#1", "1:alpha", "alpha", "alpha"]} />);

		expect(screen.getAllByText("alpha")).toHaveLength(2);
		const keyWarnings = consoleError.mock.calls.filter(([message]) =>
			String(message).includes("same key"),
		);
		consoleError.mockRestore();
		expect(keyWarnings).toHaveLength(0);
	});

	it("reserves room for the widest possible overflow counter", () => {
		// container 165: two tags plus a 30px one-digit counter would fit (150),
		// but a two-digit counter is 50px wide, so only one tag may stay visible
		restoreLayout = mockLayout(165, (label) => (label.length > 2 ? 50 : 30));
		const tags = Array.from({ length: 12 }, (_, i) => `tag-${i}`);
		render(<TagBadgeGroup tags={tags} />);

		expect(getVisibleTag("tag-0")).toBeVisible();
		expect(getOverflowButton()).toHaveTextContent("+11");
		expect(getOverflowButton()).toHaveAttribute(
			"title",
			expect.stringMatching(/^tag-1, /),
		);
	});

	it("asks its parent for the width of every tag, not just the visible ones", () => {
		// only 2 of 5 tags fit, but the group must still request room for all
		// 5 (300px) so it can grow back when the parent widens
		restoreLayout = mockLayout(160);
		const { container } = render(<TagBadgeGroup tags={TAGS} />);

		expect(getOverflowButton()).toHaveTextContent("+3");
		expect(container.firstElementChild).toHaveStyle({
			width: `${TAGS.length * TAG_WIDTH}px`,
		});
	});

	it("asks only for the room maxTagsDisplayed tags and the counter need", () => {
		restoreLayout = mockLayout(160);
		const { container } = render(
			<TagBadgeGroup tags={TAGS} maxTagsDisplayed={3} />,
		);

		expect(container.firstElementChild).toHaveStyle({
			width: `${3 * TAG_WIDTH + OVERFLOW_WIDTH}px`,
		});
	});

	it("renders a non-interactive overflow badge with overflow='badge'", () => {
		render(<TagBadgeGroup tags={TAGS} maxTagsDisplayed={2} overflow="badge" />);

		expect(screen.queryByRole("button")).not.toBeInTheDocument();
		const badge = screen.getByText("+3");
		expect(badge).toHaveAttribute("title", "gamma, delta, epsilon");
		expect(badge).toHaveAccessibleName("3 more tags: gamma, delta, epsilon");
	});

	it("caps the inline tags with maxTagsDisplayed even when there is room", () => {
		render(<TagBadgeGroup tags={TAGS} maxTagsDisplayed={2} />);

		expect(getVisibleTag("alpha")).toBeVisible();
		expect(getVisibleTag("beta")).toBeVisible();
		expect(getOverflowButton()).toHaveTextContent("+3");
	});

	it("opens the hidden tags with the keyboard", async () => {
		const user = userEvent.setup();
		render(<TagBadgeGroup tags={TAGS} maxTagsDisplayed={2} />);

		await user.tab();
		expect(getOverflowButton()).toHaveFocus();

		await user.keyboard("{Enter}");

		const popover = await screen.findByRole("dialog");
		expect(within(popover).getByText("gamma")).toBeInTheDocument();
		expect(within(popover).getByText("delta")).toBeInTheDocument();
		expect(within(popover).getByText("epsilon")).toBeInTheDocument();
	});

	it("opens the hidden tags with a pointer", async () => {
		const user = userEvent.setup();
		render(<TagBadgeGroup tags={TAGS} maxTagsDisplayed={2} />);

		await user.click(getOverflowButton());

		const popover = await screen.findByRole("dialog");
		expect(within(popover).getByText("gamma")).toBeInTheDocument();
	});

	it("keeps tag actions for hidden tags", async () => {
		const user = userEvent.setup();
		const onTagsChange = vi.fn();
		const onTagClick = vi.fn();
		render(
			<TagBadgeGroup
				tags={TAGS}
				maxTagsDisplayed={2}
				onTagsChange={onTagsChange}
				onTagClick={onTagClick}
			/>,
		);

		await user.click(getOverflowButton());
		const popover = await screen.findByRole("dialog");

		await user.click(within(popover).getByText("gamma"));
		expect(onTagClick).toHaveBeenCalledWith("gamma");

		await user.click(
			within(popover).getByRole("button", { name: "Remove delta tag" }),
		);
		expect(onTagsChange).toHaveBeenCalledWith([
			"alpha",
			"beta",
			"gamma",
			"epsilon",
		]);
	});

	it("does not expose hidden tags outside the popover", () => {
		const onTagsChange = vi.fn();
		render(
			<TagBadgeGroup
				tags={TAGS}
				maxTagsDisplayed={2}
				onTagsChange={onTagsChange}
			/>,
		);

		expect(
			screen.getAllByRole("button", { name: /^remove .* tag$/i }),
		).toHaveLength(2);
	});
});
