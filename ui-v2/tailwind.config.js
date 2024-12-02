/** @type {import('tailwindcss').Config} */
export default {
	darkMode: ["class"],
	content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
	theme: {
		extend: {
			borderRadius: {
				lg: "var(--radius)",
				md: "calc(var(--radius) - 2px)",
				sm: "calc(var(--radius) - 4px)",
			},
			colors: {
				background: "hsl(var(--background))",
				foreground: "hsl(var(--foreground))",
				card: {
					DEFAULT: "hsl(var(--card))",
					foreground: "hsl(var(--card-foreground))",
				},
				popover: {
					DEFAULT: "hsl(var(--popover))",
					foreground: "hsl(var(--popover-foreground))",
				},
				primary: {
					DEFAULT: "hsl(var(--primary))",
					foreground: "hsl(var(--primary-foreground))",
				},
				secondary: {
					DEFAULT: "hsl(var(--secondary))",
					foreground: "hsl(var(--secondary-foreground))",
				},
				muted: {
					DEFAULT: "hsl(var(--muted))",
					foreground: "hsl(var(--muted-foreground))",
				},
				accent: {
					DEFAULT: "hsl(var(--accent))",
					foreground: "hsl(var(--accent-foreground))",
				},
				destructive: {
					DEFAULT: "hsl(var(--destructive))",
					foreground: "hsl(var(--destructive-foreground))",
				},
				border: "hsl(var(--border))",
				input: "hsl(var(--input))",
				ring: "hsl(var(--ring))",
				chart: {
					1: "hsl(var(--chart-1))",
					2: "hsl(var(--chart-2))",
					3: "hsl(var(--chart-3))",
					4: "hsl(var(--chart-4))",
					5: "hsl(var(--chart-5))",
				},
				sidebar: {
					DEFAULT: "hsl(var(--sidebar-background))",
					foreground: "hsl(var(--sidebar-foreground))",
					primary: "hsl(var(--sidebar-primary))",
					"primary-foreground": "hsl(var(--sidebar-primary-foreground))",
					accent: "hsl(var(--sidebar-accent))",
					"accent-foreground": "hsl(var(--sidebar-accent-foreground))",
					border: "hsl(var(--sidebar-border))",
					ring: "hsl(var(--sidebar-ring))",
				},
				state: {
					completed: {
						DEFAULT: "hsl(var(--state-completed))",
						foreground: "hsl(var(--state-completed-foreground))",
						badge: {
							DEFAULT: "hsl(var(--state-completed-badge))",
							foreground: "hsl(var(--state-completed-badge-foreground))",
						},
					},
					failed: {
						DEFAULT: "hsl(var(--state-failed))",
						foreground: "hsl(var(--state-failed-foreground))",
						badge: {
							DEFAULT: "hsl(var(--state-failed-badge))",
							foreground: "hsl(var(--state-failed-badge-foreground))",
						},
					},
					running: {
						DEFAULT: "hsl(var(--state-running))",
						foreground: "hsl(var(--state-running-foreground))",
						badge: {
							DEFAULT: "hsl(var(--state-running-badge))",
							foreground: "hsl(var(--state-running-badge-foreground))",
						},
					},
					pending: {
						DEFAULT: "hsl(var(--state-pending))",
						foreground: "hsl(var(--state-pending-foreground))",
						badge: {
							DEFAULT: "hsl(var(--state-pending-badge))",
							foreground: "hsl(var(--state-pending-badge-foreground))",
						},
					},
					paused: {
						DEFAULT: "hsl(var(--state-paused))",
						foreground: "hsl(var(--state-paused-foreground))",
						badge: {
							DEFAULT: "hsl(var(--state-paused-badge))",
							foreground: "hsl(var(--state-paused-badge-foreground))",
						},
					},
					scheduled: {
						DEFAULT: "hsl(var(--state-scheduled))",
						foreground: "hsl(var(--state-scheduled-foreground))",
						badge: {
							DEFAULT: "hsl(var(--state-scheduled-badge))",
							foreground: "hsl(var(--state-scheduled-badge-foreground))",
						},
					},
					cancelled: {
						DEFAULT: "hsl(var(--state-cancelled))",
						foreground: "hsl(var(--state-cancelled-foreground))",
						badge: {
							DEFAULT: "hsl(var(--state-cancelled-badge))",
							foreground: "hsl(var(--state-cancelled-badge-foreground))",
						},
					},
					cancelling: {
						DEFAULT: "hsl(var(--state-cancelling))",
						foreground: "hsl(var(--state-cancelling-foreground))",
						badge: {
							DEFAULT: "hsl(var(--state-cancelling-badge))",
							foreground: "hsl(var(--state-cancelling-badge-foreground))",
						},
					},
					crashed: {
						DEFAULT: "hsl(var(--state-crashed))",
						foreground: "hsl(var(--state-crashed-foreground))",
						badge: {
							DEFAULT: "hsl(var(--state-crashed-badge))",
							foreground: "hsl(var(--state-crashed-badge-foreground))",
						},
					},
				},
			},
		},
	},
	plugins: [require("tailwindcss-animate")],
};
