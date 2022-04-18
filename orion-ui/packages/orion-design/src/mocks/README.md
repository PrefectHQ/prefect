## How to use the mocker service ##

| Argument | Type | Description |
| -- | -- | -- |
| key | `string` | String representation of the desired type. Available options are predefined and available through intellisense. Instructions for adding new options below | 
| args | `any[]` | 

example creating a random `Date`
```ts
import { mocker } from '@prefecthq/orion-design'

const myRandomDate = mocker.create('date') // Date

const myMinDate = new Date('2021-04-01')
const myRandomDateAfterMin = mocker.create('date', [myMinDate]) // Date

const myMaxDate = new Date('2030-01-01')
const myRandomDateAfterMinBeforeMax = mocker.create('date', [myMinDate, myMaxDate]) // Date
```


### Did you know? ###
Mocker also has a function `mocker.createMany`. This function does the same thing, except it creates an array of random destination types, each one different. This function takes key and args just like `create`, except it also needs to know how many you want

```ts
import { mocker } from '@prefecthq/orion-design'

const randomChars = mocker.createMany('char', 500) // string[]
```

## Adding new Mocker profiles ##
In order for the mocker to know how to create this new type, we need to define a [`MockFunction`](https://github.com/PrefectHQ/orion/blob/main/orion-ui/packages/orion-design/src/services/Mocker.ts#L43).
```ts 
import { MockFunction } from '@/services/Mocker'

export const randomThing: MockFunction<Thing> = function() {
  ...
}
```
- the name of this const doesn't _actually_ matter, but `'random${DEST_TYPE}'` is the standard
- this function will be bound to the singleton `mocker`, so when within the function, `this` will be an instance of the same mocker. This is extremely useful for nesting mocks. Think of models such as `FlowRun`, which has a property `state`. Because we have a mocker for state, you can simply use `this.create('state')` for that property. Please avoid infinite nesting 🙃 
- because of the point above, it's important to define your function as I've done above and not as an arrow function as you would lose the context.
- the name of this file doesn't _actually_ matter, but camel case of the destination type is the standard, which in this case is `src/mocks/thing.ts`.

You're not done yet, just creating this mock function does NOT make it available to `mocker.create`. The next step is to add your mock function to that [predefined index](https://github.com/PrefectHQ/orion/blob/main/orion-ui/packages/orion-design/src/mocks/index.ts) I mentioned above.

```ts
import { randomThing } from './thing'

export const mocks = {
  ...
  thing: randomThing,
  ...
}
```

the format for this object is `{ destination: mockFunction }`

That's it  🙌  now you can use `mocker.create('thing')`

## Future enhancements ##
- args should be type safe, narrowed by provided key. Meaning when you use `mocker.create('string', [])`, it should know that the arguments for key 'string' are `[chars?: number]` (That used to work, not sure when it broke.)
