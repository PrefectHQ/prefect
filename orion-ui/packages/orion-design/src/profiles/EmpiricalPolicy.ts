import { EmpiricalPolicy } from '@/models/EmpiricalPolicy'
import { IEmpiricalPolicyResponse } from '@/models/IEmpiricalPolicyResponse'
import { Profile } from '@/services/Translate'

export const empiricalPolicyProfile: Profile<IEmpiricalPolicyResponse, EmpiricalPolicy> = {
  toDestination(source) {
    return new EmpiricalPolicy({
      maxRetries: source.max_retries,
      retryDelaySeconds: source.retry_delay_seconds,
    })
  },
  toSource(destination) {
    return {
      'max_retries': destination.maxRetries,
      'retry_delay_seconds': destination.retryDelaySeconds,
    }
  },
}