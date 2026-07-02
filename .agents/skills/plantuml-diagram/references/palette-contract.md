# PlantUML Palette Contract

Use this contract for generated PlantUML diagrams unless the user explicitly
asks for another visual style. The colors are derived from The AEther Flow
Website dark diagram palette.

## Palette Boundary

Use only these literal hex colors for fills, strokes, text, arrows, and labels:

- black canvas: `#000000`
- near-black fill: `#050403`
- elevated near-black fill: `#080401`
- ivory text: `#fff8ef`
- muted ivory stroke and arrows: `#d6c3b4`
- cyan family: `#0f364d`, `#164964`, `#2d7ea0`, `#48a0c0`
- orange family: `#270b01`, `#702000`, `#f87800`
- warm highlight stroke: `#f4d6a1`
- white target text when needed for contrast: `#ffffff`

The required baseline colors for generated diagrams are `#000000`, `#050403`,
`#fff8ef`, and `#d6c3b4`.

When `#0f364d` is used as a shape fill, including actors and C4 persons, use
`#d6c3b4` for the outline. Do not use `#48a0c0` as the outline on `#0f364d`
fills; it is too close visually for small strokes on the black canvas.

## Certified Family Blocks

Use `aether_dark_style_block(diagram_type)` in repository tooling. For manual
generation, insert the complete matching family block immediately after
`@start...`.

Certified rendered-palette families are sequence, class, activity, state,
component, usecase, and C4. Non-core families such as mindmap, gantt, object,
deployment, timing, and WBS use the shared base block only until a rendered
fixture certifies the family. Unknown family names are rejected by repository
tooling instead of silently receiving the base block.

### Sequence

```plantuml
skinparam backgroundColor #000000
skinparam shadowing false
skinparam defaultFontName Inter
skinparam defaultFontColor #fff8ef
skinparam ArrowColor #d6c3b4
skinparam ArrowFontColor #fff8ef
skinparam ArrowHeadColor #d6c3b4
skinparam ArrowThickness 2
skinparam DefaultTextAlignment center
skinparam ParticipantBackgroundColor #050403
skinparam ParticipantBorderColor #d6c3b4
skinparam ParticipantFontColor #fff8ef
skinparam ActorBackgroundColor #0f364d
skinparam ActorBorderColor #d6c3b4
skinparam ActorFontColor #fff8ef
skinparam DatabaseBackgroundColor #080401
skinparam DatabaseBorderColor #f4d6a1
skinparam DatabaseFontColor #fff8ef
skinparam ClassBackgroundColor #050403
skinparam ClassBorderColor #d6c3b4
skinparam ClassFontColor #fff8ef
skinparam ComponentBackgroundColor #050403
skinparam ComponentBorderColor #d6c3b4
skinparam ComponentFontColor #fff8ef
skinparam ActivityBackgroundColor #050403
skinparam ActivityBorderColor #d6c3b4
skinparam ActivityFontColor #fff8ef
skinparam StateBackgroundColor #050403
skinparam StateBorderColor #d6c3b4
skinparam StateFontColor #fff8ef
skinparam UsecaseBackgroundColor #050403
skinparam UsecaseBorderColor #d6c3b4
skinparam UsecaseFontColor #fff8ef
skinparam NoteBackgroundColor #080401
skinparam NoteBorderColor #f4d6a1
skinparam NoteFontColor #fff8ef
skinparam PackageBackgroundColor #080401
skinparam PackageBorderColor #d6c3b4
skinparam PackageFontColor #fff8ef
skinparam SequenceLifeLineBorderColor #d6c3b4
skinparam SequenceLifeLineBorderThickness 1
skinparam SequenceArrowThickness 2
```

### Class

```plantuml
skinparam backgroundColor #000000
skinparam shadowing false
skinparam defaultFontName Inter
skinparam defaultFontColor #fff8ef
skinparam ArrowColor #d6c3b4
skinparam ArrowFontColor #fff8ef
skinparam ArrowHeadColor #d6c3b4
skinparam ArrowThickness 2
skinparam DefaultTextAlignment center
skinparam ParticipantBackgroundColor #050403
skinparam ParticipantBorderColor #d6c3b4
skinparam ParticipantFontColor #fff8ef
skinparam ActorBackgroundColor #0f364d
skinparam ActorBorderColor #d6c3b4
skinparam ActorFontColor #fff8ef
skinparam DatabaseBackgroundColor #080401
skinparam DatabaseBorderColor #f4d6a1
skinparam DatabaseFontColor #fff8ef
skinparam ClassBackgroundColor #050403
skinparam ClassBorderColor #d6c3b4
skinparam ClassFontColor #fff8ef
skinparam ComponentBackgroundColor #050403
skinparam ComponentBorderColor #d6c3b4
skinparam ComponentFontColor #fff8ef
skinparam ActivityBackgroundColor #050403
skinparam ActivityBorderColor #d6c3b4
skinparam ActivityFontColor #fff8ef
skinparam StateBackgroundColor #050403
skinparam StateBorderColor #d6c3b4
skinparam StateFontColor #fff8ef
skinparam UsecaseBackgroundColor #050403
skinparam UsecaseBorderColor #d6c3b4
skinparam UsecaseFontColor #fff8ef
skinparam NoteBackgroundColor #080401
skinparam NoteBorderColor #f4d6a1
skinparam NoteFontColor #fff8ef
skinparam PackageBackgroundColor #080401
skinparam PackageBorderColor #d6c3b4
skinparam PackageFontColor #fff8ef
hide circle
skinparam ClassAttributeFontColor #fff8ef
skinparam ClassStereotypeFontColor #fff8ef
```

