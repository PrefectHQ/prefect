import { Container, Point, SimpleRope } from "pixi.js";
import {
	DEFAULT_EDGE_CONTAINER_NAME,
	DEFAULT_EDGE_MINIMUM_BEZIER,
	DEFAULT_EDGE_POINTS,
} from "@/graphs/consts";
import { animationFactory } from "@/graphs/factories/animation";
import { ArrowDirection, arrowFactory } from "@/graphs/factories/arrow";
import type { Pixels } from "@/graphs/models/layout";
import { waitForCull, waitForEdgeCull } from "@/graphs/objects/culling";
import { waitForStyles } from "@/graphs/objects/styles";
import { getPixelTexture } from "@/graphs/textures/pixel";
import { repeat } from "@/graphs/utilities/repeat";

export type EdgeFactory = Awaited<ReturnType<typeof edgeFactory>>;

const arrowOffset = 8;
const edgeTargetOffset = 2;

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function edgeFactory() {
	const styles = await waitForStyles();
	const cull = await waitForCull();
	const edgeCull = await waitForEdgeCull();
	const { animate } = await animationFactory();

	const container = new Container();
	const { element: arrow, render: renderArrow } = await arrowFactory();
	const pixel = await getPixelTexture();
	const points = repeat(DEFAULT_EDGE_POINTS, () => new Point());
	const rope = new SimpleRope(pixel, points);

	let initialized = false;

	container.name = DEFAULT_EDGE_CONTAINER_NAME;

	container.addChild(arrow);
	container.addChild(rope);

	cull.addAll([arrow, rope]);

	edgeCull.add(container);

	async function render(): Promise<Container> {
		await renderArrow({
			size: 10,
			rotate: ArrowDirection.Right,
		});

		arrow.tint = styles.edgeColor;
		rope.tint = styles.edgeColor;

		return container;
	}

	async function setPosition(source: Pixels, target: Pixels): Promise<void> {
		const newPositions = getPointPositions(target);

		if (!initialized) {
			await render();
		}

		for (const [index, point] of points.entries()) {
			const { x, y } = newPositions[index];

			animate(
				point,
				{
					x,
					y,
				},
				!initialized,
			);
		}

		animate(
			container,
			{
				x: source.x,
				y: source.y,
			},
			!initialized,
		);

		animate(
			arrow,
			{
				x: target.x - arrowOffset,
				y: target.y,
			},
			!initialized,
		);

		initialized = true;
	}

	function getPointPositions({ x, y }: Pixels): Pixels[] {
		const newPoints: Pixels[] = [];
		const source: Pixels = { x: 0, y: 0 };

		const target: Pixels = { x: x - edgeTargetOffset, y };

		const sourceBezier: Pixels = {
			x: getXBezier(source.x, { source, target }),
			y: source.y,
		};

		const targetBezier: Pixels = {
			x: getXBezier(target.x, { source, target }, true),
			y: target.y,
		};

		for (const [index] of points.entries()) {
			if (index === points.length - 1) {
				newPoints[index] = target;
				continue;
			}

			const position = getPointBezierPosition(index, {
				source,
				target,
				sourceBezier,
				targetBezier,
			});

			newPoints[index] = position;
		}

		return newPoints;
	}

	return {
		element: container,
		render,
		setPosition,
	};
}

type BezierControlPoints = {
	source: Pixels;
	target: Pixels;
};

function getXBezier(
	xPos: number,
	{ source, target }: BezierControlPoints,
	upstream?: boolean,
): number {
	const bezierLength = (target.x - source.x) / 2;

	return (
		xPos +
		(bezierLength > DEFAULT_EDGE_MINIMUM_BEZIER
			? bezierLength
			: DEFAULT_EDGE_MINIMUM_BEZIER) *
			(upstream ? -1 : 1)
	);
}

type ControlPoints = {
	source: Pixels;
	target: Pixels;
	sourceBezier: Pixels;
	targetBezier: Pixels;
};

function getPointBezierPosition(
	pointOnPath: number,
	control: ControlPoints,
): Pixels {
	// https://javascript.info/bezier-curve#de-casteljau-s-algorithm
	const point = pointOnPath / DEFAULT_EDGE_POINTS;
	const { source, target, sourceBezier, targetBezier } = control;

	const cx1 = source.x + (sourceBezier.x - source.x) * point;
	const cy1 = source.y + (sourceBezier.y - source.y) * point;
	const cx2 = sourceBezier.x + (targetBezier.x - sourceBezier.x) * point;
	const cy2 = sourceBezier.y + (targetBezier.y - sourceBezier.y) * point;
	const cx3 = targetBezier.x + (target.x - targetBezier.x) * point;
	const cy3 = targetBezier.y + (target.y - targetBezier.y) * point;

	const cx4 = cx1 + (cx2 - cx1) * point;
	const cy4 = cy1 + (cy2 - cy1) * point;
	const cx5 = cx2 + (cx3 - cx2) * point;
	const cy5 = cy2 + (cy3 - cy2) * point;

	const x = cx4 + (cx5 - cx4) * point;
	const y = cy4 + (cy5 - cy4) * point;

	return { x, y };
}
