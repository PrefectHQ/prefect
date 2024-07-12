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
