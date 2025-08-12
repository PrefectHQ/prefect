import type { Meta, StoryObj } from "@storybook/react";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { PageHeading } from "./page-heading";

const meta: Meta<typeof PageHeading> = {
	title: "UI/PageHeading",
	component: PageHeading,
	parameters: {
		layout: "padded",
	},
};

export default meta;
type Story = StoryObj<typeof PageHeading>;

export const Default: Story = {
	args: {
		title: "Page Title",
	},
};

export const WithSubtitle: Story = {
	args: {
		title: "Page Title",
		subtitle: "This is a subtitle providing additional context",
	},
};

export const WithBreadcrumbs: Story = {
	args: {
		title: "Page Title",
		breadcrumbs: (
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem>
						<span className="hover:text-foreground transition-colors cursor-pointer">Home</span>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					<BreadcrumbItem>
						<span className="hover:text-foreground transition-colors cursor-pointer">Section</span>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					<BreadcrumbItem>
						<BreadcrumbPage>Current Page</BreadcrumbPage>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		),
	},
};

export const WithActions: Story = {
	args: {
		title: "Page Title",
		actions: (
			<>
				<Button variant="outline" size="sm">
					Secondary Action
				</Button>
				<Button size="sm">Primary Action</Button>
			</>
		),
	},
};

export const Complete: Story = {
	args: {
		title: "Work Pool Details",
		subtitle: "Manage and configure your work pool settings",
		breadcrumbs: (
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem>
						<span className="hover:text-foreground transition-colors cursor-pointer">Work Pools</span>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					<BreadcrumbItem>
						<BreadcrumbPage>my-work-pool</BreadcrumbPage>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		),
		actions: (
			<>
				<Button variant="outline" size="sm">
					Edit
				</Button>
				<Button variant="destructive" size="sm">
					Delete
				</Button>
			</>
		),
	},
};
