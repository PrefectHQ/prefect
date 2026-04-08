# Auth

Manages authentication state for the Prefect UI, including detecting whether auth is required, validating stored credentials, and exposing login/logout actions.

## Purpose & Scope

Provides the `AuthProvider` component and `useAuth` hook that gate access to the UI when the server requires authentication. Handles credential storage, validation, and session invalidation.

Does NOT implement the login form UI — that lives in `src/routes/`. Does NOT make authenticated API requests — it only validates credentials via `/admin/version`.

## Entry Points & Contracts

- **`AuthProvider`** — wrap the app root to enable auth. Reads `/ui-settings` on mount to determine if auth is required.
- **`useAuth()`** — throws if called outside `AuthProvider`. Use for components that are always rendered inside the provider.
- **`useAuthSafe()`** — returns `null` if called outside `AuthProvider`. Use in components that may render outside the provider (e.g., tests, Storybook).

## Key Behaviors

- Auth is required when `settings.auth` is any truthy value (not only `"BASIC"`). This means custom auth modes also trigger the auth gate.
- Credentials are stored as a base64-encoded password in `localStorage` under the key `"prefect-password"`.
- On init, stored credentials are validated against `/admin/version` with a `Basic` auth header. Invalid credentials are cleared immediately.
- Session invalidation is event-driven: API middleware dispatches a `"auth:unauthorized"` window event, which `AuthProvider` listens for to reset `isAuthenticated` to `false` without a page reload.

## Anti-Patterns

- Do not check `settings.auth === "BASIC"` to detect auth requirements — any truthy `auth` value means auth is required.
- Do not call `useAuth()` in components that might render in Storybook or tests outside a provider — use `useAuthSafe()` instead.
