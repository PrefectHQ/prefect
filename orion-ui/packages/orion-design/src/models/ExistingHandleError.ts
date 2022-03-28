import { AxiosError } from 'axios'
import { Require } from '@/types/utilities'

export type ExistingHandleError = {
  detail: string,
}

export function isExistingHandleError(error: AxiosError): error is Require<AxiosError<ExistingHandleError>, 'response'> {
  return error.response?.data.detail !== undefined
}
