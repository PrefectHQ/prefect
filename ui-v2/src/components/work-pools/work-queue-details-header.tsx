import type { WorkQueue } from "@/api/work-queues";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { StatusBadge } from "@/components/ui/status-badge";
import { Link } from "@tanstack/react-router";

export type WorkQueueDetailsHeaderProps = {
  workPoolName: string;
  workQueue: WorkQueue;
};

export const WorkQueueDetailsHeader = ({ workPoolName, workQueue }: WorkQueueDetailsHeaderProps) => {
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
          <BreadcrumbItem>
            <BreadcrumbLink
              to="/work-pools/work-pool/$workPoolName"
              params={{ workPoolName }}
              className="text-xl font-semibold"
            >
              {workPoolName}
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem className="text-xl font-semibold">
            <BreadcrumbPage>{workQueue.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      {workQueue.status && <StatusBadge status={workQueue.status} />}
    </div>
  );
};
