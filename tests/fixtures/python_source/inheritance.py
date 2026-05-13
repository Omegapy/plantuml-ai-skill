class Animal:
    name: str


class Dog(Animal):
    breed: str


class Owner:
    dogs: list[Dog]
