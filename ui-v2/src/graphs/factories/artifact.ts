import { artifactNodeFactory } from "@/graphs/factories/artifactNode";
import type { RunGraphArtifact } from "@/graphs/models/artifact";
import { emitter } from "@/graphs/objects/events";
import { isSelected, selectItem } from "@/graphs/objects/selection";

export type ArtifactFactory = Awaited<ReturnType<typeof artifactFactory>>;

type ArtifactFactoryOptions = {
	cullAtZoomThreshold?: boolean;
	enableLocalClickHandling?: boolean;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function artifactFactory(
	artifact: RunGraphArtifact,
	{
		cullAtZoomThreshold = true,
		enableLocalClickHandling = false,
	}: ArtifactFactoryOptions = {},
) {
	const { element, render: renderArtifactNode } = await artifactNodeFactory({
		cullAtZoomThreshold,
	});

	let selected = false;
	let internalArtifact = artifact;

	element.eventMode = "static";
	element.cursor = "pointer";

	if (enableLocalClickHandling) {
		element.on("click", (event) => {
			event.stopPropagation();
			selectItem({ kind: "artifact", id: internalArtifact.id });
		});
	}

	emitter.on("itemSelected", () => {
		const isCurrentlySelected = isSelected({
			kind: "artifact",
			id: internalArtifact.id,
		});

		if (isCurrentlySelected !== selected) {
			selected = isCurrentlySelected;
			render(internalArtifact);
		}
	});

	async function render(artifact: RunGraphArtifact): Promise<void> {
		internalArtifact = artifact;

		await renderArtifactNode({
			selected,
			name: internalArtifact.key,
			...internalArtifact,
		});
	}

	function getSelected(): boolean {
		return selected;
	}

	function getDate(): Date {
		return internalArtifact.created;
	}

	function getId(): string {
		return internalArtifact.id;
	}

	return {
		isArtifact: true,
		element,
		render,
		getSelected,
		getDate,
		getId,
	};
}

export function isArtifactFactory(
	value: Record<string, unknown>,
): value is ArtifactFactory {
	return value.isArtifact === true;
}
