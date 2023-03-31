function isCdnRequest(path: string): boolean {
    if (path.startsWith('/v1/projects') ||
        path.startsWith('/analytics.js/v1') ||
        path.startsWith('/next-integrations') ||
        path.startsWith('/analytics-next/bundles')) {
        return true
    }
    return false
}
  
export default async (request: Request): Promise<Response> => {
    const PREFIX = '/segment'
    const url = new URL(request.url)
    let path = url.pathname
    if (path.startsWith(PREFIX)) {
        path = path.slice(PREFIX.length)
    }
  
    // Mitigation for possible path traversal attacks
    if (path.includes('/./') || path.includes('/../')) {
        return new Response(null, {
            status: 400,
        })
    }
  
    const cdnRequest = isCdnRequest(path)
    const target = cdnRequest ? 'https://cdn.segment.com' : 'https://api.segment.io'
    // Allow GET requests to CDN
    // Allow POST requests to API
    // Block other request methods
    if (cdnRequest && request.method !== 'GET' ||
        !cdnRequest && request.method !== 'POST') {
        return new Response(null, {
            status: 400,
        })
    }
  
    const proxyRequest = new Request(new URL(path, target), {
        method: request.method,
        headers: request.headers,
        body: request.body,
    })
  
    const filteredHeaders = new Headers()
    const response = await fetch(proxyRequest)
    response.headers.forEach((value, header) => {
        // Drop unnecessary headers from response
        if (header.startsWith('x-amz-') ||
            header === 'x-cache' ||
            header.startsWith('access-control-')) {
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
