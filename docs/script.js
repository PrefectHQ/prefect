function loadScript(src, onload) {
    if (typeof window === 'undefined') return
    if (typeof src !== 'string') {
        console.error('src must be a string')
        return
    }

    const script = document.createElement('script')
    script.src = src
    script.async = true

    if (typeof onload === 'function') {
        script.addEventListener('load', onload)
    }

    document.head.appendChild(script)
    return script
}

const UNIFY_PAGE_PATHS = new Set([
    '/v3/how-to-guides/cloud/manage-users/configure-sso',
    '/v3/how-to-guides/cloud/manage-users/index',
    '/v3/how-to-guides/cloud/manage-users/manage-roles',
    '/v3/how-to-guides/cloud/manage-users/object-access-control-lists',
    '/v3/how-to-guides/cloud/manage-users/secure-access-by-private-link',
    '/v3/api-ref/python/prefect-cli-cloud-ip_allowlist',
])

const UNIFY_API_KEY = 'wk_SBvJ4jyD_wRgPAHCNJb89seVmREhcj2NspRpxAywi'
const UNIFY_SCRIPT_ID = 'unifytag'
const UNIFY_SCRIPT_SRC = 'https://tag.unifyintent.com/v1/Rj9KrQqMhyYcU5qfJtVszE/script.js'

let unifyTagLoaded = false
let currentUnifyPagePath = null

function normalizePathname(pathname) {
    if (pathname === '/') return pathname
    return pathname.replace(/\/+$/, '')
}

function isUnifyPage(pathname) {
    return UNIFY_PAGE_PATHS.has(normalizePathname(pathname))
}

function initializeUnifyQueue() {
    const methods = ['identify', 'page', 'startAutoPage', 'stopAutoPage', 'startAutoIdentify', 'stopAutoIdentify']

    function createQueue(queue) {
        return Object.assign([], methods.reduce(function (acc, method) {
            acc[method] = function () {
                queue.push([method, [].slice.call(arguments)])
                return queue
            }
            return acc
        }, {}))
    }

    window.unify = window.unify || createQueue(window.unify || [])
    window.unifyBrowser = window.unifyBrowser || createQueue(window.unifyBrowser || [])
}

function ensureUnifyTagLoaded() {
    if (unifyTagLoaded || document.getElementById(UNIFY_SCRIPT_ID)) {
        unifyTagLoaded = true
        return
    }

    initializeUnifyQueue()
    window.unify.stopAutoPage()
    window.unify.stopAutoIdentify()

    const script = document.createElement('script')
    script.async = true
    script.id = UNIFY_SCRIPT_ID
    script.src = UNIFY_SCRIPT_SRC
    script.setAttribute('data-api-key', UNIFY_API_KEY)

    ;(document.body || document.head).appendChild(script)
    unifyTagLoaded = true
}

function syncUnifyTag() {
    const pathname = normalizePathname(window.location.pathname)
    const isTargetPage = isUnifyPage(pathname)

    if (!isTargetPage) {
        if (unifyTagLoaded && currentUnifyPagePath !== null) {
            window.unify.stopAutoIdentify()
            currentUnifyPagePath = null
        }
        return
    }

    ensureUnifyTagLoaded()
    window.unify.startAutoIdentify()

    if (currentUnifyPagePath !== pathname) {
        window.unify.page()
        currentUnifyPagePath = pathname
    }
}

function observeRouteChanges(callback) {
    const onRouteChange = () => {
        window.setTimeout(callback, 0)
    }

    const { pushState, replaceState } = window.history

    window.history.pushState = function () {
        const result = pushState.apply(this, arguments)
        onRouteChange()
        return result
    }

    window.history.replaceState = function () {
        const result = replaceState.apply(this, arguments)
        onRouteChange()
        return result
    }

    window.addEventListener('popstate', onRouteChange)
    window.addEventListener('hashchange', onRouteChange)
    callback()
}

function loadCommonRoom() {
    const url = 'https://cdn.cr-relay.com/v1/site/5c7cdf16-fbc0-4bb8-b39e-a8c6136687b9/signals.js'
    const init = () => {
        window.signals = Object.assign(
            [],
            ['page', 'identify', 'form'].reduce(function (acc, method) {
                acc[method] = function () {
                    signals.push([method, arguments])
                    return signals
                }
                return acc
            }, {})
        )
    }

    loadScript(url, init)
}

function loadAmplitude() {
    // TODO: Move the key and url to an env var in mintlify
    const amplitudeKey = 'c97dd2acbf306ab7bf54aca0aeb7ffa1'
    const amplitudeUrl = 'https://api2.amplitude.com/2/httpapi'

    const addUrl = (event) => {
        const deviceId = amplitude.getDeviceId()
        const { href = '' } = event.target
        const url = new URL(href)
        url.searchParams.set('deviceId', deviceId)
        event.target.href = url.toString()
    }

    const removeUrl = (event) => {
        const { href = '' } = event.target
        const url = new URL(href)
        url.searchParams.delete('deviceId')
        event.target.href = url.toString()
    }

    const urls = [
        'https://app.prefect.cloud',
    ]

    const selector = urls.map((url) => `a[href^="${url}"]`).join(',')

    const addDeviceIdToAppLinks = () => {
        const elements = document.querySelectorAll(selector)

        elements.forEach((element) => {
            element.addEventListener('mouseenter', addUrl)
            element.addEventListener('mouseleave', removeUrl)
            element.addEventListener('focus', addUrl)
            element.addEventListener('blur', removeUrl)
            element.addEventListener('touchstart', addUrl)
            element.addEventListener('touchend', removeUrl)
        })
    }

    function trackPageView() {
        amplitude.track(
            'Page View: Docs New',
            {
                'url': window.href,
                'title': document.title,
                'referrer': document.referrer,
                'path': window.location.pathname,
                'source': 'docs',
                'source_detail': '3.x'
            }
        )
    }

    const init = () => {
        amplitude.init(amplitudeKey, undefined, {
            useBatch: true,
            serverUrl: amplitudeUrl,
            attribution: {
                disabled: false,
                trackNewCampaigns: true,
                trackPageViews: true,
                resetSessionOnNewCampaign: true,
            },
            defaultTracking: {
                pageViews: {
                    trackOn: function () { return true },
                    eventType: "Page View: Docs New",
                    trackHistoryChanges: "all",
                },
                sessions: false,
                formInteractions: true,
                fileDownloads: true,
            },
        })

        setTimeout(addDeviceIdToAppLinks)
        setTimeout(trackPageView)
    }

    const url = 'https://cdn.amplitude.com/libs/analytics-browser-2.8.1-min.js.gz'
    loadScript(url, init)
}

function loadReo() {
    var e, t, n; e = "85cf6f7792f05b5", t = function () { Reo.init({ clientID: "85cf6f7792f05b5" }) }, (n = document.createElement("script")).src = "https://static.reo.dev/" + e + "/reo.js", n.async = !0, n.onload = t, document.head.appendChild(n)
}


loadCommonRoom()
loadAmplitude()
loadReo()
observeRouteChanges(syncUnifyTag)
