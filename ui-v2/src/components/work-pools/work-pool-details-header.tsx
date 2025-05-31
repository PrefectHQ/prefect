import type { WorkPool } from "@/api/work-pools";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { WorkPoolPauseResumeToggle } from "./work-pool-card/components/work-pool-pause-resume-toggle";
import { Link } from "@tanstack/react-router";

export type WorkPoolDetailsHeaderProps = {
  workPool: WorkPool;
};

export const WorkPoolDetailsHeader = ({ workPool }: WorkPoolDetailsHeaderProps) => {
  return (
    <div className="flex items-center justify-between">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink to="/work-pools" className="text-xl font-semibold">
              Work pools
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem className="text-xl font-semibold">
            <BreadcrumbPage>{workPool.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <WorkPoolPauseResumeToggle workPool={workPool} />
    </div>
  );
};
