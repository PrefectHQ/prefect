// Mintlify renders every external link it generates (content links, navbar,
// footer socials) as `<a target="_blank" rel="noreferrer">`. That `noreferrer`
// token strips the Referer header, so prefect.io and every other destination
// see docs traffic as "direct" in their analytics.
//
// This script removes the `noreferrer` token from a link right before the
// browser follows it. The site's `Referrer-Policy: strict-origin-when-cross-origin`
// header still applies, so destinations only receive the docs origin, never
// the full page URL. `noopener` is kept (or added) so the opened tab cannot
// reach back into this window.
;(function () {
    if (typeof window === 'undefined') return

    function allowReferrer(event) {
        const target = event.target
        if (!target || typeof target.closest !== 'function') return

        const anchor = target.closest('a[rel~="noreferrer"]')
        if (!anchor) return

        const tokens = (anchor.getAttribute('rel') || '')
            .split(/\s+/)
            .filter((token) => token && token !== 'noreferrer')

        if (!tokens.includes('noopener')) {
            tokens.push('noopener')
        }

        anchor.setAttribute('rel', tokens.join(' '))
    }

    const events = ['pointerdown', 'mousedown', 'click', 'auxclick', 'keydown']

    events.forEach((name) => {
        document.addEventListener(name, allowReferrer, true)
    })
})()
