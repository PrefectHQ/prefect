import { Container } from "pixi.js";
import {
	type FlowRunStateFactory,
	flowRunStateFactory,
} from "@/graphs/factories/flowRunState";
import {
	isNodeFlowRunStateFactory,
	type NodeFlowRunStateFactory,
	type NodeFlowRunStateFactoryRenderProps,
	nodeFlowRunStateFactory,
} from "@/graphs/factories/nodeFlowRunState";
import type { RunGraphStateEvent } from "@/graphs/models/states";

type FlowRunStatesFactoryProps = {
	isRoot?: boolean;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function runStatesFactory({ isRoot }: FlowRunStatesFactoryProps = {}) {
	const element = new Container();

	const states = new Map<
		string,
		FlowRunStateFactory | NodeFlowRunStateFactory
	>();
	const stateCreationPromises = new Map<string, Promise<void>>();
	let internalData: RunGraphStateEvent[] | null = null;

	async function render(
		newStateData?: RunGraphStateEvent[],
		nodesStateOptions?: NodeFlowRunStateFactoryRenderProps,
	): Promise<void> {
		if (newStateData) {
			internalData = newStateData;
		}

		if (!internalData) {
			return;
		}

		const promises: Promise<void>[] = [];

		for (let i = 0; i < internalData.length; i++) {
			promises.push(createState(internalData[i], i, nodesStateOptions));
		}

		await Promise.all(promises);
	}

	async function createState(
		state: RunGraphStateEvent,
		currIndex: number,
		nodesStateOptions?: NodeFlowRunStateFactoryRenderProps,
	): Promise<void> {
		const nextState =
			internalData &&
			internalData.length >= currIndex + 1 &&
			internalData[currIndex + 1];
		const end = nextState ? nextState.timestamp : undefined;

		let factory;

		// Since the render function can be called rapidly when subflows are expanded and
		// resizing occurs, a locking mechanism is used to prevent multiple render calls
		// from creating the same state factory
		if (stateCreationPromises.has(state.id)) {
			await stateCreationPromises.get(state.id);
		}

		if (states.has(state.id)) {
			factory = states.get(state.id)!;
		} else {
			const stateCreationPromise = (async () => {
				const newFactory = isRoot
					? await flowRunStateFactory(state)
					: await nodeFlowRunStateFactory(state);

				states.set(state.id, newFactory);

				element.addChild(newFactory.element);
			})();

			stateCreationPromises.set(state.id, stateCreationPromise);

			await stateCreationPromise;

			stateCreationPromises.delete(state.id);

			factory = states.get(state.id)!;
		}

		if (isNodeFlowRunStateFactory(factory)) {
			await factory.render({ end, ...nodesStateOptions });
		} else {
			await factory.render(end ? { end } : undefined);
		}
	}

	return {
		element,
		render,
	};
}
