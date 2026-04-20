/**
 * Full-page loading component with animated Prefect logo.
 * Use this for route-level loading states like auth initialization.
 */
export function PrefectLoading() {
	return (
		<div className="flex h-screen w-screen items-center justify-center">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 76 76"
				className="size-16 animate-pulse text-foreground"
				aria-label="Loading"
			>
				<title>Loading</title>
				<path
					fill="currentColor"
					fillRule="evenodd"
					d="M15.89 15.07 38 26.543v22.935l22.104-11.47.007.004V15.068l-.003.001L38 3.598z"
					clipRule="evenodd"
				/>
				<path
					fill="currentColor"
					fillRule="evenodd"
					d="M15.89 15.07 38 26.543v22.935l22.104-11.47.007.004V15.068l-.003.001L38 3.598z"
					clipRule="evenodd"
				/>
				<path
					fill="currentColor"
					fillRule="evenodd"
					d="M37.987 49.464 15.89 38v22.944l.013-.006L38 72.402V49.457z"
					clipRule="evenodd"
				/>
			</svg>
		</div>
	);
}
