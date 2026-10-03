import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeDeployment } from "@/mocks";
import { DeploymentTagsSelect } from "./deployment-tags-select";

beforeAll(() => {
	mockPointerEvents();
});

const mockDeploymentsAPI = (tags: string[][]) => {
	server.use(
		http.post(buildApiUrl("/deployments/filter"), () =>
			HttpResponse.json(
				tags.map((deploymentTags) =>
					createFakeDeployment({ tags: deploymentTags }),
				),
			),
		),
	);
};

describe("DeploymentTagsSelect", () => {
	beforeEach(() => {
		mockDeploymentsAPI([
			["production", "team-b"],
			["nightly", "production"],
			[],
		]);
	});

	const openSelect = async (user: ReturnType<typeof userEvent.setup>) => {
		await user.click(screen.getByRole("button", { name: "Filter by tags" }));
	};

	it("suggests the tags of existing deployments, deduplicated and sorted", async () => {
		const user = userEvent.setup();
		render(<DeploymentTagsSelect value={[]} onChange={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		await openSelect(user);

		const listbox = await screen.findByRole("listbox");
		const options = await within(listbox).findAllByRole("option");
		expect(options.map((option) => option.textContent)).toEqual([
			"nightly",
			"production",
			"team-b",
		]);
	});

	it("adds a suggested tag to the selection", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(<DeploymentTagsSelect value={["nightly"]} onChange={onChange} />, {
			wrapper: createWrapper(),
		});

		await openSelect(user);
		const listbox = await screen.findByRole("listbox");
		await user.click(await within(listbox).findByText("production"));

		expect(onChange).toHaveBeenCalledWith(["nightly", "production"]);
	});

	it("adds a tag that no deployment uses", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(<DeploymentTagsSelect value={[]} onChange={onChange} />, {
			wrapper: createWrapper(),
		});

		await openSelect(user);
		await user.type(screen.getByRole("combobox"), "unknown-tag");
		await user.keyboard("{Enter}");

		expect(onChange).toHaveBeenCalledWith(["unknown-tag"]);
	});
});
