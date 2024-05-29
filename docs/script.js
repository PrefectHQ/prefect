<script>
    (function() {
    if (typeof window === 'undefined') return;
    if (typeof window.signals !== 'undefined') return;
    var script = document.createElement('script');
    script.src = 'https://cdn.cr-relay.com/v1/site/5c7cdf16-fbc0-4bb8-b39e-a8c6136687b9/signals.js';
    script.async = true;
    window.signals = Object.assign(
    [],
    ['page', 'identify', 'form'].reduce(function (acc, method){
        acc[method] = function () {
            signals.push([method, arguments]);
            return signals;
        };
    return acc;
    }, { })
    );
    document.head.appendChild(script);
  })();
</script>