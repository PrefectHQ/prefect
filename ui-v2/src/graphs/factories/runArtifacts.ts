import throttle from "lodash.throttle";
import { Container } from "pixi.js";
import { DEFAULT_ROOT_COLLISION_THROTTLE } from "@/graphs/consts";
import type { ArtifactFactory } from "@/graphs/factories/artifact";
import type { ArtifactClusterFactory } from "@/graphs/factories/artifactCluster";
import { flowRunArtifactFactory } from "@/graphs/factories/flowRunArtifact";
import { nodeFlowRunArtifactFactory } from "@/graphs/factories/nodeFlowRunArtifact";
import type { RunGraphArtifact } from "@/graphs/models";
import { layout, waitForSettings } from "@/graphs/objects/settings";
import { clusterHorizontalCollisions } from "@/graphs/utilities/detectHorizontalCollisions";

type RunEventsFactoryProps = {
	isRoot?: boolean;
	parentStartDate?: Date;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function runArtifactsFactory({
	isRoot,
	parentStartDate,
}: RunEventsFactoryProps = {}) {
	const settings = await waitForSettings();

	const artifacts: Map<string, ArtifactFactory> = new Map();
	const artifactCreationPromises = new Map<string, Promise<void>>();
	const clusterNodes: ArtifactClusterFactory[] = [];
	let availableClusterNodes: ArtifactClusterFactory[] = [];

	const container = new Container();
	let internalData: RunGraphArtifact[] | null = null;

	async function render(newData?: RunGraphArtifact[]): Promise<void> {
		if (newData) {
			internalData = newData;
		}

		if (!internalData) {
			return;
		}

		const promises: Promise<void>[] = [];

		for (const artifact of internalData) {
			promises.push(createArtifact(artifact));
		}

		await Promise.all(promises);

		update();
	}

	async function createArtifact(artifact: RunGraphArtifact): Promise<void> {
		if (artifacts.has(artifact.id)) {
			return artifacts.get(artifact.id)!.render(artifact);
		}

		if (artifactCreationPromises.has(artifact.id)) {
			await artifactCreationPromises.get(artifact.id);
		}

		const artifactCreationPromise = (async () => {
			const factory = isRoot
				? await flowRunArtifactFactory({ type: "artifact", artifact })
				: await nodeFlowRunArtifactFactory({
						type: "artifact",
						artifact,
						parentStartDate,
					});

			artifacts.set(artifact.id, factory);

			container.addChild(factory.element);
		})();

		artifactCreationPromises.set(artifact.id, artifactCreationPromise);

		await artifactCreationPromise;

		artifactCreationPromises.delete(artifact.id);

		return artifacts.get(artifact.id)!.render(artifact);
	}

	function update(): void {
		if (settings.disableArtifacts || !layout.isTemporal()) {
			return;
		}

		if (!layout.isTemporal()) {
			container.visible = false;
			return;
		}

		container.visible = true;
		container.position.x = 0;
		checkLayout();
	}

	const checkLayout = throttle(async () => {
		availableClusterNodes = [...clusterNodes];

		await clusterHorizontalCollisions({
			items: artifacts,
			createCluster,
		});

		for (const cluster of availableClusterNodes) {
			cluster.render();
		}
	}, DEFAULT_ROOT_COLLISION_THROTTLE);

	async function createCluster(): Promise<ArtifactClusterFactory> {
		if (availableClusterNodes.length > 0) {
			return availableClusterNodes.pop()!;
		}

		const newCluster = isRoot
			? await flowRunArtifactFactory({ type: "cluster" })
			: await nodeFlowRunArtifactFactory({ type: "cluster", parentStartDate });

		container!.addChild(newCluster.element);
		clusterNodes.push(newCluster);

		return newCluster;
	}

	return {
		element: container,
		render,
		update,
	};
}
