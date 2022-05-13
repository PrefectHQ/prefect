## How to use the mapper service ##

| Argument | Type | Description |
| -- | -- | -- |
| source | `string` | String representation of the source type. Available options are predefined, available through intellisense, and enforce what types are allowed to be passed as "value" argument. Instructions for adding additional options below. |
| value | `T` |  Source type provided by "source" argument narrows the available `MapperFunction`, `T` will equal the argument of whatever `MapperFunction` claims to be responsible for the given "source" argument.  |
| destination |  `string` | String representation of the desired destination type. Available options are predefined, available through intellisense, and narrowed to only the available destinations for the given "source" argument | 

example converting `Date` => `string`
```ts
import { mapper } from '@prefecthq/orion-design'

const mySourceValue = new Date()
const myDestinationValue = mapper.map('Date', mySourceValue, 'string')

// "2022-04-07T19:28:24.264Z"
```

## Adding new Mapper profiles ##
In order for the mapper to know how to map from `BlueType` to `RedType`, we need to define a [`MapperFunction`](https://github.com/PrefectHQ/orion/blob/d8f5439590504de2acdf78639281ec6f58530f7a/orion-ui/packages/orion-design/src/services/Mapper.ts#L51).
```ts 
import { MapFunction } from '@/services/Mapper'

export const mapBlueTypeToRedType: MapFunction<BlueType, RedType> = function(source: BlueType): RedType {
  ...
}
```
- the name of this const doesn't _actually_ matter, but `'map${SOURCE_TYPE}To${DEST_TYPE}'` is the standard
- this function will be bound to the singleton `mapper`, so when within the function, `this` will be an instance of the same mapper. This is extremely useful for nesting mappers. Think of models such as `FlowRun`, which has a property `state`. Because we have a mapper for state, you can simply use `this.map('IStateResponse', source.state, 'IState')` for that property. Or a simpler example would be going to/from Date/string within _most_ map functions. Please avoid infinite nesting 🙃 
- because of the point above, it's important to define your function as I've done above and not as an arrow function as you would lose the context.
- the name of this file doesn't _actually_ matter, but camel case of the destination type is the standard, which in this case is `src/maps/redType.ts`.

You're not done yet, just creating this map function does NOT make it available to `mapper.map`. The next step is to add your map function to that [predefined index](https://github.com/PrefectHQ/orion/blob/d8f5439590504de2acdf78639281ec6f58530f7a/orion-ui/packages/orion-design/src/maps/index.ts) I mentioned above.

```ts
import { mapBlueTypeToRedType } from './redType'

export const maps = {
  ...
  BlueType: {
    RedType: mapBlueTypeToRedType
  }
  ...
}
```

the format for this object is `{ source: { destination: mapFunction } }`

That's it  🙌  now you can use `mapper.map('BlueType', eiffel65, 'RedType')`

## Mapping Array or Record types ##
Mapper is happy to accept arrays or objects!

```ts
const ex1 = mapper.map('string', '100', 'number') // 100
const ex2 = mapper.map('string', ['100'], 'number') // [100]
const ex3 = mapper.map('string', ['100', '101'], 'number') // [100, 101]
const ex4 = mapper.mapEntries('string', { foo: '100', bar: '101' }, 'number') // { foo: 100, bar: 101 }
```

## Future enhancements ##
- MapFunctions could be async? In the case where the source has `flow_id:string`, and destination has `flow:Flow` you'd need to run to the server to get the value.
