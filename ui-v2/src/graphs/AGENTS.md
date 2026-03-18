# graphs

Pixi.js-based run graph rendering engine, ported from `@prefecthq/graphs`. Renders flow-run and task-run DAGs on a WebGL canvas with temporal and non-temporal layouts.

## Purpose & Scope

Provides an imperative, event-driven canvas renderer for Prefect run graphs. Consumers call `start()`/`stop()` and interact via the exported `emitter` and control functions.

Does NOT use React state, DOM diffing, or Tanstack Query — it is a self-contained rendering engine that the React component in `src/components/flow-runs/flow-run-graph/` wraps.

## Directory Structure

```
src/graphs/
├── consts.ts          # Shared sizing, z-index, culling threshold constants
├── index.ts           # Public API surface
├── factories/         # Pure functions that create/update Pixi display objects
├── models/            # TypeScript types (RunGraphData, RunGraphConfig, etc.)
├── objects/           # Stateful singletons — one per concern (nodes, viewport, scale…)
├── services/          # Supporting services (visibility culling)
├── textures/          # Precomputed Pixi textures (circles, caps, icons)
├── utilities/         # Pure layout helpers (column math, collision detection)
└── workers/           # Web Worker for off-thread layout computation
```

## Entry Points & Contracts

```ts
// Mount the graph into a DOM element
start({ stage: HTMLDivElement, config: RunGraphConfig }): void

// Tear down and release all Pixi resources
stop(): void

// Event bus — subscribe to internal lifecycle events
emitter: EventEmitter<Events>

// Control functions
layout()                          // trigger a layout pass
selectItem(selection)             // programmatically select a node
setConfig(config)
setHorizontalMode() / setVerticalMode()
setHorizontalScaleMultiplier(n)
resetHorizontalScaleMultiplier()
centerViewport()
updateViewportFromDateRange(range)
setDisabledArtifacts/Events/Edges(bool)
```

`RunGraphConfig` requires at minimum `runId`, `fetch` (async data loader), and `theme`. All other fields are optional with defaults.

## Usage Patterns

The React wrapper in `flow-run-graph/` calls `start()` on mount and `stop()` on unmount. All subsequent interaction goes through the exported functions and `emitter`:

```ts
import { start, stop, emitter, selectItem } from "@/graphs";

// mount
start({ stage: divRef.current, config });

// react to internal events
emitter.on("itemSelected", (selection) => { ... });

// unmount
stop();
```

Layout runs in a Web Worker (`workers/runGraph.worker.ts`) to keep the main thread free. Use `layoutWorkerFactory` from `workers/runGraph.ts` to create the worker.

## Anti-Patterns

- Do not import Pixi objects directly into React components — always go through the public API in `index.ts`.
- Do not call `start()` without calling `stop()` on cleanup — Pixi applications hold WebGL contexts and will leak if not destroyed.
- Do not modify `consts.ts` defaults without checking all callers; many culling thresholds are tuned for performance.

## Pitfalls

- **Two separate culling properties — do not mix them.** `Culler.shared.cull()` (the built-in pixi.js v8 viewport culler) toggles `renderable`. `VisibilityCull` (scale-threshold culling for labels/edges/icons) toggles `visible`. Custom show/hide logic must use `visible` — the viewport culler overwrites `renderable` on every ticker tick and will silently undo any `renderable` changes made elsewhere.
- **Biome and ESLint both ignore `src/graphs/`** (`biome.json` and `eslint.config.js` exclude it). Linting rules that apply elsewhere do not apply here.
- **`stop()` is wrapped in try/catch** — errors during teardown are swallowed and logged. If teardown silently fails, the Pixi application may still be running.
- **Object singletons are module-level state** — each `objects/` file holds state as a module variable. Calling `start()` twice without `stop()` will corrupt state.
- **Layout is async via Web Worker** — the `layout()` call is non-blocking; results come back via `emitter.on("layoutUpdated", ...)`.
- **Z-index ordering is load-bearing** — constants in `consts.ts` define rendering order for nested graphs; changing them will affect artifact/event/state visibility.
