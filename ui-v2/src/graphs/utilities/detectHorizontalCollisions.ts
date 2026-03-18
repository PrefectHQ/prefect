import type { Container } from "pixi.js";

type ItemFactory = {
	element: Container;
	getId: () => string;
	getDate: () => Date;
} & Record<string, unknown>;

type ClusterFactory = {
	element: Container;
	getIds: () => string[];
	getDate: () => Date | null;
	render: (props: { ids: string[]; date: Date }) => void;
} & Record<string, unknown>;

export function itemIsClusterFactory(
	item: ItemFactory | ClusterFactory,
): item is ClusterFactory {
	return "getIds" in item;
}

type ClusterHorizontalCollisionsProps = {
	items: Map<string, ItemFactory | ClusterFactory>;
	createCluster: () => Promise<ClusterFactory>;
};

export async function clusterHorizontalCollisions({
	items,
	createCluster,
}: ClusterHorizontalCollisionsProps): Promise<void> {
	const visibleItems = [...items.values()].sort(
		(itemA, itemB) => itemA.element.x - itemB.element.x,
	);

	async function checkCollisions(startIndex?: number): Promise<void> {
		let xCheckpoint;
		let prevIndex: number | null = null;
		let collisionIndex: number | null = null;

		for (let i = startIndex ?? 0; i < visibleItems.length; i++) {
			const item = visibleItems[i];
			const itemX = item.element.x;
			item.element.visible = true;

			if (prevIndex !== null && xCheckpoint && itemX < xCheckpoint) {
				collisionIndex = i;
				break;
			}

			prevIndex = i;
			xCheckpoint = itemX + item.element.width;
		}

		if (collisionIndex !== null && prevIndex !== null) {
			const prevItem = visibleItems[prevIndex];
			const collisionItem = visibleItems[collisionIndex];

			prevItem.element.visible = false;
			collisionItem.element.visible = false;

			const cluster = await clusterItems(prevItem, collisionItem);

			if (cluster) {
				visibleItems.splice(prevIndex, 1, cluster);
				visibleItems.splice(collisionIndex, 1);
			}

			checkCollisions(prevIndex);
		}
	}

	async function clusterItems(
		prevItem: ItemFactory | ClusterFactory,
		currentItem: ItemFactory | ClusterFactory,
	): Promise<ItemFactory | ClusterFactory | null> {
		const prevDate = prevItem.getDate();
		const currentDate = currentItem.getDate();
		const prevIds = itemIsClusterFactory(prevItem)
			? prevItem.getIds()
			: [prevItem.getId()];
		const currentIds = itemIsClusterFactory(currentItem)
			? currentItem.getIds()
			: [currentItem.getId()];

		if (!prevDate || !currentDate) {
			console.error("flowRunArtifacts: visible item is missing date");
			return null;
		}

		let clusterNode: ClusterFactory;

		if (itemIsClusterFactory(prevItem)) {
			clusterNode = prevItem;
		} else if (itemIsClusterFactory(currentItem)) {
			clusterNode = currentItem;
		} else {
			clusterNode = await createCluster();
		}

		const ids = [...prevIds, ...currentIds];
		const date = getCenteredDate(ids);

		await clusterNode.render({ ids, date });

		return clusterNode;
	}

	function getCenteredDate(ids: string[]): Date {
		const times = ids.reduce((acc: number[], id) => {
			const item = items.get(id);
			const itemDate = item?.getDate();

			if (itemDate) {
				acc.push(itemDate.getTime());
			}

			return acc;
		}, []);

		const min = Math.min(...times);
		const max = Math.max(...times);

		return new Date((min + max) / 2);
	}

	await checkCollisions();
}
