const { autocomplete, getAlgoliaResults } = window['@algolia/autocomplete-js'];

const searchClient = algoliasearch('56FX6RAQWT', 'a44396335bea82d8190edeb3f690b61b');

function convertUrlToCurrentContextUrl(url) {
    // Parse the input URL
    const parsedUrl = new URL(url);

    // Return the reconstructed URL with the current base
    return `${parsedUrl.pathname.replace(/\/latest|latest/, '')}${parsedUrl.search}${parsedUrl.hash}`;
}

const itemTemplate = ({ item, components, html }) => {
    const title = Object.values(item.hierarchy).filter((lvl) => lvl !== null).join(' > ')
    console.log({ item })
    return html`
<a href="${convertUrlToCurrentContextUrl(item.url)}" class="md-nav__link">
    ${title}
</a>
    `
}

const prefectioSource = ({ query }) => {
    return {
        sourceId: 'prefect_docs',
        getItems() {
            return getAlgoliaResults({
                searchClient,
                queries: [
                    {
                        indexName: 'prefectio',
                        query,
                        params: {
                            hitsPerPage: 10,
                        },
                    },
                ],
            })
        },
        templates: {
            item: itemTemplate
        }
    }
}

const algoliaSources = (res) => {
    return [
        prefectioSource(res)
    ]
}

autocomplete({
    placeholder: 'Search our docs',
    container: '#autocomplete',
    getSources: algoliaSources
});

