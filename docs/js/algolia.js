const searchClient = algoliasearch('56FX6RAQWT', 'f0c51e95953d6290a9e6632e66244682');

const search = instantsearch({
    indexName: 'demo_ecommerce',
    searchClient,
});

search.addWidgets([
    instantsearch.widgets.searchBox({
        container: '#searchbox',
    }),

    instantsearch.widgets.hits({
        container: '#hits',
    })
]);

search.start();