### Activity

```plantuml
skinparam backgroundColor #000000
skinparam shadowing false
skinparam defaultFontName Inter
skinparam defaultFontColor #fff8ef
skinparam ArrowColor #d6c3b4
skinparam ArrowFontColor #fff8ef
skinparam ArrowHeadColor #d6c3b4
skinparam ArrowThickness 2
skinparam DefaultTextAlignment center
skinparam ParticipantBackgroundColor #050403
skinparam ParticipantBorderColor #d6c3b4
skinparam ParticipantFontColor #fff8ef
skinparam ActorBackgroundColor #0f364d
skinparam ActorBorderColor #d6c3b4
skinparam ActorFontColor #fff8ef
skinparam DatabaseBackgroundColor #080401
skinparam DatabaseBorderColor #f4d6a1
skinparam DatabaseFontColor #fff8ef
skinparam ClassBackgroundColor #050403
skinparam ClassBorderColor #d6c3b4
skinparam ClassFontColor #fff8ef
skinparam ComponentBackgroundColor #050403
skinparam ComponentBorderColor #d6c3b4
skinparam ComponentFontColor #fff8ef
skinparam ActivityBackgroundColor #050403
skinparam ActivityBorderColor #d6c3b4
skinparam ActivityFontColor #fff8ef
skinparam StateBackgroundColor #050403
skinparam StateBorderColor #d6c3b4
skinparam StateFontColor #fff8ef
skinparam UsecaseBackgroundColor #050403
skinparam UsecaseBorderColor #d6c3b4
skinparam UsecaseFontColor #fff8ef
skinparam NoteBackgroundColor #080401
skinparam NoteBorderColor #f4d6a1
skinparam NoteFontColor #fff8ef
skinparam PackageBackgroundColor #080401
skinparam PackageBorderColor #d6c3b4
skinparam PackageFontColor #fff8ef
skinparam ActivityDiamondFontColor #fff8ef
skinparam ActivityBorderThickness 1
```

### State

```plantuml
skinparam backgroundColor #000000
skinparam shadowing false
skinparam defaultFontName Inter
skinparam defaultFontColor #fff8ef
skinparam ArrowColor #d6c3b4
skinparam ArrowFontColor #fff8ef
skinparam ArrowHeadColor #d6c3b4
skinparam ArrowThickness 2
skinparam DefaultTextAlignment center
skinparam ParticipantBackgroundColor #050403
skinparam ParticipantBorderColor #d6c3b4
skinparam ParticipantFontColor #fff8ef
skinparam ActorBackgroundColor #0f364d
skinparam ActorBorderColor #d6c3b4
skinparam ActorFontColor #fff8ef
skinparam DatabaseBackgroundColor #080401
skinparam DatabaseBorderColor #f4d6a1
skinparam DatabaseFontColor #fff8ef
skinparam ClassBackgroundColor #050403
skinparam ClassBorderColor #d6c3b4
skinparam ClassFontColor #fff8ef
skinparam ComponentBackgroundColor #050403
skinparam ComponentBorderColor #d6c3b4
skinparam ComponentFontColor #fff8ef
skinparam ActivityBackgroundColor #050403
skinparam ActivityBorderColor #d6c3b4
skinparam ActivityFontColor #fff8ef
skinparam StateBackgroundColor #050403
skinparam StateBorderColor #d6c3b4
skinparam StateFontColor #fff8ef
skinparam UsecaseBackgroundColor #050403
skinparam UsecaseBorderColor #d6c3b4
skinparam UsecaseFontColor #fff8ef
skinparam NoteBackgroundColor #080401
skinparam NoteBorderColor #f4d6a1
skinparam NoteFontColor #fff8ef
skinparam PackageBackgroundColor #080401
skinparam PackageBorderColor #d6c3b4
skinparam PackageFontColor #fff8ef
skinparam StateAttributeFontColor #fff8ef
```

### Component

