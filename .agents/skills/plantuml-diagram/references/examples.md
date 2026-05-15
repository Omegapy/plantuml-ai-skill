# Examples

## Sequence

```plantuml
@startuml
actor Client
participant API
database Database
Client -> API: request
API -> Database: query
Database --> API: timeout
API --> Client: error response
@enduml
```

## Class

```plantuml
@startuml
class User {
  id: UUID
  email: str
}
class Account {
  status: str
}
User "1" *-- "1..*" Account : owns
@enduml
```

## Activity

```plantuml
@startuml
start
:Receive request;
if (Valid?) then (yes)
  :Process request;
else (no)
  :Return validation error;
endif
stop
@enduml
```

## Large Activity

```plantuml
@startuml
start
:Receive request;
if (Authorized?) then (yes)
  fork
    :Validate account;
  fork again
    :Check policy;
  end fork
  split
    :Reserve capacity;
  split again
    :Notify reviewer;
  end split
else (no)
  :Reject request;
  stop
endif
repeat
  :Collect approval;
repeat while (More approvers?) is (yes)
:Publish decision;
stop
@enduml
```

## State

```plantuml
@startuml
[*] --> Draft
Draft --> Submitted : submit
Submitted --> Approved : approve
Submitted --> Rejected : reject
Approved --> [*]
Rejected --> Draft : revise
@enduml
```

## Component

```plantuml
@startuml
component "Web App" as Web
component "API" as API
database "Database" as DB
Web --> API : HTTPS
API --> DB : SQL
@enduml
```

## Large Sequence

```plantuml
@startuml
actor User
participant "Web App" as Web
participant "Policy API" as Policy
participant "Billing Service" as Billing
participant "Audit Log" as Audit
autonumber
User -> Web: submit request
par policy check
  Web -> Policy: validate request
  Policy --> Web: policy result
else billing check
  Web -> Billing: reserve funds
  Billing --> Web: reservation id
end
alt approved
  Web -> Audit: record approval
  Web --> User: confirmation
else rejected
  Web -> Audit: record rejection
  Web --> User: explain rejection
end
@enduml
```

## C4 Container

```plantuml
@startuml
!include C4_Container.puml
Person(user, "User")
System_Boundary(system, "Diagram Service") {
  Container(api, "API", "Python/FastAPI")
}
Rel(user, api, "Uses")
@enduml
```
