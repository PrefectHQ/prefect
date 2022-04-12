import { EmpiricalPolicy } from '@/models/EmpiricalPolicy'
import { IEmpiricalPolicyResponse } from '@/models/IEmpiricalPolicyResponse'
import { MapFunction } from '@/services/Mapper'

export const mapIEmpiricalPolicyResponseToEmpiricalPolicy: MapFunction<IEmpiricalPolicyResponse, EmpiricalPolicy> = function(source: IEmpiricalPolicyResponse): EmpiricalPolicy {
  return new EmpiricalPolicy({
    maxRetries: source.max_retries,
    retryDelaySeconds: source.retry_delay_seconds,
  })
}

export const mapEmpiricalPolicyToIEmpiricalPolicyResponse: MapFunction<EmpiricalPolicy, IEmpiricalPolicyResponse> = function(source: EmpiricalPolicy): IEmpiricalPolicyResponse {
  return {
    'max_retries': source.maxRetries,
    'retry_delay_seconds': source.retryDelaySeconds,
  }
}