```plantuml
skinparam backgroundColor #000000
skinparam shadowing false
skinparam defaultFontName Inter
skinparam defaultFontColor #fff8ef
skinparam ArrowColor #d6c3b4
skinparam ArrowFontColor #fff8ef
skinparam ArrowHeadColor #d6c3b4
skinparam ArrowThickness 2
skinparam DefaultTextAlignment center
skinparam ParticipantBackgroundColor #050403
skinparam ParticipantBorderColor #d6c3b4
skinparam ParticipantFontColor #fff8ef
skinparam ActorBackgroundColor #0f364d
skinparam ActorBorderColor #d6c3b4
skinparam ActorFontColor #fff8ef
skinparam DatabaseBackgroundColor #080401
skinparam DatabaseBorderColor #f4d6a1
skinparam DatabaseFontColor #fff8ef
skinparam ClassBackgroundColor #050403
skinparam ClassBorderColor #d6c3b4
skinparam ClassFontColor #fff8ef
skinparam ComponentBackgroundColor #050403
skinparam ComponentBorderColor #d6c3b4
skinparam ComponentFontColor #fff8ef
skinparam ActivityBackgroundColor #050403
skinparam ActivityBorderColor #d6c3b4
skinparam ActivityFontColor #fff8ef
skinparam StateBackgroundColor #050403
skinparam StateBorderColor #d6c3b4
skinparam StateFontColor #fff8ef
skinparam UsecaseBackgroundColor #050403
skinparam UsecaseBorderColor #d6c3b4
skinparam UsecaseFontColor #fff8ef
skinparam NoteBackgroundColor #080401
skinparam NoteBorderColor #f4d6a1
skinparam NoteFontColor #fff8ef
skinparam PackageBackgroundColor #080401
skinparam PackageBorderColor #d6c3b4
skinparam PackageFontColor #fff8ef
skinparam ComponentBorderThickness 1
```

### Use Case

```plantuml
skinparam backgroundColor #000000
skinparam shadowing false
skinparam defaultFontName Inter
skinparam defaultFontColor #fff8ef
skinparam ArrowColor #d6c3b4
skinparam ArrowFontColor #fff8ef
skinparam ArrowHeadColor #d6c3b4
skinparam ArrowThickness 2
skinparam DefaultTextAlignment center
skinparam ParticipantBackgroundColor #050403
skinparam ParticipantBorderColor #d6c3b4
skinparam ParticipantFontColor #fff8ef
skinparam ActorBackgroundColor #0f364d
skinparam ActorBorderColor #d6c3b4
skinparam ActorFontColor #fff8ef
skinparam DatabaseBackgroundColor #080401
skinparam DatabaseBorderColor #f4d6a1
skinparam DatabaseFontColor #fff8ef
skinparam ClassBackgroundColor #050403
skinparam ClassBorderColor #d6c3b4
skinparam ClassFontColor #fff8ef
skinparam ComponentBackgroundColor #050403
skinparam ComponentBorderColor #d6c3b4
skinparam ComponentFontColor #fff8ef
skinparam ActivityBackgroundColor #050403
skinparam ActivityBorderColor #d6c3b4
skinparam ActivityFontColor #fff8ef
skinparam StateBackgroundColor #050403
skinparam StateBorderColor #d6c3b4
skinparam StateFontColor #fff8ef
skinparam UsecaseBackgroundColor #050403
skinparam UsecaseBorderColor #d6c3b4
skinparam UsecaseFontColor #fff8ef
skinparam NoteBackgroundColor #080401
skinparam NoteBorderColor #f4d6a1
skinparam NoteFontColor #fff8ef
skinparam PackageBackgroundColor #080401
skinparam PackageBorderColor #d6c3b4
skinparam PackageFontColor #fff8ef
skinparam UsecaseBorderThickness 1
```

## C4 Style Block

For C4 diagrams, place the portable C4 include first, then this style block.
Repository validation maps this standard-library include to the vendored C4
snapshot:

```plantuml
!include <C4/C4_Container.puml>
skinparam backgroundColor #000000
skinparam shadowing false
skinparam defaultFontName Inter
skinparam defaultFontColor #fff8ef
skinparam ArrowColor #d6c3b4
skinparam ArrowFontColor #fff8ef
UpdateElementStyle("person", $bgColor="#0f364d", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateElementStyle("external_person", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#f4d6a1")
UpdateElementStyle("system", $bgColor="#050403", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateElementStyle("external_system", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#f4d6a1")
UpdateElementStyle("container", $bgColor="#050403", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateElementStyle("external_container", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#f4d6a1")
UpdateElementStyle("boundary", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateRelStyle($textColor="#fff8ef", $lineColor="#d6c3b4")
UpdateBoundaryStyle("system", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateBoundaryStyle("container", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateBoundaryStyle("", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#d6c3b4")
AddRelTag("risk", $textColor="#fff8ef", $lineColor="#f87800", $lineStyle=DashedLine())
```

Use C4 macros normally after that. Do not reimplement C4 macros inline.

## Rendered Validation

The strict `aether_dark_rendered_required` policy validates rendered SVG output:
no warning banner, no colors outside the approved palette, required role colors
present, and declared role-pair contrast thresholds satisfied. The rendered
exception color set starts empty; add exceptions only with visual proof and a
fixture.

Color is not the only meaning carrier. Use shape, line style, labels, notes, and
grouping to encode the diagram-specific grammar.
