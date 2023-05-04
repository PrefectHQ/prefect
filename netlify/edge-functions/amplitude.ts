export default async (request: Request): Promise<Response> => {
    if (request.method !== 'POST') {
      return new Response(null, {
        status: 400,
      })
    }
  
    const target = 'https://api2.amplitude.com/2/httpapi'
    const proxyRequest = new Request(target, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    })
  
    const filteredHeaders = new Headers()
    const response = await fetch(proxyRequest)
    response.headers.forEach((value, header) => {
      // Drop unnecessary headers from response
      if (header.startsWith('access-control-')) {
        return
      }
  
      filteredHeaders.append(header, value)
    })
  
    const filteredResponse = new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: filteredHeaders,
    })
    return filteredResponse
  }
